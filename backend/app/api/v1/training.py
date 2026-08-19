from __future__ import annotations

import asyncio
import difflib
import json
import math
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user, require_admin
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.kb import KBMember, KnowledgeBase
from app.models.training import (
    QuestionBankItem,
    TrainingAnswer,
    TrainingQuestion,
    TrainingSession,
)
from app.models.user import User
from app.schemas.training import (
    BankBuildIn,
    BankBuildOut,
    BankItemOut,
    BankListOut,
    ExamStartIn,
    ExamStartOut,
    SubjectOut,
    TrainingGradeIn,
    TrainingQuestionOut,
    TrainingReportOut,
    TrainingSessionCreate,
    TrainingSessionOut,
)
from app.services.llm import chat_stream as llm_chat_stream

# 客观题（本地判分），主观题（送 AI 批改）
_OBJECTIVE = ("single_choice", "judge")
_BATCH = 6  # 每批最多出题数，避免一次性 20 题 JSON 被 max_tokens 截断

# 成卷题序：先判断题，再单选题，最后简答/论述/比较等主观题（同型保持原相对顺序）。
_TYPE_ORDER = {"judge": 0, "single_choice": 1}


def _order_by_type(items: list[dict]) -> list[dict]:
    """按题型分组排序成卷：判断题 → 单选题 → 其它，避免题型杂乱。"""
    return sorted(items, key=lambda c: _TYPE_ORDER.get(c.get("question_type"), 2))

router = APIRouter(prefix="/training", tags=["training"])


async def _allowed_kb_ids(db: AsyncSession, user: User, kb_ids: list[int]) -> list[int]:
    ids = list(dict.fromkeys(int(k) for k in kb_ids if k is not None))
    if not ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择至少一个知识库")
    rows = (
        await db.execute(
            select(KnowledgeBase.id)
            .outerjoin(
                KBMember,
                and_(KBMember.kb_id == KnowledgeBase.id, KBMember.user_id == user.id),
            )
            .where(
                KnowledgeBase.id.in_(ids),
                or_(
                    KnowledgeBase.owner_id == user.id,
                    KBMember.id.is_not(None),
                    KnowledgeBase.is_public.is_(True),
                ),
            )
        )
    ).scalars().all()
    allowed = set(rows)
    missing = [kb_id for kb_id in ids if kb_id not in allowed]
    if missing:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"无权访问知识库 {missing}")
    return ids


async def _load_session(db: AsyncSession, user: User, session_id: int) -> TrainingSession:
    session = (
        await db.execute(
            select(TrainingSession).where(
                TrainingSession.id == session_id,
                TrainingSession.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "训练会话不存在")
    return session


async def _collect_context(db: AsyncSession, kb_ids: list[int], topic: str, limit: int = 8) -> list[dict]:
    base = (
        select(Chunk, Document.filename)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.kb_id.in_(kb_ids))
    )
    topic = (topic or "").strip()
    rows = []
    if topic:
        pat = f"%{topic}%"
        rows = (
            await db.execute(
                base.where(Chunk.text.ilike(pat))
                .order_by(func.length(Chunk.text).desc())
                .limit(limit)
            )
        ).all()
    if not rows:
        rows = (
            await db.execute(
                base.order_by(Chunk.id.desc()).limit(limit)
            )
        ).all()
    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选知识库还没有可用于出题的内容")
    out = []
    for idx, (chunk, filename) in enumerate(rows, start=1):
        out.append(
            {
                "idx": idx,
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "kb_id": chunk.kb_id,
                "filename": filename,
                "page": chunk.page,
                "text": (chunk.text or "")[:900],
            }
        )
    return out


async def _complete_json(prompt: str, *, temperature: float = 0.25, max_tokens: int = 3000) -> str:
    messages = [{"role": "user", "content": prompt}]
    content = ""
    async for delta in llm_chat_stream(
        model=settings.default_chat_model,
        messages=messages,
        temperature=temperature,
        top_p=0.9,
        think=False,
        max_tokens=max_tokens,
    ):
        content += delta.get("content") or ""
        if delta.get("done"):
            break
    return content.strip()


def _salvage_objects(s: str) -> list[dict]:
    """从（可能被截断的）JSON 数组文本里逐个救回完整的对象。"""
    out: list[dict] = []
    depth = 0
    start: int | None = None
    in_str = False
    esc = False
    for i, ch in enumerate(s):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        o = json.loads(s[start : i + 1])
                        if isinstance(o, dict):
                            out.append(o)
                    except Exception:
                        pass
                    start = None
    return out


def _parse_json_array(raw: str) -> list[dict]:
    """健壮解析：去 fence、支持 {"questions":[...]}、截断数组逐对象救回。"""
    text = (raw or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # 1) 直接解析
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
        if isinstance(data, list):
            return [i for i in data if isinstance(i, dict)]
    except Exception:
        pass
    # 2) 截取数组片段
    lb = text.find("[")
    if lb < 0:
        # 也许是若干裸对象，尝试救回
        salvaged = _salvage_objects(text)
        if salvaged:
            return salvaged
        raise ValueError("model did not return a JSON array")
    rb = text.rfind("]")
    if rb > lb:
        try:
            d = json.loads(text[lb : rb + 1])
            if isinstance(d, list):
                return [i for i in d if isinstance(i, dict)]
        except Exception:
            pass
    # 3) 截断救回
    salvaged = _salvage_objects(text[lb:])
    if salvaged:
        return salvaged
    raise ValueError("model did not return a JSON array")


_TYPE_GUIDE = {
    "mixed": "综合搭配单选题、判断题、简答题与论述题，题型多样、比例均衡。",
    "single_choice": "全部为单项选择题：每题给出 4 个选项(A/B/C/D)，且只有一个正确。",
    "judge": "全部为判断题：给出一句关于材料的陈述，判断「对」或「错」。",
    "short_answer": "全部为简答题：考查史实、概念、人物与事件的准确记忆与理解，答案简明。",
    "essay": "全部为论述题：要求结合材料展开分析与论证，答案有观点、有层次。",
    "compare": "全部为比较辨析题：就材料中的人物、学说、书院或事件进行对比辨析。",
}
_DIFF_GUIDE = {
    "easy": "难度基础：侧重材料中明确给出的史实与概念，便于入门复习。",
    "normal": "难度进阶：在记忆基础上考查理解与归纳。",
    "hard": "难度挑战：考查综合分析、辨析与迁移应用，但仍须有材料依据。",
}


def _question_prompt(topic: str, question_type: str, difficulty: str, count: int, context: list[dict]) -> str:
    context_text = "\n\n".join(
        f"[{item['idx']}] 文件：{item['filename']}，页码：{item.get('page') or '未知'}，chunk_id：{item['chunk_id']}\n{item['text']}"
        for item in context
    )
    type_guide = _TYPE_GUIDE.get(question_type, _TYPE_GUIDE["mixed"])
    diff_guide = _DIFF_GUIDE.get(difficulty, _DIFF_GUIDE["normal"])
    return f"""你是一名豫章书院文化研学教师。请只根据给定材料，为学生生成练习题。

训练主题：{topic or "综合复习"}
题型要求：{type_guide}
难度要求：{diff_guide}
题目数量：必须恰好 {count} 题。

通用规则：
1. 出题须以下列材料为依据，但【题干必须自足】：把作答所需的背景信息直接写进题干。
   ★严禁出现“根据材料/上述材料/材料中/结合材料/如上所述/文中/上文/下文/如图/材料一”等指代外部材料的字样，
   因为学生看不到这些材料，只能看到题干本身。请像正式考卷那样，直接陈述事实再发问。
2. rubric 为可操作的评分标准；max_score 为该题满分（建议 10 分，数值类型）。
3. citations 使用材料编号数组，例如 [1, 3]，仅供系统记录出处，不会展示给学生。
4. 【多样性】本批题目须覆盖不同知识点、不同角度，彼此之间不得重复或高度相似。
5. 只输出 JSON 数组，不要 Markdown 代码块、不要任何解释文字。

各题型字段约定（type 必须是 single_choice / judge / short_answer / essay / compare 之一）：
- 单选题 single_choice：options 为 4 个选项的数组，形如
  [{{"key":"A","text":"…"}},{{"key":"B","text":"…"}},{{"key":"C","text":"…"}},{{"key":"D","text":"…"}}]；
  reference_answer 为唯一正确选项的 key（如 "B"）。
- 判断题 judge：reference_answer 取 "对" 或 "错"；options 省略或为 null。
- 简答/论述/比较 short_answer/essay/compare：reference_answer 为文本参考答案；options 为 null。

每个元素字段：type, question, options, reference_answer, rubric, max_score, citations。

材料：
{context_text}
"""


def _grade_prompt(questions: list[TrainingQuestion], answers: dict[int, str]) -> str:
    payload = []
    for q in questions:
        payload.append(
            {
                "question_id": q.id,
                "question": q.question,
                "reference_answer": q.reference_answer,
                "rubric": q.rubric,
                "max_score": q.max_score,
                "student_answer": answers.get(q.id, ""),
            }
        )
    return f"""你是一名严格但鼓励学生的阅卷教师。请根据参考答案和评分标准批改学生答案。

要求：
1. 每题分数在 0 到 max_score 之间。
2. feedback 说明得分原因，suggestion 给出下一步改进建议。
3. 只输出 JSON 数组，不要 Markdown，不要解释。
4. JSON 字段必须为：question_id, score, feedback, suggestion。

待批改内容：
{json.dumps(payload, ensure_ascii=False)}
"""


async def _grade_subjective(subjective: list[TrainingQuestion], answers: dict[int, str]) -> list[dict]:
    """批改主观题：要求模型只返回 JSON 数组；解析失败/为空时用更严格的提示重试一次。

    根因：模型偶发返回多余说明文字、代码块或被 max_tokens 截断，导致一次性解析失败
    （即"模型没有返回 JSON"）。这里给足 token 预算并重试，配合 _parse_json_array 的截断救回，
    把偶发失败降到极低；彻底失败时返回空，由上层做优雅降级而非整卷报错。"""
    n = max(1, len(subjective))
    toks = min(4096, 360 * n + 800)
    base = _grade_prompt(subjective, answers)
    for attempt in range(2):
        prompt = base
        if attempt == 1:
            prompt = base + (
                '\n\n再次强调：只输出一个 JSON 数组本身，不要 Markdown 代码块、不要任何前后说明文字。'
                '形如 [{"question_id":1,"score":8,"feedback":"…","suggestion":"…"}]。'
            )
        try:
            raw = await _complete_json(prompt, temperature=0.0 if attempt else 0.1, max_tokens=toks)
            parsed = _parse_json_array(raw)
            if parsed:
                return parsed
        except Exception:
            continue
    return []


def _safe_float(value, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _grade_objective(q: TrainingQuestion, ans: str) -> tuple[float, str, str]:
    """客观题本地判分（选择/判断），无需调用 AI。"""
    if q.question_type == "single_choice":
        ok = (ans or "").strip().upper() == (q.reference_answer or "").strip().upper()
    else:  # judge
        ok = _norm_judge(ans) == _norm_judge(q.reference_answer)
    if ok:
        return float(q.max_score), "回答正确。", "继续保持。"
    return 0.0, f"回答有误，正确答案为「{q.reference_answer}」。", "对照材料复核该知识点。"


@router.post("/sessions", response_model=TrainingSessionOut, status_code=201)
async def create_session(
    data: TrainingSessionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    kb_ids = await _allowed_kb_ids(db, user, data.kb_ids)
    title = data.title or (data.topic.strip() if data.topic.strip() else "AI 问答训练")
    session = TrainingSession(
        user_id=user.id,
        title=title[:256],
        topic=data.topic.strip(),
        question_type=data.question_type,
        difficulty=data.difficulty,
        question_count=data.question_count,
        kb_ids=kb_ids,
        status="draft",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=list[TrainingSessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前用户的历史答题记录（最近 100 条，最新在前）。"""
    rows = (
        await db.execute(
            select(TrainingSession)
            .where(TrainingSession.user_id == user.id)
            .order_by(TrainingSession.updated_at.desc())
            .limit(100)
        )
    ).scalars().all()
    return rows


def _resolve_citations(citation_idxs, context_by_idx: dict) -> list[dict]:
    citations: list[dict] = []
    for idx in citation_idxs or []:
        try:
            source = context_by_idx.get(int(idx))
        except Exception:
            source = None
        if source:
            citations.append(
                {
                    "idx": source["idx"],
                    "chunk_id": source["chunk_id"],
                    "document_id": source["document_id"],
                    "kb_id": source.get("kb_id"),
                    "filename": source["filename"],
                    "page": source["page"],
                }
            )
    return citations


_LETTERS = "ABCDEFGH"
_TRUE_SET = {"对", "正确", "√", "T", "TRUE", "是", "对的"}
_FALSE_SET = {"错", "错误", "×", "F", "FALSE", "否", "错的"}


def _norm_options(raw) -> list[dict] | None:
    if not isinstance(raw, list):
        return None
    out: list[dict] = []
    for i, o in enumerate(raw):
        if isinstance(o, dict):
            key = str(o.get("key") or (_LETTERS[i] if i < len(_LETTERS) else i)).strip()
            text = str(o.get("text") or o.get("value") or "").strip()
        else:
            key = _LETTERS[i] if i < len(_LETTERS) else str(i)
            text = str(o).strip()
        if text:
            out.append({"key": key, "text": text})
    return out or None


def _norm_judge(s: str) -> str:
    v = (s or "").strip()
    if v in _TRUE_SET:
        return "对"
    if v in _FALSE_SET:
        return "错"
    return v


# 题干若指代“学生看不到的材料”，判为不合格直接丢弃（防止出现“根据材料…”这类题）。
_MATERIAL_REFS = (
    "根据材料", "上述材料", "结合材料", "依据材料", "材料中", "材料一", "材料二", "材料所",
    "根据上述", "如上所述", "上文", "下文", "文中", "本文", "短文", "阅读材料", "根据以上",
    "根据短文", "结合上文", "结合下文", "如图",
)


def _refs_external_material(q: str) -> bool:
    return any(p in q for p in _MATERIAL_REFS)


def _normalize_item(item: dict, default_type: str, context_by_idx: dict) -> dict | None:
    q = str(item.get("question") or "").strip()
    if not q or _refs_external_material(q):
        return None
    qtype = str(item.get("type") or default_type or "short_answer")[:64]
    if qtype == "mixed":
        qtype = "short_answer"
    options: list[dict] | None = None
    ref = str(item.get("reference_answer") or "").strip()
    if qtype == "single_choice":
        options = _norm_options(item.get("options"))
        if not options or len(options) < 2:
            return None
        keys = {o["key"] for o in options}
        if ref not in keys:
            ref = next((o["key"] for o in options if o["text"] == ref), ref.upper()[:8])
    elif qtype == "judge":
        options = [{"key": "对", "text": "正确"}, {"key": "错", "text": "错误"}]
        ref = _norm_judge(ref)
    if not ref:
        return None
    return {
        "question_type": qtype,
        "question": q,
        "reference_answer": ref,
        "rubric": str(item.get("rubric") or "").strip(),
        "max_score": max(1, _safe_float(item.get("max_score"), 10)),
        "options": options,
        "citations": _resolve_citations(item.get("citations"), context_by_idx),
    }


def _tokens_for(n: int) -> int:
    return min(4096, 400 * n + 700)


def _norm_q(s: str) -> str:
    """题干归一化：去标点与空白，便于近似查重。"""
    s = re.sub(r"[，。、；：？！,.;:?!\"'“”‘’（）()【】\[\]\s]", "", s or "")
    return s


def _is_dup(qnorm: str, seen: list[str], threshold: float = 0.86) -> bool:
    """与已收题做近似比对（difflib 相似度），仅拦截【近乎雷同】的题。
    阈值刻意取高：经验上“同句式不同主体”（如陆九渊/王阳明各一问）相似度可达 ~0.77，
    若阈值过低会误删这类本应保留的不同题，故以源头多样化为主、本查重仅作兜底。"""
    for s in seen:
        if difflib.SequenceMatcher(None, qnorm, s).ratio() >= threshold:
            return True
    return False


async def _generate_batch(
    topic: str, question_type: str, difficulty: str, n: int, context: list[dict]
) -> list[dict]:
    """生成一批题目；解析失败时小批重试一次，仍失败返回空（让其它批次照常产出）。
    温度略升以增加并发批次之间的多样性（仍以材料为依据）。"""
    prompt = _question_prompt(topic, question_type, difficulty, n, context)
    try:
        return _parse_json_array(await _complete_json(prompt, temperature=0.55, max_tokens=_tokens_for(n)))
    except Exception:
        try:
            small = min(n, 4)
            p2 = _question_prompt(topic, question_type, difficulty, small, context)
            return _parse_json_array(await _complete_json(p2, temperature=0.55, max_tokens=_tokens_for(small)))
        except Exception:
            return []


async def _ai_generate(
    db: AsyncSession,
    kb_ids: list[int],
    topic: str,
    question_type: str,
    difficulty: str,
    count: int,
) -> list[dict]:
    """分批调用大模型出题——各批【并发】执行（避免 30 题串行超时）。
    为降低并发批次出重题的概率：① 抓取更大的材料池，给每批【不同的材料子集】作依据；
    ② 略升温度增加多样性；③ 合并时按题干做【近似查重】，相似题只保留一条。"""
    # 材料池放大到约「题量」规模（上限 30），让各批有不同素材可用。
    pool = await _collect_context(db, kb_ids, topic, limit=min(30, max(8, count)))
    context_by_idx = {item["idx"]: item for item in pool}
    batches = max(1, math.ceil(count / _BATCH))
    # 轮转切分材料：第 i 批拿 pool[i::batches]，彼此材料尽量不重叠（材料太少时回退用整池）。
    subsets = [pool[i::batches] or pool for i in range(batches)]
    results = await asyncio.gather(
        *[
            _generate_batch(topic, question_type, difficulty, _BATCH, subsets[i])
            for i in range(batches)
        ]
    )
    out: list[dict] = []
    seen_norms: list[str] = []
    for items in results:
        for item in items:
            d = _normalize_item(item, question_type, context_by_idx)
            if not d:
                continue
            qn = _norm_q(d["question"])
            if not qn or _is_dup(qn, seen_norms):
                continue
            seen_norms.append(qn)
            out.append(d)
            if len(out) >= count:
                break
        if len(out) >= count:
            break
    return out[:count]


def _save_to_bank(
    db: AsyncSession,
    dicts: list[dict],
    topic: str,
    question_type: str,
    difficulty: str,
    default_kb_id: int,
) -> None:
    """把 AI 新出的题写入题库以便复用。题库归属取首条引用所在 KB。"""
    topic = (topic or "").strip()[:512]
    for d in dicts:
        cits = d.get("citations") or []
        kb_id = next((int(c["kb_id"]) for c in cits if c.get("kb_id")), None) or default_kb_id
        db.add(
            QuestionBankItem(
                kb_id=kb_id,
                topic=topic,
                question_type=d["question_type"],
                difficulty=difficulty,
                question=d["question"],
                reference_answer=d["reference_answer"],
                rubric=d.get("rubric") or "",
                max_score=d["max_score"],
                citations=cits,
                options=d.get("options"),
            )
        )


async def _bank_pick(
    db: AsyncSession,
    kb_ids: list[int],
    topic: str,
    question_type: str,
    difficulty: str,
    count: int,
) -> list[dict]:
    """从题库随机抽取匹配的题目（题型/难度/KB，主题可选）。"""
    conds = [QuestionBankItem.kb_id.in_(kb_ids), QuestionBankItem.difficulty == difficulty]
    if question_type and question_type != "mixed":
        conds.append(QuestionBankItem.question_type == question_type)
    stmt = select(QuestionBankItem).where(*conds)
    topic = (topic or "").strip()
    if topic:
        stmt = stmt.where(
            or_(QuestionBankItem.topic == topic, QuestionBankItem.question.ilike(f"%{topic}%"))
        )
    stmt = stmt.order_by(func.rand()).limit(count)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "question_type": r.question_type,
            "question": r.question,
            "reference_answer": r.reference_answer,
            "rubric": r.rubric,
            "max_score": r.max_score,
            "citations": r.citations or [],
            "options": r.options,
        }
        for r in rows
    ]


@router.post("/sessions/{session_id}/generate", response_model=list[TrainingQuestionOut])
async def generate_questions(
    session_id: int,
    fresh: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """出题：默认题库优先（命中即秒出），不足部分再调用 AI 并自动入库；
    fresh=true 时跳过题库、强制 AI 重新出题（结果同样入库）。"""
    session = await _load_session(db, user, session_id)
    kb_ids = await _allowed_kb_ids(db, user, list(session.kb_ids or []))
    need = session.question_count

    chosen: list[dict] = []
    if not fresh:
        chosen = await _bank_pick(
            db, kb_ids, session.topic, session.question_type, session.difficulty, need
        )

    remaining = need - len(chosen)
    if remaining > 0:
        ai_dicts = await _ai_generate(
            db, kb_ids, session.topic, session.question_type, session.difficulty, remaining
        )
        if ai_dicts:
            _save_to_bank(
                db, ai_dicts, session.topic, session.question_type, session.difficulty, kb_ids[0]
            )
            chosen.extend(ai_dicts)

    chosen = [c for c in chosen if c["question"] and c["reference_answer"]][:need]
    if not chosen:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "未能获取可用题目，请稍后重试")
    chosen = _order_by_type(chosen)

    await db.execute(delete(TrainingAnswer).where(TrainingAnswer.session_id == session.id))
    await db.execute(delete(TrainingQuestion).where(TrainingQuestion.session_id == session.id))

    questions = [
        TrainingQuestion(
            session_id=session.id,
            seq=seq,
            question_type=c["question_type"],
            question=c["question"],
            reference_answer=c["reference_answer"],
            rubric=c.get("rubric") or "",
            max_score=c["max_score"],
            citations=c.get("citations") or [],
            options=c.get("options"),
        )
        for seq, c in enumerate(chosen, start=1)
    ]
    db.add_all(questions)
    session.status = "generated"
    session.total_score = None
    session.updated_at = datetime.now()
    await db.commit()
    for q in questions:
        await db.refresh(q)
    return questions


@router.post("/bank/build", response_model=BankBuildOut)
async def build_bank(
    data: BankBuildIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """【管理后台】预先扩充题库：按知识库/主题/题型/难度批量 AI 出题并入库，供之后秒速出卷。"""
    kb_ids = await _allowed_kb_ids(db, user, data.kb_ids)
    ai_dicts = await _ai_generate(db, kb_ids, data.topic, data.question_type, data.difficulty, data.count)
    if not ai_dicts:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI 没有生成可用题目")
    _save_to_bank(db, ai_dicts, data.topic, data.question_type, data.difficulty, kb_ids[0])
    await db.commit()
    total = (
        await db.execute(
            select(func.count(QuestionBankItem.id)).where(QuestionBankItem.kb_id.in_(kb_ids))
        )
    ).scalar_one()
    return BankBuildOut(added=len(ai_dicts), total=int(total))


@router.get("/bank", response_model=BankListOut)
async def list_bank(
    kb_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """【管理后台】分页查看题库。"""
    conds = [QuestionBankItem.kb_id == kb_id] if kb_id is not None else []
    total = (await db.execute(select(func.count(QuestionBankItem.id)).where(*conds))).scalar_one()
    rows = (
        await db.execute(
            select(QuestionBankItem)
            .where(*conds)
            .order_by(QuestionBankItem.id.desc())
            .limit(min(max(limit, 1), 200))
            .offset(max(offset, 0))
        )
    ).scalars().all()
    return {"items": rows, "total": int(total)}


@router.delete("/bank/{item_id}", status_code=204)
async def delete_bank_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """【管理后台】删除一道题库题。"""
    item = await db.get(QuestionBankItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    await db.delete(item)
    await db.commit()


# ---- 学生考试：按「科目 + 难度」从题库抽题（不涉及知识库，前台零自定义）----
# 科目 = 题库题目的 topic 字段；空 topic 归为「综合」。
_GENERAL = "综合"


async def _bank_pick_subject(db: AsyncSession, subject: str, difficulty: str, count: int) -> list[dict]:
    conds = [QuestionBankItem.difficulty == difficulty]
    subject = (subject or "").strip()
    if subject and subject != _GENERAL:
        conds.append(QuestionBankItem.topic == subject)
    else:
        conds.append(or_(QuestionBankItem.topic == "", QuestionBankItem.topic.is_(None)))
    stmt = select(QuestionBankItem).where(*conds).order_by(func.rand()).limit(count)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "question_type": r.question_type,
            "question": r.question,
            "reference_answer": r.reference_answer,
            "rubric": r.rubric,
            "max_score": r.max_score,
            "citations": r.citations or [],
            "options": r.options,
        }
        for r in rows
    ]


@router.get("/subjects", response_model=list[SubjectOut])
async def list_subjects(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """学生端可选「科目」列表（来自题库，按难度统计可用题量）。"""
    rows = (
        await db.execute(
            select(QuestionBankItem.topic, QuestionBankItem.difficulty, func.count(QuestionBankItem.id))
            .group_by(QuestionBankItem.topic, QuestionBankItem.difficulty)
        )
    ).all()
    agg: dict[str, dict] = {}
    for topic, diff, cnt in rows:
        subj = (topic or "").strip() or _GENERAL
        a = agg.setdefault(subj, {"subject": subj, "total": 0, "easy": 0, "normal": 0, "hard": 0})
        a["total"] += int(cnt)
        if diff in ("easy", "normal", "hard"):
            a[diff] += int(cnt)
    return sorted(agg.values(), key=lambda x: -x["total"])


@router.post("/exam", response_model=ExamStartOut, status_code=201)
async def start_exam(
    data: ExamStartIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """学生开始考试：按科目+难度从题库抽题成卷（题库已由管理员维护，不现场调用 AI）。"""
    picked = await _bank_pick_subject(db, data.subject, data.difficulty, data.count)
    if not picked:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该科目下暂无可用题目，请联系管理员在题库中添加。")
    picked = _order_by_type(picked)
    subj = (data.subject or "").strip() or _GENERAL
    diff_label = {"easy": "基础", "normal": "进阶", "hard": "挑战"}.get(data.difficulty, data.difficulty)
    session = TrainingSession(
        user_id=user.id,
        title=f"{subj} · {diff_label}卷"[:256],
        topic=subj,
        question_type="mixed",
        difficulty=data.difficulty,
        question_count=len(picked),
        kb_ids=[],
        status="generated",
    )
    db.add(session)
    await db.flush()
    questions = [
        TrainingQuestion(
            session_id=session.id,
            seq=seq,
            question_type=c["question_type"],
            question=c["question"],
            reference_answer=c["reference_answer"],
            rubric=c.get("rubric") or "",
            max_score=c["max_score"],
            citations=c.get("citations") or [],
            options=c.get("options"),
        )
        for seq, c in enumerate(picked, start=1)
    ]
    db.add_all(questions)
    await db.commit()
    await db.refresh(session)
    for q in questions:
        await db.refresh(q)
    return {"session": session, "questions": questions}


@router.post("/sessions/{session_id}/grade", response_model=TrainingReportOut)
async def grade_session(
    session_id: int,
    data: TrainingGradeIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = await _load_session(db, user, session_id)
    questions = (
        await db.execute(
            select(TrainingQuestion)
            .where(TrainingQuestion.session_id == session.id)
            .order_by(TrainingQuestion.seq)
        )
    ).scalars().all()
    if not questions:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先生成题目")
    answer_map = {item.question_id: item.answer.strip() for item in data.answers}
    valid_ids = {q.id for q in questions}
    answer_map = {qid: answer for qid, answer in answer_map.items() if qid in valid_ids}
    if not answer_map:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请至少提交一道题的答案")

    # 主观题（简答/论述/比较）才送 AI 批改；客观题本地判分。
    subjective = [q for q in questions if q.question_type not in _OBJECTIVE]
    has_subjective_answers = any(answer_map.get(q.id) for q in subjective)
    graded_by_id: dict[int, dict] = {}
    if subjective and has_subjective_answers:
        graded = await _grade_subjective(subjective, answer_map)
        # 彻底解析失败（重试后仍为空）才报错，让用户重试；部分成功则用已得结果，
        # 缺失的题在下方回退为中性反馈，不至于整卷失败。
        if not graded:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "AI 批改暂时不可用，请稍后重试。"
            )
        for item in graded:
            try:
                graded_by_id[int(item.get("question_id"))] = item
            except Exception:
                continue

    await db.execute(delete(TrainingAnswer).where(TrainingAnswer.session_id == session.id))
    answers: list[TrainingAnswer] = []
    for q in questions:
        ans = answer_map.get(q.id, "")
        if q.question_type in _OBJECTIVE:
            score, feedback, suggestion = _grade_objective(q, ans)
        else:
            item = graded_by_id.get(q.id, {})
            score = max(0, min(float(q.max_score), _safe_float(item.get("score", 0), 0)))
            feedback = str(item.get("feedback") or "本题未获得有效批改反馈。").strip()
            suggestion = str(item.get("suggestion") or "建议对照参考答案补充关键事实。").strip()
        answers.append(
            TrainingAnswer(
                session_id=session.id,
                question_id=q.id,
                answer=ans,
                score=score,
                feedback=feedback,
                suggestion=suggestion,
            )
        )
    db.add_all(answers)
    session.status = "graded"
    max_total = sum(float(q.max_score or 0) for q in questions) or 1
    session.total_score = round(sum(a.score for a in answers) / max_total * 100, 1)
    session.updated_at = datetime.now()
    await db.commit()
    await db.refresh(session)
    for a in answers:
        await db.refresh(a)
    return {"session": session, "questions": questions, "answers": answers}


@router.get("/sessions/{session_id}/report", response_model=TrainingReportOut)
async def get_report(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = await _load_session(db, user, session_id)
    questions = (
        await db.execute(
            select(TrainingQuestion)
            .where(TrainingQuestion.session_id == session.id)
            .order_by(TrainingQuestion.seq)
        )
    ).scalars().all()
    answers = (
        await db.execute(
            select(TrainingAnswer)
            .where(TrainingAnswer.session_id == session.id)
            .order_by(TrainingAnswer.question_id)
        )
    ).scalars().all()
    return {"session": session, "questions": questions, "answers": answers}

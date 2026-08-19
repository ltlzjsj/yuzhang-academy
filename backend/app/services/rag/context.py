"""Build an LLM system prompt that embeds retrieved chunks as citations."""
from __future__ import annotations

import re

from app.core.config import settings
from app.services.rag.retriever import RetrievedChunk

_DEFAULT_INSTRUCTION = (
    "你是一个基于知识库的江西书院问答助手。回答必须优先依据「已命中问答库」和「参考资料」。\n"
    "【引用规范】凡用到某条资料，就在该句末标注其编号；用到多条要分别标注，例如 [1][3]。"
    "不要把所有内容都只标 [1]——有几条相关就用几个编号，鼓励引用多个来源。\n"
    "【资料不足】若资料不足，请先说明「资料中未提及」或「资料不足以确认」，再在单独的「模型补充」段落补充通用知识，"
    "不要把模型补充伪装成知识库事实。"
)

_IMAGE_INSTRUCTION = (
    "【配图】系统会自动在你的回答下方展示与该书院相关的图片，你无需也无法自行生成或绘制图片。"
    "若用户索要图片，直接说「下方已附上相关图片」并据图简要描述即可，切勿回复「我无法生成图片」之类。"
)


# Aggressive table HTML → markdown-ish rows. Keeps the LLM cheap while the
# table stays readable — we're not trying to preserve layout, just the cell
# values and row alignment.
_TAG_TR = re.compile(r"</\s*tr\s*>", re.I)
_TAG_CELL_CLOSE = re.compile(r"</\s*(td|th)\s*>", re.I)
_TAG_ANY = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\u00a0]+")


def _table_html_to_text(html: str, *, max_rows: int = 12, max_chars: int = 1200) -> str:
    """Render a (simple) HTML <table> to ``row1 | row2 | …`` lines."""
    if not html:
        return ""
    # Split rows first so cell-separator whitespace is safe to collapse after
    rows = _TAG_TR.split(html)
    out_lines: list[str] = []
    for raw in rows:
        cells = _TAG_CELL_CLOSE.sub("\t", raw)  # delimit cells with tabs
        cells = _TAG_ANY.sub("", cells)
        cells = cells.replace("\r", " ").replace("\n", " ")
        cells = _WS.sub(" ", cells).strip(" \t")
        parts = [c.strip() for c in cells.split("\t") if c.strip()]
        if not parts:
            continue
        out_lines.append(" | ".join(parts))
        if len(out_lines) >= max_rows:
            out_lines.append("…（表格后续行略）")
            break
    rendered = "\n".join(out_lines).strip()
    if len(rendered) > max_chars:
        rendered = rendered[:max_chars].rstrip() + "…"
    return rendered


def _render_structured_extras(r: RetrievedChunk) -> str:
    """Extra block appended to a citation body when it carries tables/formulas."""
    if not r.meta:
        return ""
    extras_lines: list[str] = []
    tables = r.meta.get("tables") or []
    for t in tables:
        html = t.get("html") or ""
        rendered = _table_html_to_text(html) or (t.get("text") or "").strip()
        if not rendered:
            continue
        cap = (t.get("caption") or "").strip()
        head = f"【表】{cap}" if cap else "【表】"
        extras_lines.append(f"{head}\n{rendered}")
    formulas = r.meta.get("formulas") or []
    for f in formulas:
        latex = (f.get("latex") or "").strip()
        if latex:
            extras_lines.append(f"【公式】$ {latex} $")
    return "\n\n".join(extras_lines)


def _chunk_images(r: RetrievedChunk) -> list[dict]:
    if not r.meta:
        return []
    imgs = r.meta.get("images")
    return imgs if isinstance(imgs, list) else []


def collect_images(
    retrieved: list[RetrievedChunk],
    *,
    max_images: int | None = None,
) -> list[dict]:
    """Aggregate unique figures across retrieved chunks (book reading order).

    Returns ``[{"src", "page", "caption", "filename"}]`` — ``src`` is the web
    path under the ``/api/v1/assets/mineru`` static mount. Deduped by ``src``,
    capped to ``max_images`` (defaults to ``settings.rag_max_images``).
    """
    cap = int(max_images if max_images is not None else settings.rag_max_images)
    out: list[dict] = []
    seen: set[str] = set()
    for r in retrieved:
        for im in _chunk_images(r):
            src = im.get("src")
            if not src or src in seen:
                continue
            seen.add(src)
            out.append(
                {
                    "src": src,
                    "page": im.get("page") or r.page,
                    "caption": im.get("caption") or "",
                    "filename": r.filename,
                    "kind": "mineru",
                }
            )
            if len(out) >= cap:
                return out
    return out


def _matched_qa(r: RetrievedChunk) -> dict | None:
    if not r.meta:
        return None
    qa = r.meta.get("_matched_qa")
    return qa if isinstance(qa, dict) else None


def build_rag_system_prompt(
    base_system: str | None,
    retrieved: list[RetrievedChunk],
    *,
    max_chars_per_chunk: int = 400,
    include_image_instruction: bool = True,
) -> str:
    parts: list[str] = []
    if base_system and base_system.strip():
        parts.append(base_system.strip())
    parts.append(_DEFAULT_INSTRUCTION)
    if include_image_instruction:
        parts.append(_IMAGE_INSTRUCTION)

    if retrieved:
        direct_hits: list[str] = []
        for i, r in enumerate(retrieved, start=1):
            qa = _matched_qa(r)
            if not qa:
                continue
            score = float(qa.get("score") or 0.0)
            if score < float(settings.rag_direct_qa_min_score):
                continue
            q = (qa.get("question") or "").strip()
            a = (qa.get("answer") or "").strip()
            if q and a:
                direct_hits.append(
                    f"[{i}] 来源：{r.filename} p.{r.page or 'n/a'}，QA相似度 {score:.3f}\n问：{q}\n答：{a}"
                )
        if direct_hits:
            parts.append(
                "---\n# 已命中问答库\n"
                "以下问答与用户问题高度相似。若能回答用户问题，应优先依据这些答案，并保留对应引用编号。\n"
                + "\n\n".join(direct_hits)
            )
        parts.append("---\n# 参考资料")
        used_chars = 0
        total_budget = max(800, int(settings.rag_context_max_chars or 3200))
        for i, r in enumerate(retrieved, start=1):
            remaining = total_budget - used_chars
            if remaining <= 0:
                break
            text = (r.text or "").strip().replace("\n\n", "\n")
            if len(text) > max_chars_per_chunk:
                text = text[:max_chars_per_chunk] + "…"
            page_str = f"p.{r.page}" if r.page else "n/a"
            extras = _render_structured_extras(r)
            qa = _matched_qa(r)
            qa_block = ""
            if qa:
                q = (qa.get("question") or "").strip()
                a = (qa.get("answer") or "").strip()
                score = float(qa.get("score") or 0.0)
                if q and a:
                    qa_block = f"【关联问答，score={score:.3f}】\n问：{q}\n答：{a}"
            body_parts = [x for x in (qa_block, text, extras) if x]
            body = "\n\n".join(body_parts)
            if len(body) > remaining:
                body = body[:remaining].rstrip() + "…"
            used_chars += len(body)
            parts.append(f"[{i}] 《{r.filename}》 {page_str}\n{body}")
        # 图文: if any retrieved chunk carries figures, tell the model the
        # images shown to it correspond to these academies so it can describe
        # them when relevant.
        if include_image_instruction and any(_chunk_images(r) for r in retrieved):
            parts.append(
                "---\n# 配图说明\n本次已随消息附上与上述书院相关的图片，并会自动展示在你回答的下方。"
                "你可以结合图片描述书院的建筑、景观、碑刻文物等，但不要虚构图中不存在的细节；"
                "不要声称自己无法生成或提供图片（图片由系统负责展示）。"
            )
    else:
        parts.append("---\n# 参考资料\n（本次检索未命中相关资料）")

    return "\n\n".join(parts)


def citations_payload(
    retrieved: list[RetrievedChunk],
    *,
    gate_reason: str | None = None,
) -> list[dict]:
    """Serialisable list for the SSE `citations` event + message.citations column."""
    out: list[dict] = []
    for i, r in enumerate(retrieved, start=1):
        preview = (r.text or "").strip().replace("\n", " ")
        if len(preview) > 200:
            preview = preview[:200] + "…"
        # Flag the citation if it carries structured extras so the UI can hint
        # to the user there's a table/formula attached.
        has_table = bool(r.meta and (r.meta.get("tables") or []))
        has_formula = bool(r.meta and (r.meta.get("formulas") or []))
        structured_preview = _render_structured_extras(r) if (has_table or has_formula) else ""
        if len(structured_preview) > 1200:
            structured_preview = structured_preview[:1200].rstrip() + "..."
        retrieval = dict((r.meta or {}).get("_retrieval") or {})
        matched_qa = _matched_qa(r)
        if matched_qa:
            retrieval["matched_qa"] = matched_qa
        if gate_reason:
            retrieval["gate_reason"] = gate_reason
        out.append(
            {
                "idx": i,
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "kb_id": r.kb_id,
                "page": r.page,
                "bbox": r.bbox,
                "filename": r.filename,
                "text_preview": preview,
                "score": round(r.score, 6),
                "retrieval": retrieval,
                "matched_qa": matched_qa,
                "has_table": has_table,
                "has_formula": has_formula,
                "structured_preview": structured_preview,
                "images": _chunk_images(r),
            }
        )
    return out

"""江西书院名录与查询匹配。

语料是一本江右(江西)书院图文志，章节以书院为单位。检索改为 BM25 关键词后，
这里提供"书院名"维度的轻量加权：当用户问题里出现某个书院名时，检索结果中正文
含该名的 chunk 获得额外加分，确保"问某书院"稳定命中其所在章节，而不会被同样
高频的"书院"二字稀释到其它书院。

名录取自该书目录(约 70 所书院 + 若干专题)。如后续语料扩充，往 ACADEMIES 追加即可。
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from app.core.config import settings

# 书院/书舍/文馆等正式名称。按字符串长度降序匹配，避免短名(如"义学")吞掉长名。
ACADEMIES: tuple[str, ...] = (
    "白鹿洞书院", "白鹭洲书院", "鹅湖书院", "象山书院", "豫章书院", "友教书院",
    "东湖书院", "墨庄书院", "阳明书院", "潋江书院", "易堂书院", "新安书院",
    "鳌峰书院", "华林书院", "昌黎书院", "龙光书院", "紫阳书院", "六柳书院",
    "凤仪书院", "明月轩书院", "天宝古书院", "奎光书院", "正谊书院", "桂林书院",
    "龙江书院", "燕山书院", "曲山书院", "石莲书院", "新兴书院", "复古书院",
    "复真书院", "山角书院", "匡山书院", "复初书舍", "衡公书舍", "武城书院",
    "青云书院", "泷冈书院", "爱莲书院", "横溪书院", "朗山书院", "科山书院",
    "涧东书院", "竹隐书院", "叠山书院", "信江书院", "明经书院", "含珠书院",
    "东山书院", "端明书院", "仰山书院", "兴鲁书院", "雯峰书院", "应宿第书院",
    "怀仁书院", "问渠书院", "流坑文馆", "如蘭书院", "元猷书院", "盱江书院",
    "凤巘书院", "高峰书院", "同文书院", "云溪书院", "柳山书院", "东佳书院",
    "净明堂书院", "长芗书院", "复礼书院", "龙溪书院", "义学",
    # 专题章节
    "江西书院十大人物", "江西书院十大事件",
)

# 长名优先，防止子串误吞
_SORTED = tuple(sorted(set(ACADEMIES), key=len, reverse=True))
_ACADEMY_ALIASES: tuple[tuple[str, str], ...] = (
    ("白鹿书院", "白鹿洞书院"),
    ("白鹿洞", "白鹿洞书院"),
    ("庐山白鹿洞", "白鹿洞书院"),
    ("白鹭书院", "白鹭洲书院"),
    ("白鹭洲", "白鹭洲书院"),
)


def detect_academies(query: str) -> list[str]:
    """返回 query 中出现的书院名(去重，按出现顺序/长度优先)。"""
    q = query or ""
    matches: list[tuple[int, int, str]] = []
    for name in _SORTED:
        pos = q.find(name)
        if pos >= 0:
            matches.append((pos, -len(name), name))
    for alias, canonical in _ACADEMY_ALIASES:
        pos = q.find(alias)
        if pos >= 0:
            matches.append((pos, -len(alias), canonical))
    matches.sort()
    found: list[str] = []
    for _pos, _neg_len, name in matches:
        if name not in found:
            found.append(name)
    return found


_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _iter_image_files(base: Path) -> list[tuple[str, Path]]:
    """递归列出图片文件，返回 (相对 posix 路径, 绝对路径)，按路径排序。"""
    files: list[tuple[str, Path]] = []
    for f in base.rglob("*"):
        if f.is_file() and f.suffix.lower() in _IMG_EXT:
            files.append((f.relative_to(base).as_posix(), f))
    files.sort(key=lambda t: t[0])
    return files


_DROP_CHARS = re.compile(r"[\s\-_.,，。、《》〈〉（）()【】\[\]“”\"'`·　]+")
_ACADEMY_SUFFIXES = ("书院", "书堂", "书舍", "精舍", "义学", "文馆")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    return _DROP_CHARS.sub("", s)


def _academy_terms(name: str) -> list[str]:
    terms = [name]
    for suffix in _ACADEMY_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            terms.append(name[: -len(suffix)])
            break
    out: list[str] = []
    seen: set[str] = set()
    for term in terms:
        n = _norm(term)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _image_match_score(name: str, rel: str, file_stem: str) -> int:
    terms = _academy_terms(name)
    if not terms:
        return 0
    rel_norm = _norm(rel)
    stem_norm = _norm(file_stem)
    exact = terms[0]
    if exact in stem_norm:
        return 120
    if exact in rel_norm:
        return 100
    for alias in terms[1:]:
        if len(alias) >= 2 and alias in stem_norm:
            return 80
        if len(alias) >= 2 and alias in rel_norm:
            return 60
    return 0


def _manifest_path(base: Path) -> Path:
    configured = Path(settings.academy_images_manifest or "manifest.json")
    return configured if configured.is_absolute() else base / configured


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _read_manifest(base: Path) -> list[dict]:
    path = _manifest_path(base)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = data.get("images", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []

    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        src = str(item.get("src") or "").replace("\\", "/").strip()
        if not src or Path(src).suffix.lower() not in _IMG_EXT:
            continue
        fp = base / src
        if not fp.is_file():
            continue
        try:
            priority = int(item.get("priority", 50))
        except (TypeError, ValueError):
            priority = 50
        academies = [str(x).strip() for x in _as_list(item.get("academy")) if str(x).strip()]
        tags = [str(x).strip() for x in _as_list(item.get("tags")) if str(x).strip()]
        out.append(
            {
                "src": src,
                "caption": str(item.get("caption") or fp.stem).strip(),
                "academy": academies,
                "tags": tags,
                "priority": priority,
                "source": str(item.get("source") or "").strip(),
                "_file": fp,
            }
        )
    return out


def _manifest_match_score(name: str, entry: dict) -> int:
    src = entry["src"]
    fp: Path = entry["_file"]
    score = _image_match_score(name, src, fp.stem)

    name_terms = _academy_terms(name)
    for academy in entry.get("academy") or []:
        academy_terms = _academy_terms(academy)
        if name_terms and academy_terms and name_terms[0] == academy_terms[0]:
            score = max(score, 1000)
        elif set(name_terms) & set(academy_terms):
            score = max(score, 850)

    haystack = " ".join(
        [entry.get("caption") or "", entry.get("source") or "", " ".join(entry.get("tags") or [])]
    )
    haystack_norm = _norm(haystack)
    if score <= 0:
        for term in name_terms:
            if term and term in haystack_norm:
                score = max(score, 500)

    if score <= 0:
        return 0
    return score + max(0, int(entry.get("priority") or 0))


def _source_from_rel(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else ""


def images_for_academies(
    names: list[str],
    base_dir: str | Path,
    *,
    max_total: int = 6,
    exclude_srcs: set[str] | None = None,
) -> list[dict]:
    """收集用户自备的书院图片，按书院名在「文件路径」中做子串匹配。

    适配实际素材的组织方式：书院名常出现在文件名或父目录里（如
    ``江西四大书院/白鹿洞书院/白鹿洞书院石牌坊.jpg``、``吉安科山书院.JPG``），
    无需把图片重整成「一个书院一个文件夹」。

    返回 ``[{"src", "caption", "academy", "kind", "page"}]``：``src`` 是 academy
    静态挂载下的相对路径，``caption`` 取文件名（去扩展名，比书院名更具体），
    ``kind="academy"`` 供前端/识图选根。多个书院按传入顺序匹配，整体上限 ``max_total``。
    """
    base = Path(base_dir)
    if not base.is_dir() or not names:
        return []
    all_files = _iter_image_files(base)
    manifest_entries = _read_manifest(base)
    out: list[dict] = []
    seen: set[str] = set(exclude_srcs or set())
    for name in names:
        candidates: list[tuple[int, int, str, Path, dict | None]] = []
        for entry in manifest_entries:
            rel = entry["src"]
            if rel in seen:
                continue
            score = _manifest_match_score(name, entry)
            if score <= 0:
                continue
            candidates.append((score, int(entry.get("priority") or 0), rel, entry["_file"], entry))
        for rel, f in all_files:
            if rel in seen:
                continue
            if any(entry["src"] == rel for entry in manifest_entries):
                continue
            score = _image_match_score(name, rel, f.stem)
            if score <= 0:
                continue
            candidates.append((score, 0, rel, f, None))
        candidates.sort(key=lambda t: (-t[0], -t[1], len(t[2]), t[2]))
        for _score, _priority, rel, f, entry in candidates:
            seen.add(rel)
            academy = name
            if entry and entry.get("academy"):
                academy = entry["academy"][0]
            out.append(
                {
                    "src": rel,
                    "caption": (entry or {}).get("caption") or f.stem,
                    "academy": academy,
                    "kind": "academy",
                    "page": None,
                    "tags": (entry or {}).get("tags") or [],
                    "priority": int((entry or {}).get("priority") or 0),
                    "source": (entry or {}).get("source") or _source_from_rel(rel),
                }
            )
            if len(out) >= max_total:
                return out
    return out

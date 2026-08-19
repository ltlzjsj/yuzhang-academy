"""Smoke test for MinerU pipeline backend.

Run: python D:/GeoRag/backend/scripts/test_mineru.py
Produces: D:/GeoRag/mineru_out/<stem>/auto/<stem>_content_list.json
Prints the first few block entries so we can lock in field names.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,::1,hf-mirror.com")

from mineru.cli.common import do_parse, read_fn  # noqa: E402

PDF = Path(r"D:/GeoRag/backend/uploads/kb_3/a4937d3c97b64b9988fac8741ab96b51.pdf")
OUT = Path(r"D:/GeoRag/mineru_out")


def main() -> int:
    if not PDF.exists():
        print(f"PDF not found: {PDF}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    stem = PDF.stem
    print(f"[1/3] reading {PDF.name} …")
    pdf_bytes = read_fn(PDF)

    print(f"[2/3] calling do_parse(backend=pipeline, lang=ch) → {OUT}")
    do_parse(
        output_dir=str(OUT),
        pdf_file_names=[stem],
        pdf_bytes_list=[pdf_bytes],
        p_lang_list=["ch"],
        backend="pipeline",
        parse_method="auto",
        formula_enable=True,
        table_enable=True,
        f_draw_layout_bbox=False,
        f_draw_span_bbox=False,
        f_dump_md=True,
        f_dump_middle_json=True,
        f_dump_model_output=False,
        f_dump_orig_pdf=False,
        f_dump_content_list=True,
        f_make_md_mode="mm_markdown",
    )

    cl_path = OUT / stem / "auto" / f"{stem}_content_list.json"
    print(f"[3/3] reading {cl_path}")
    if not cl_path.exists():
        # Fall back: search any depth
        matches = list(OUT.rglob(f"{stem}_content_list.json"))
        print(f"  direct path missing; glob hits: {matches}")
        if not matches:
            return 2
        cl_path = matches[0]

    data = json.loads(cl_path.read_text(encoding="utf-8"))
    print(f"  total blocks: {len(data)}")
    type_counts: dict[str, int] = {}
    for b in data:
        type_counts[b.get("type", "?")] = type_counts.get(b.get("type", "?"), 0) + 1
    print(f"  type histogram: {type_counts}")
    print("\n--- first 3 blocks (keys + samples) ---")
    for b in data[:3]:
        print(json.dumps(b, ensure_ascii=False, indent=2)[:800])
        print("---")
    return 0


if __name__ == "__main__":
    sys.exit(main())

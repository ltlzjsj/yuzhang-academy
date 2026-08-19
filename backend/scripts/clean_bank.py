"""清理题库中“指代外部材料”的不合格题目（题干含“根据材料/文中/上文”等，学生看不到材料）。

用法： python -m scripts.clean_bank          # 实删
       python -m scripts.clean_bank --dry    # 仅预览
"""
import sys

from sqlalchemy import create_engine, text

from app.core.config import settings

PHRASES = [
    "根据材料", "上述材料", "结合材料", "依据材料", "材料中", "材料一", "材料二", "材料所",
    "根据上述", "如上所述", "上文", "下文", "文中", "本文", "短文", "阅读材料", "根据以上",
    "根据短文", "结合上文", "结合下文", "如图",
]


def main() -> None:
    dry = "--dry" in sys.argv
    like = " OR ".join([f"question LIKE :p{i}" for i in range(len(PHRASES))])
    params = {f"p{i}": f"%{p}%" for i, p in enumerate(PHRASES)}
    engine = create_engine(settings.alembic_database_uri)
    with engine.begin() as conn:
        n = conn.execute(text(f"SELECT COUNT(*) FROM question_bank WHERE {like}"), params).scalar()
        print(f"matched {n} broken bank items")
        if not dry and n:
            conn.execute(text(f"DELETE FROM question_bank WHERE {like}"), params)
            print(f"deleted {n}")
        elif dry:
            for r in conn.execute(text(f"SELECT id, question FROM question_bank WHERE {like} LIMIT 10"), params):
                print("  -", r[0], str(r[1])[:60])


if __name__ == "__main__":
    main()

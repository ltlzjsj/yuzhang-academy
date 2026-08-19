"""把指定用户名设为管理员（role='admin'），可访问 /admin 管理后台。

用法：
    python -m scripts.set_admin <username>
    python scripts/set_admin.py <username>

不带参数时默认将用户名 'admin' 设为管理员。
"""
import sys

from sqlalchemy import create_engine, text

from app.core.config import settings


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    engine = create_engine(settings.alembic_database_uri)
    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE users SET role='admin' WHERE username=:u"),
            {"u": username},
        )
        rows = conn.execute(
            text("SELECT id, username, role FROM users WHERE username=:u"),
            {"u": username},
        ).fetchall()
    if not rows:
        print(f"[!] 未找到用户 '{username}'，请先注册该账号后再运行。")
        return
    print(f"[ok] updated={result.rowcount}; {[tuple(r) for r in rows]}")


if __name__ == "__main__":
    main()

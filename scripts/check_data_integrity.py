"""Basic integrity checks for SQLite and vector store files."""

from pathlib import Path
import sqlite3
import sys

DB_PATH = Path("./data/healthbuddy.db")
CHROMA_DB = Path("./data/chroma_db/chroma.sqlite3")


def check_sqlite(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing: {path}"
    conn = sqlite3.connect(path)
    try:
        result = conn.execute("PRAGMA integrity_check;").fetchone()
        if result and result[0] == "ok":
            return True, "ok"
        return False, str(result)
    finally:
        conn.close()


def main() -> int:
    checks = []
    checks.append(("app_db",) + check_sqlite(DB_PATH))
    checks.append(("chroma_db",) + check_sqlite(CHROMA_DB))

    has_errors = False
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")
        if not ok:
            has_errors = True

    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())

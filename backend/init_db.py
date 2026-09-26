"""Create a fresh exercise database from the application schema."""

import argparse
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent / "data" / "app.sqlite3"


def initialize(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with db_path.open("xb"):
        pass
    try:
        with sqlite3.connect(db_path) as db:
            db.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA busy_timeout = 30000")
    except Exception:
        db_path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    try:
        initialize(args.db)
    except (OSError, sqlite3.Error) as error:
        parser.exit(1, f"Could not initialize database: {error}\n")
    print(f"Created {args.db.resolve()} from schema.sql (no rows seeded).")
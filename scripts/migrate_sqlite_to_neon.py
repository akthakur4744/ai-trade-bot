"""One-shot data copy: local SQLite -> Neon Postgres.

Usage:
  # Paper
  python scripts/migrate_sqlite_to_neon.py \
      --source sqlite:///insight_alpha_paper.db \
      --target "$DATABASE_URL_PAPER"

  # Live (usually empty — safe to skip if no real-money history yet)
  python scripts/migrate_sqlite_to_neon.py \
      --source sqlite:///insight_alpha_live.db \
      --target "$DATABASE_URL_LIVE"

Assumes `alembic upgrade head` has already been run against the target.
Copies every row of every ORM-declared table, preserving primary keys.
Skips rows whose PK already exists in the target (idempotent re-run).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python scripts/...` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from src.storage.models import Base


def copy_table(src: Session, dst: Session, table) -> tuple[int, int]:
    """Copy rows for one table. Returns (copied, skipped)."""
    pk_cols = [c for c in table.primary_key.columns]
    copied = skipped = 0

    existing_pks: set = set()
    if pk_cols:
        rows = dst.execute(select(*pk_cols)).all()
        existing_pks = {tuple(r) for r in rows}

    for row in src.execute(select(table)).mappings():
        pk_tuple = tuple(row[c.name] for c in pk_cols)
        if pk_tuple in existing_pks:
            skipped += 1
            continue
        dst.execute(table.insert().values(**dict(row)))
        copied += 1

    dst.commit()
    return copied, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="SQLAlchemy URL of source (usually sqlite:///...)")
    ap.add_argument("--target", required=True, help="SQLAlchemy URL of target (Neon Postgres)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src_engine = create_engine(args.source)
    dst_engine = create_engine(args.target)

    src_tables = set(inspect(src_engine).get_table_names())
    dst_tables = set(inspect(dst_engine).get_table_names())

    # Ordered by FK dependencies (signals before trades).
    ordered = [t for t in Base.metadata.sorted_tables if t.name in src_tables]
    missing_in_target = [t.name for t in ordered if t.name not in dst_tables]
    if missing_in_target:
        print(f"ERROR: target missing tables: {missing_in_target}")
        print("Run `alembic upgrade head` against the target first.")
        return 2

    print(f"Source tables present: {sorted(t.name for t in ordered)}")
    if args.dry_run:
        return 0

    with Session(src_engine) as src, Session(dst_engine) as dst:
        for table in ordered:
            c, s = copy_table(src, dst, table)
            print(f"  {table.name}: copied={c} skipped={s}")

    print("Done. Spot-check counts with: SELECT count(*) FROM <table>;")
    return 0


if __name__ == "__main__":
    sys.exit(main())

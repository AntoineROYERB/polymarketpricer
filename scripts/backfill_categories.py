"""Backfill mapped_category for all existing markets in the database.

Usage:
    python scripts/backfill_categories.py          # Live mode — updates DB
    python scripts/backfill_categories.py --dry-run # Preview only
"""

import argparse
import os
import sys

from sqlalchemy import create_engine, text

sys.path.insert(0, ".")

from magic.default_repo.utils.category_classifier import infer_category

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://app:devpassword@localhost:5432/polymarket",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill market categories")
    parser.add_argument("--dry-run", action="store_true", help="Print counts without updating")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, question, category, mapped_category FROM markets ORDER BY id")
        ).fetchall()

    total = len(rows)
    already = sum(1 for r in rows if r.mapped_category is not None)
    to_classify = [r for r in rows if r.mapped_category is None]

    print(f"Total markets: {total}")
    print(f"Already classified: {already}")
    print(f"To classify: {len(to_classify)}")

    updates: list[tuple[str, str | None]] = []
    category_counts: dict[str, int] = {}
    unclassified = 0

    for row in to_classify:
        cat = infer_category(
            question=row.question or "",
            raw_category=row.category,
        )
        updates.append((row.id, cat))
        if cat:
            category_counts[cat] = category_counts.get(cat, 0) + 1
        else:
            unclassified += 1

    print(f"\nCategory distribution ({sum(category_counts.values())} classified):")
    for cat, cnt in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {cnt}")
    print(f"  (unclassified): {unclassified}")

    if args.dry_run:
        print(f"\nDry-run mode: {len(updates)} updates would be applied")
        return

    with engine.begin() as conn:
        for market_id, cat in updates:
            conn.execute(
                text("UPDATE markets SET mapped_category = :cat WHERE id = :id"),
                {"cat": cat, "id": market_id},
            )

    print(f"\nUpdated {len(updates)} markets")
    engine.dispose()


if __name__ == "__main__":
    main()

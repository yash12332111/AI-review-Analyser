"""
CLI entry point for embedding operations.

Usage:
  python -m app.embed --backfill      # Embed all classified, non-skipped records not yet in ChromaDB
  python -m app.embed --count         # Print how many records are in ChromaDB
"""
from __future__ import annotations

import argparse
import logging
import sys

from app.config.settings import settings
from app.database.db_manager import DatabaseManager
from app.embeddings.embed_pipeline import EmbeddingPipeline

# Setup basic logging to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Spotify Feedback Embedding Pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--backfill",
        action="store_true",
        help="Embed all classified, non-skipped records not yet in ChromaDB",
    )
    group.add_argument(
        "--count",
        action="store_true",
        help="Print how many records are in ChromaDB",
    )
    args = parser.parse_args()

    if args.count:
        ep = EmbeddingPipeline()
        count = ep.get_collection_count()
        print(f"📦 ChromaDB collection 'feedback': {count} documents")
        return

    if args.backfill:
        _run_backfill()


def _run_backfill() -> None:
    """Embed all classified, non-skipped feedback not already in ChromaDB."""
    db = DatabaseManager(settings.SQLITE_DB_PATH)
    db.initialize()
    ep = EmbeddingPipeline()

    # Get IDs already in ChromaDB
    existing_ids = ep.get_embedded_ids()
    logger.info(f"ChromaDB currently has {len(existing_ids)} documents.")

    # Fetch classified feedback excluding already-embedded
    records = db.get_classified_feedback(limit=10000, exclude_ids=existing_ids)
    logger.info(f"Found {len(records)} classified records to embed.")

    if not records:
        print("✅ All classified records are already embedded. Nothing to do.")
        db.close()
        return

    # Embed and store
    embedded = ep.embed_and_store(records)
    final_count = ep.get_collection_count()

    # Verify against SQLite
    classified_count = db.conn.execute(
        "SELECT COUNT(*) as cnt FROM feedback WHERE classified_at IS NOT NULL AND skipped = 0"
    ).fetchone()["cnt"]

    print(f"\n📊 Embedding Backfill Complete:")
    print(f"  New records embedded:   {embedded}")
    print(f"  ChromaDB total:         {final_count}")
    print(f"  SQLite classified:      {classified_count}")

    if final_count == classified_count:
        print(f"  ✅ Counts match — all classified records are embedded.")
    elif final_count < classified_count:
        diff = classified_count - final_count
        print(f"  ⚠️  {diff} classified records not in ChromaDB (likely < 30 chars — too short for embedding)")
    else:
        print(f"  ⚠️  ChromaDB has {final_count - classified_count} more than SQLite — possible stale embeddings")

    db.close()


if __name__ == "__main__":
    main()

"""
CLI entry point for classification.

Usage:
  python -m app.classify --batch-size 50
  python -m app.classify --all
"""
import argparse
import asyncio
import logging

from app.config.settings import settings
from app.database.db_manager import DatabaseManager
from app.classifier.engine import ClassificationEngine

# Setup basic logging to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    parser = argparse.ArgumentParser(description="Spotify Feedback Classifier")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--batch-size", type=int,
        help="Classify up to N unclassified records"
    )
    group.add_argument(
        "--all", action="store_true",
        help="Classify all unclassified records (up to daily cap)"
    )

    args = parser.parse_args()

    # Initialize DB and engine
    db = DatabaseManager(settings.SQLITE_DB_PATH)
    db.initialize()
    engine = ClassificationEngine(db)

    batch_size = args.batch_size if args.batch_size else settings.MAX_CLASSIFICATIONS_PER_RUN

    print(f"🧠 Starting classification (batch_size={batch_size})...")
    classified = await engine.classify_batch(batch_size=batch_size)
    print(f"\n✅ Classification complete: {classified} records classified")

    # Show summary
    cursor = db.conn.execute("SELECT COUNT(*) as total FROM feedback")
    total = cursor.fetchone()["total"]
    cursor = db.conn.execute("SELECT COUNT(*) as classified FROM feedback WHERE classified_at IS NOT NULL")
    total_classified = cursor.fetchone()["classified"]
    cursor = db.conn.execute("SELECT COUNT(*) as unclassified FROM feedback WHERE classified_at IS NULL")
    remaining = cursor.fetchone()["unclassified"]

    print(f"\n📊 Database Summary:")
    print(f"  Total records:       {total}")
    print(f"  Classified:          {total_classified}")
    print(f"  Remaining:           {remaining}")

    db.close()


if __name__ == "__main__":
    asyncio.run(main())

"""
CLI entry point for data collection.

Usage:
  python -m app.collect --all
  python -m app.collect --source appstore
"""
import argparse
import asyncio
import logging
from pprint import pprint

from app.config.settings import settings
from app.database.db_manager import DatabaseManager
from app.collectors.orchestrator import CollectionOrchestrator

# Setup basic logging to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    parser = argparse.ArgumentParser(description="Spotify Feedback Collector")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Run all collectors")
    group.add_argument(
        "--source", 
        choices=["appstore", "playstore", "spotify_community", "trustpilot"],
        help="Run a specific collector"
    )

    args = parser.parse_args()

    # Initialize DB
    db = DatabaseManager(settings.SQLITE_DB_PATH)
    # Ensure tables exist (just in case this is run before the web app starts)
    db.initialize()
    
    orchestrator = CollectionOrchestrator(db)

    print(f"🚀 Starting collection process...")
    
    if args.all:
        results = await orchestrator.run_all()
        print("\n📊 Collection Summary:")
        for source, log in results.items():
            print(f"  - {source}: {log.status} ({log.records_new} new out of {log.records_fetched} fetched)")
    else:
        result = await orchestrator.run_source(args.source)
        print(f"\n📊 Collection Summary ({args.source}):")
        print(f"  Status: {result.status}")
        print(f"  Fetched: {result.records_fetched}")
        print(f"  New (Inserted): {result.records_new}")
        if result.error_message:
            print(f"  Error: {result.error_message}")
            
    db.close()


if __name__ == "__main__":
    asyncio.run(main())

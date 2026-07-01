"""
Collection Orchestrator — manages concurrent execution of all collectors.
"""
import asyncio
import logging
from typing import Dict

from app.database.db_manager import DatabaseManager
from app.models.feedback import CollectionRunLog
from app.collectors.appstore_collector import AppStoreCollector
from app.collectors.playstore_collector import PlayStoreCollector
from app.collectors.spotify_community_collector import SpotifyCommunityCollector
from app.collectors.trustpilot_collector import TrustpilotCollector

logger = logging.getLogger(__name__)


class CollectionOrchestrator:
    def __init__(self, db: DatabaseManager):
        self.db = db
        # Initialize all 4 compliant collectors
        self.collectors = [
            AppStoreCollector(db),
            PlayStoreCollector(db),
            SpotifyCommunityCollector(db),
            TrustpilotCollector(db),
        ]

    async def run_all(self) -> Dict[str, CollectionRunLog]:
        """
        Run all 4 collectors concurrently using asyncio.gather.
        If a collector fails, it logs the error but doesn't stop the others.
        """
        logger.info("Starting concurrent collection across all sources...")
        
        # Create a task for each collector's run() method
        tasks = [collector.run() for collector in self.collectors]
        
        # return_exceptions=True isolates failures (Edge case #12)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        run_logs = {}
        for collector, result in zip(self.collectors, results):
            source = collector.source_name
            if isinstance(result, Exception):
                logger.error(f"[{source}] Unhandled collector exception: {result}")
                # Create a failed log entry since the collector crashed completely
                import datetime
                log = CollectionRunLog(
                    source=source,
                    started_at=datetime.datetime.utcnow(),
                    completed_at=datetime.datetime.utcnow(),
                    status="failed",
                    error_message=str(result)
                )
                self.db.log_collection_run(log)
                run_logs[source] = log
            else:
                run_logs[source] = result
                
        logger.info("Concurrent collection complete.")
        return run_logs

    async def run_source(self, source_name: str) -> CollectionRunLog:
        """Run a single collector by name."""
        target = next((c for c in self.collectors if c.source_name == source_name), None)
        if not target:
            raise ValueError(f"Unknown source: {source_name}")
            
        logger.info(f"Starting targeted collection for: {source_name}")
        return await target.run()

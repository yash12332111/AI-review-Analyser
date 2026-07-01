"""
AbstractCollector — base class for all data collectors.

Implements the full lifecycle:
1. Get last collection timestamp from DB
2. Call self.collect(since) to fetch raw data
3. Normalize each raw item into FeedbackRecord
4. Insert into DB (dedup handled by DB layer)
5. Log the run and return CollectionRunLog
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from app.config.settings import settings
from app.models.feedback import FeedbackRecord, CollectionRunLog
from app.database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class AbstractCollector(ABC):
    """Base class for all source-specific collectors."""

    source_name: str  # e.g., "appstore", "playstore"

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def run(self) -> CollectionRunLog:
        """
        Full lifecycle:
        1. Get last collection timestamp from DB
        2. Call self.collect(since) to fetch raw data (capped)
        3. Normalize each raw item into FeedbackRecord
        4. Insert into DB (dedup handled by DB layer)
        5. Log the run and return CollectionRunLog
        """
        started_at = datetime.utcnow()
        log = CollectionRunLog(
            source=self.source_name,
            started_at=started_at,
            status="running",
        )

        try:
            # 1. Get last collection time (default: 30 days back on first run)
            since = self.db.get_last_collection_time(self.source_name)
            if since is None:
                since = datetime.utcnow() - timedelta(days=30)
                logger.info(
                    f"[{self.source_name}] First run — looking back 30 days to {since.isoformat()}"
                )

            # 2. Fetch raw data
            raw_items = await self.collect(since)
            log.records_fetched = len(raw_items)
            logger.info(f"[{self.source_name}] Fetched {len(raw_items)} raw items")

            # 3 & 4. Normalize and insert
            new_count = 0
            for raw in raw_items:
                try:
                    record = self.normalize(raw)

                    # Edge case #6: filter out garbage/ultra-short reviews
                    if len(record.content.strip()) < 20:
                        continue

                    is_new = self.db.insert_feedback(record)
                    if is_new:
                        new_count += 1
                except Exception as e:
                    logger.warning(
                        f"[{self.source_name}] Failed to normalize/insert item: {e}"
                    )
                    continue

            log.records_new = new_count
            log.completed_at = datetime.utcnow()
            log.status = "success"
            logger.info(
                f"[{self.source_name}] Done — {new_count} new records inserted"
            )

        except Exception as e:
            log.completed_at = datetime.utcnow()
            log.status = "failed"
            log.error_message = str(e)
            logger.error(f"[{self.source_name}] Collection failed: {e}")

        # 5. Log the run
        self.db.log_collection_run(log)
        return log

    @abstractmethod
    async def collect(self, since: datetime) -> List[Dict]:
        """Fetch raw data from the source platform since the given timestamp."""

    @abstractmethod
    def normalize(self, raw: dict) -> FeedbackRecord:
        """Convert one source-specific raw dict into a unified FeedbackRecord."""

    @staticmethod
    def content_hash(content: str) -> str:
        """Compute a SHA-256 hash of normalized content for cross-platform dedup."""
        return hashlib.sha256(content.strip().lower().encode("utf-8")).hexdigest()

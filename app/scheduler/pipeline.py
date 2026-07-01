import logging
import time
from datetime import datetime, date, timedelta

from app.database.db_manager import DatabaseManager
from app.collectors.orchestrator import CollectionOrchestrator
from app.classifier.engine import ClassificationEngine
from app.embeddings.embed_pipeline import EmbeddingPipeline
from app.clustering.engine import ThemeClusteringEngine
from app.config.settings import settings

logger = logging.getLogger(__name__)

class NightlyPipeline:
    def __init__(self):
        self.db = DatabaseManager(settings.SQLITE_DB_PATH)
        self.orchestrator = CollectionOrchestrator(self.db)
        self.classifier = ClassificationEngine(self.db)
        self.embedding = EmbeddingPipeline()
        self.clustering = ThemeClusteringEngine(self.db, self.embedding)

    async def run(self) -> dict:
        """
        Execute the full pipeline:
        1. COLLECT
        2. CLASSIFY
        3. EMBED
        4. CLUSTER
        5. DELTA
        6. LOG
        """
        start_time = time.time()
        logger.info("Starting Nightly Pipeline")

        results = {
            "collect": {},
            "classify": {},
            "embed": {},
            "cluster": {},
            "delta": {},
            "errors": []
        }

        # 1. COLLECT
        logger.info("Pipeline Step 1: Collection")
        try:
            collect_results = await self.orchestrator.run_all()
            total_new = sum(log.records_new for log in collect_results.values() if log.status == "success")
            results["collect"] = {"total_new": total_new, "sources": {k: v.records_new for k, v in collect_results.items()}}
            logger.info(f"Collection complete: {total_new} new records")
        except Exception as e:
            logger.error(f"Collection failed: {e}")
            results["errors"].append(f"Collect: {str(e)}")

        # 2. CLASSIFY
        logger.info("Pipeline Step 2: Classification")
        try:
            classified_count = await self.classifier.classify_batch(batch_size=settings.MAX_CLASSIFICATIONS_PER_RUN)
            results["classify"] = {"count": classified_count}
            logger.info(f"Classification complete: {classified_count} records classified")
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            results["errors"].append(f"Classify: {str(e)}")

        # 3. EMBED
        logger.info("Pipeline Step 3: Embedding")
        try:
            existing_ids = self.embedding.get_embedded_ids()
            records = self.db.get_classified_feedback(limit=10000, exclude_ids=existing_ids)
            embed_count = self.embedding.embed_and_store(records)
            results["embed"] = {"count": embed_count}
            logger.info(f"Embedding complete: {embed_count} records embedded")
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            results["errors"].append(f"Embed: {str(e)}")

        # 4. CLUSTER
        logger.info("Pipeline Step 4: Clustering")
        try:
            cluster_results = self.clustering.run_clustering()
            results["cluster"] = {"status": cluster_results.get("status", "unknown"), "clusters_found": cluster_results.get("clusters_found", 0)}
            logger.info(f"Clustering complete: {cluster_results.get('clusters_found', 0)} clusters found")
        except Exception as e:
            logger.error(f"Clustering failed: {e}")
            results["errors"].append(f"Cluster: {str(e)}")

        # 5. DELTA
        logger.info("Pipeline Step 5: Delta Summary")
        try:
            delta_summary = await self.generate_delta_summary()
            self.db.insert_daily_summary(delta_summary)
            results["delta"] = {"status": "success"}
            logger.info("Delta summary complete")
        except Exception as e:
            logger.error(f"Delta summary failed: {e}")
            results["errors"].append(f"Delta: {str(e)}")

        end_time = time.time()
        duration = end_time - start_time
        results["duration_seconds"] = duration
        logger.info(f"Nightly Pipeline finished in {duration:.2f} seconds with {len(results['errors'])} errors")
        
        return results

    async def generate_delta_summary(self) -> dict:
        today = date.today()
        # Retrieve recent topic trends to compute delta
        trends = self.db.get_topic_trends(days=7)
        # Note: robust delta requires aggregating over days and comparing yesterday to avg.
        # This is a simplified version just creating the summary structure.
        
        # We can leverage db methods to build `by_source`, `by_topic`, etc.
        from app.models.feedback import DashboardFilters
        today_filter = DashboardFilters(date_from=today, date_to=today)
        summary_stats = self.db.get_summary_stats(today_filter)
        
        top_complaints = self.db.get_complaint_ranking(today_filter)
        
        summary = {
            "summary_date": today.isoformat(),
            "total_new": summary_stats.get("total_feedback", 0),
            "by_source": summary_stats.get("by_source", {}),
            "by_topic": self.db.get_topic_distribution(today_filter),
            "top_complaints": [c["core_complaint"] for c in top_complaints[:5]],
            "growing_patterns": [], # Computed based on 7-day average in a full implementation
            "fading_patterns": []
        }
        return summary

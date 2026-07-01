from __future__ import annotations
"""
FeedbackRetriever — unified retrieval layer for the dashboard and RAG chat.

Provides three retrieval modes:
  1. structured_query()  — SQL-based, for dashboard with exact filters
  2. semantic_search()   — Vector-based, for meaning-driven RAG queries
  3. hybrid_search()     — Merges both, deduplicates, and re-ranks

Design notes (Architecture.md §4.4 / implementation_plan.md Task 4.2):
- structured_query delegates to DatabaseManager.query_feedback()
- semantic_search converts ChatFilters → ChromaDB where clause, queries
  EmbeddingPipeline, then hydrates full ClassifiedFeedback from SQLite
- hybrid_search merges both result sets, deduplicates by feedback_id,
  and re-ranks by combined relevance
"""

import logging
from typing import Optional, List, Dict, Any

from app.database.db_manager import DatabaseManager
from app.embeddings.embed_pipeline import EmbeddingPipeline
from app.models.feedback import (
    ClassifiedFeedback,
    DashboardFilters,
    ChatFilters,
)

logger = logging.getLogger(__name__)


class FeedbackRetriever:
    """Unified retrieval layer for dashboard + RAG chat."""

    def __init__(self, db: DatabaseManager, embedding_pipeline: EmbeddingPipeline):
        self.db = db
        self.ep = embedding_pipeline

    # ------------------------------------------------------------------
    # SQL-based retrieval (Dashboard)
    # ------------------------------------------------------------------

    def structured_query(
        self,
        filters: DashboardFilters,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ClassifiedFeedback]:
        """SQL-based query for dashboard — fast, exact filters."""
        return self.db.query_feedback(filters, limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Vector-based retrieval (RAG Chat)
    # ------------------------------------------------------------------

    def semantic_search(
        self,
        query: str,
        filters: Optional[ChatFilters] = None,
        top_k: int = 20,
    ) -> List[ClassifiedFeedback]:
        """Semantic similarity search with optional metadata filtering.

        1. Convert ChatFilters into a ChromaDB where clause
        2. Run embedding_pipeline.query() with the where clause
        3. Fetch full ClassifiedFeedback from SQLite by IDs
        4. Return ranked results
        """
        where = self._build_chroma_filter(filters) if filters else None

        results = self.ep.query(text=query, n_results=top_k, where=where)

        if not results:
            logger.info("Semantic search returned 0 results.")
            return []

        # Hydrate full records from SQLite
        result_ids = [r["id"] for r in results]
        # Build a distance map for ranking
        distance_map = {r["id"]: r["distance"] for r in results}

        hydrated = self._hydrate_by_ids(result_ids)

        # Sort by distance (ascending = most similar first)
        hydrated.sort(key=lambda rec: distance_map.get(rec.id, 999.0))
        return hydrated

    # ------------------------------------------------------------------
    # Hybrid retrieval (combines both)
    # ------------------------------------------------------------------

    def hybrid_search(
        self,
        query: str,
        filters: Optional[ChatFilters] = None,
        top_k: int = 20,
    ) -> List[ClassifiedFeedback]:
        """Combine semantic + structured results, deduplicate, re-rank.

        1. Run semantic_search() for meaning-based results
        2. Run structured_query() for metadata-matched results
        3. Merge and deduplicate by feedback_id
        4. Return top_k results
        """
        # Semantic results
        semantic_results = self.semantic_search(query, filters, top_k=top_k)

        # Structured results (convert ChatFilters → DashboardFilters)
        dash_filters = DashboardFilters(
            source=filters.source if filters else None,
            sentiment=filters.sentiment if filters else None,
            topic=filters.topic if filters else None,
            date_from=filters.date_from if filters else None,
            date_to=filters.date_to if filters else None,
        )
        structured_results = self.structured_query(dash_filters, limit=top_k)

        # Merge and deduplicate — semantic results take priority
        seen_ids = set()
        merged: List[ClassifiedFeedback] = []

        for rec in semantic_results:
            if rec.id not in seen_ids:
                seen_ids.add(rec.id)
                merged.append(rec)

        for rec in structured_results:
            if rec.id not in seen_ids:
                seen_ids.add(rec.id)
                merged.append(rec)

        return merged[:top_k]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _hydrate_by_ids(self, ids: List[str]) -> List[ClassifiedFeedback]:
        """Fetch full ClassifiedFeedback records from SQLite by a list of IDs."""
        if not ids:
            return []

        placeholders = ",".join(["?"] * len(ids))
        query = f"""
            SELECT f.id, f.source, f.country, f.source_id, f.author, f.content,
                   f.url, f.posted_at, f.collected_at,
                   c.topic, c.core_complaint, c.trust_level, c.sentiment,
                   c.frustration_intensity, c.user_job_to_be_done,
                   c.repeat_listen_reason, c.workaround_mentioned,
                   c.workaround_description, c.behaviour_pattern,
                   c.pattern_evidence, c.unmet_need
            FROM feedback f
            JOIN classifications c ON f.id = c.feedback_id
            WHERE f.id IN ({placeholders})
        """
        from datetime import datetime

        rows = self.db.conn.execute(query, ids).fetchall()
        return [
            ClassifiedFeedback(
                id=row["id"],
                source=row["source"],
                country=row["country"],
                source_id=row["source_id"],
                author=row["author"],
                content=row["content"],
                url=row["url"],
                posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
                collected_at=datetime.fromisoformat(row["collected_at"]),
                topic=row["topic"],
                core_complaint=row["core_complaint"],
                trust_level=row["trust_level"],
                sentiment=row["sentiment"],
                frustration_intensity=row["frustration_intensity"],
                user_job_to_be_done=row["user_job_to_be_done"],
                repeat_listen_reason=row["repeat_listen_reason"],
                workaround_mentioned=bool(row["workaround_mentioned"]),
                workaround_description=row["workaround_description"],
                behaviour_pattern=row["behaviour_pattern"],
                pattern_evidence=row["pattern_evidence"],
                unmet_need=row["unmet_need"],
            )
            for row in rows
        ]

    @staticmethod
    def _build_chroma_filter(filters: ChatFilters) -> Optional[Dict[str, Any]]:
        """Convert ChatFilters into a ChromaDB-safe where clause.

        Returns None if no filters are applicable, or a dict like:
          {"$and": [{"source": "appstore"}, {"sentiment": "negative"}]}
        """
        conditions: List[Dict[str, Any]] = []

        if filters.source:
            conditions.append({"source": filters.source})
        if filters.sentiment:
            conditions.append({"sentiment": filters.sentiment})

        # Signal type shortcuts
        if filters.signal_type == "workarounds_only":
            conditions.append({"workaround_mentioned": True})
        elif filters.signal_type == "high_frustration_only":
            conditions.append({"frustration_intensity": "severe"})
        elif filters.signal_type == "churned_only":
            conditions.append({"frustration_intensity": "churned"})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

from __future__ import annotations
"""
DatabaseManager — wraps all SQLite interactions for the feedback system.

Provides CRUD operations for feedback, classifications, collection runs,
daily summaries, and dashboard queries. All table creation is driven by
schema.sql from Architecture.md Section 1.3.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.feedback import (
    FeedbackRecord,
    ClassificationResult,
    ClassifiedFeedback,
    CollectionRunLog,
    DashboardFilters,
)
from app.config.filters import build_discovery_sql_condition


class DatabaseManager:
    """SQLite database manager for the AI Feedback Intelligence System."""

    def __init__(self, db_path: str):
        """Initialize connection and create tables if they don't exist."""
        self.db_path = db_path
        # Ensure the parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def initialize(self) -> None:
        """Read schema.sql and execute all CREATE statements."""
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        self.conn.executescript(schema_sql)
        self.conn.commit()

    def insert_feedback(self, record: FeedbackRecord) -> bool:
        """INSERT OR IGNORE — returns True if new, False if duplicate."""
        cursor = self.conn.execute(
            """INSERT OR IGNORE INTO feedback
               (id, source, source_id, country, author, content, url,
                posted_at, collected_at, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id,
                record.source,
                record.source_id,
                record.country,
                record.author,
                record.content,
                record.url,
                record.posted_at.isoformat() if record.posted_at else None,
                record.collected_at.isoformat(),
                record.raw_json,
            ),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def insert_classification(self, result: ClassificationResult) -> None:
        """Store classification result, update feedback.classified_at."""
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO classifications
               (feedback_id, topic, core_complaint, trust_level, sentiment,
                frustration_intensity, user_job_to_be_done, repeat_listen_reason,
                workaround_mentioned, workaround_description, behaviour_pattern,
                pattern_evidence, quote_translated, unmet_need, classified_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.feedback_id,
                result.topic,
                result.core_complaint,
                result.trust_level,
                result.sentiment,
                result.frustration_intensity,
                result.user_job_to_be_done,
                result.repeat_listen_reason,
                1 if result.workaround_mentioned else 0,
                result.workaround_description,
                result.behaviour_pattern,
                result.pattern_evidence,
                result.quote_translated,
                result.unmet_need,
                now,
            ),
        )
        self.conn.execute(
            "UPDATE feedback SET classified_at = ? WHERE id = ?",
            (now, result.feedback_id),
        )
        self.conn.commit()

    def get_unclassified(self, limit: int = 50) -> list[FeedbackRecord]:
        """Return feedback records where classified_at IS NULL and skipped = 0."""
        rows = self.conn.execute(
            """SELECT id, source, source_id, country, author, content, url,
                      posted_at, collected_at, raw_json
               FROM feedback
               WHERE classified_at IS NULL
                 AND skipped = 0
               ORDER BY collected_at ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            FeedbackRecord(
                id=row["id"],
                source=row["source"],
                source_id=row["source_id"],
                country=row["country"],
                author=row["author"],
                content=row["content"],
                url=row["url"],
                posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
                collected_at=datetime.fromisoformat(row["collected_at"]),
                raw_json=row["raw_json"],
            )
            for row in rows
        ]

    def mark_skipped(self, feedback_id: str) -> None:
        """Mark a review as skipped (off-topic / all-null). Retained for audit,
        excluded from clustering and future classification runs."""
        self.conn.execute(
            "UPDATE feedback SET skipped = 1 WHERE id = ?",
            (feedback_id,),
        )
        self.conn.commit()

    def get_classified_feedback(
        self, limit: int = 1000, exclude_ids: Optional[list] = None
    ) -> list:
        """Return classified, non-skipped feedback joined with classifications.

        Used by the embedding backfill to find records that need embedding.
        If exclude_ids is provided, those IDs are excluded (already in ChromaDB).
        """
        query = """
            SELECT f.id, f.source, f.country, f.source_id, f.author, f.content,
                   f.url, f.posted_at, f.collected_at,
                   c.topic, c.core_complaint, c.trust_level, c.sentiment,
                   c.frustration_intensity, c.user_job_to_be_done,
                   c.repeat_listen_reason, c.workaround_mentioned,
                   c.workaround_description, c.behaviour_pattern,
                   c.pattern_evidence, c.quote_translated, c.unmet_need
            FROM feedback f
            JOIN classifications c ON f.id = c.feedback_id
            WHERE f.classified_at IS NOT NULL
              AND f.skipped = 0
            ORDER BY f.collected_at ASC
            LIMIT ?
        """
        rows = self.conn.execute(query, (limit,)).fetchall()

        # Filter out already-embedded IDs in Python (simpler than building
        # a massive NOT IN clause for SQLite)
        exclude_set = set(exclude_ids) if exclude_ids else set()

        results = []
        for row in rows:
            if row["id"] in exclude_set:
                continue
            results.append(
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
                    quote_translated=row["quote_translated"],
                    unmet_need=row["unmet_need"],
                )
            )
        return results

    def get_last_collection_time(self, source: str) -> datetime | None:
        """Return the max completed_at from collection_runs for this source."""
        row = self.conn.execute(
            """SELECT MAX(completed_at) as last_time
               FROM collection_runs
               WHERE source = ? AND status = 'success'""",
            (source,),
        ).fetchone()
        if row and row["last_time"]:
            return datetime.fromisoformat(row["last_time"])
        return None

    def log_collection_run(self, log: CollectionRunLog) -> int:
        """Insert a collection run log entry, return the run ID."""
        cursor = self.conn.execute(
            """INSERT INTO collection_runs
               (source, started_at, completed_at, records_fetched, records_new,
                status, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                log.source,
                log.started_at.isoformat(),
                log.completed_at.isoformat() if log.completed_at else None,
                log.records_fetched,
                log.records_new,
                log.status,
                log.error_message,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def query_feedback(
        self,
        filters: DashboardFilters,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ClassifiedFeedback]:
        """Parameterized query joining feedback + classifications with filters."""
        query = """
            SELECT f.id, f.source, f.country, f.source_id, f.author, f.content,
                   f.url, f.posted_at, f.collected_at,
                   c.topic, c.core_complaint, c.trust_level, c.sentiment,
                   c.frustration_intensity, c.user_job_to_be_done,
                   c.repeat_listen_reason, c.workaround_mentioned,
                   c.workaround_description, c.behaviour_pattern,
                   c.pattern_evidence, c.quote_translated, c.unmet_need
            FROM feedback f
            JOIN classifications c ON f.id = c.feedback_id
            WHERE 1=1
        """
        params: list = []

        if filters.date_from:
            query += " AND f.posted_at >= ?"
            params.append(filters.date_from.isoformat())
        if filters.date_to:
            query += " AND f.posted_at <= ?"
            params.append(filters.date_to.isoformat())
        if filters.source:
            query += " AND f.source = ?"
            params.append(filters.source)
        if filters.country:
            query += " AND f.country = ?"
            params.append(filters.country)
        if filters.sentiment:
            query += " AND c.sentiment = ?"
            params.append(filters.sentiment)
        if filters.topic:
            query += " AND c.topic LIKE ?"
            params.append(f"%{filters.topic}%")
        if filters.discovery_filter:
            query += " AND " + build_discovery_sql_condition('c')

        query += " ORDER BY f.posted_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.conn.execute(query, params).fetchall()
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
                quote_translated=row["quote_translated"],
                unmet_need=row["unmet_need"],
            )
            for row in rows
        ]

    def get_sentiment_distribution(self, filters: DashboardFilters) -> dict[str, int]:
        """COUNT grouped by sentiment."""
        query = """
            SELECT c.sentiment, COUNT(*) as cnt
            FROM feedback f
            JOIN classifications c ON f.id = c.feedback_id
            WHERE 1=1
        """
        params: list = []
        if filters.date_from:
            query += " AND f.posted_at >= ?"
            params.append(filters.date_from.isoformat())
        if filters.date_to:
            query += " AND f.posted_at <= ?"
            params.append(filters.date_to.isoformat())
        if filters.source:
            query += " AND f.source = ?"
            params.append(filters.source)
        if filters.country:
            query += " AND f.country = ?"
            params.append(filters.country)
        if filters.discovery_filter:
            query += " AND " + build_discovery_sql_condition('c')
        query += " GROUP BY c.sentiment"

        rows = self.conn.execute(query, params).fetchall()
        return {row["sentiment"]: row["cnt"] for row in rows}

    def get_complaint_ranking(self, filters: DashboardFilters) -> list[dict]:
        """COUNT grouped by core_complaint, ordered DESC, with week-over-week delta."""
        query = """
            SELECT c.core_complaint, COUNT(*) as cnt
            FROM feedback f
            JOIN classifications c ON f.id = c.feedback_id
            WHERE c.core_complaint IS NOT NULL
        """
        params: list = []
        if filters.date_from:
            query += " AND f.posted_at >= ?"
            params.append(filters.date_from.isoformat())
        if filters.date_to:
            query += " AND f.posted_at <= ?"
            params.append(filters.date_to.isoformat())
        if filters.source:
            query += " AND f.source = ?"
            params.append(filters.source)
        if filters.country:
            query += " AND f.country = ?"
            params.append(filters.country)
        if filters.discovery_filter:
            query += " AND " + build_discovery_sql_condition('c')
        query += " GROUP BY c.core_complaint ORDER BY cnt DESC LIMIT 20"

        rows = self.conn.execute(query, params).fetchall()
        return [{"core_complaint": row["core_complaint"], "count": row["cnt"]} for row in rows]

    def get_topic_distribution(self, filters: DashboardFilters) -> dict[str, int]:
        """COUNT grouped by topic."""
        query = """
            SELECT c.topic, COUNT(*) as cnt
            FROM feedback f
            JOIN classifications c ON f.id = c.feedback_id
            WHERE c.topic IS NOT NULL
        """
        params: list = []
        if filters.date_from:
            query += " AND f.posted_at >= ?"
            params.append(filters.date_from.isoformat())
        if filters.date_to:
            query += " AND f.posted_at <= ?"
            params.append(filters.date_to.isoformat())
        if filters.source:
            query += " AND f.source = ?"
            params.append(filters.source)
        if filters.country:
            query += " AND f.country = ?"
            params.append(filters.country)
        if filters.discovery_filter:
            query += " AND " + build_discovery_sql_condition('c')
        query += " GROUP BY c.topic ORDER BY cnt DESC"

        rows = self.conn.execute(query, params).fetchall()
        return {row["topic"]: row["cnt"] for row in rows}

    def get_workarounds(
        self, filters: DashboardFilters, limit: int = 20
    ) -> list[ClassifiedFeedback]:
        """Return records where workaround_mentioned = 1."""
        query = """
            SELECT f.id, f.source, f.country, f.source_id, f.author, f.content,
                   f.url, f.posted_at, f.collected_at,
                   c.topic, c.core_complaint, c.trust_level, c.sentiment,
                   c.frustration_intensity, c.user_job_to_be_done,
                   c.repeat_listen_reason, c.workaround_mentioned,
                   c.workaround_description, c.behaviour_pattern,
                   c.pattern_evidence, c.quote_translated, c.unmet_need
            FROM feedback f
            JOIN classifications c ON f.id = c.feedback_id
            WHERE c.workaround_mentioned = 1
        """
        params: list = []
        if filters.date_from:
            query += " AND f.posted_at >= ?"
            params.append(filters.date_from.isoformat())
        if filters.date_to:
            query += " AND f.posted_at <= ?"
            params.append(filters.date_to.isoformat())
        if filters.source:
            query += " AND f.source = ?"
            params.append(filters.source)
        if filters.country:
            query += " AND f.country = ?"
            params.append(filters.country)
        if filters.discovery_filter:
            query += " AND " + build_discovery_sql_condition('c')
        query += " ORDER BY f.posted_at DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
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
                quote_translated=row["quote_translated"],
                unmet_need=row["unmet_need"],
            )
            for row in rows
        ]

    def get_topic_trends(self, days: int = 30) -> list[dict]:
        """Daily COUNT by topic for the last N days."""
        rows = self.conn.execute(
            """SELECT DATE(f.posted_at) as day, c.topic, COUNT(*) as cnt
               FROM feedback f
               JOIN classifications c ON f.id = c.feedback_id
               WHERE f.posted_at >= DATE('now', ?)
               GROUP BY day, c.topic
               ORDER BY day ASC""",
            (f"-{days} days",),
        ).fetchall()
        return [{"day": row["day"], "topic": row["topic"], "count": row["cnt"]} for row in rows]

    def get_summary_stats(self, filters: DashboardFilters) -> dict:
        """Total feedback, by source, by sentiment — high-level summary."""
        # Total count
        total_query = "SELECT COUNT(*) as cnt FROM feedback f JOIN classifications c ON f.id = c.feedback_id WHERE 1=1"
        params: list = []
        if filters.date_from:
            total_query += " AND f.posted_at >= ?"
            params.append(filters.date_from.isoformat())
        if filters.date_to:
            total_query += " AND f.posted_at <= ?"
            params.append(filters.date_to.isoformat())
        if filters.source:
            total_query += " AND f.source = ?"
            params.append(filters.source)
        if filters.country:
            total_query += " AND f.country = ?"
            params.append(filters.country)
        if filters.discovery_filter:
            total_query += " AND " + build_discovery_sql_condition('c')

        total = self.conn.execute(total_query, params).fetchone()["cnt"]

        # By source
        by_source = {}
        source_query = "SELECT f.source, COUNT(*) as cnt FROM feedback f JOIN classifications c ON f.id = c.feedback_id WHERE 1=1"
        source_params = []
        if filters.discovery_filter:
             source_query += " AND " + build_discovery_sql_condition('c')
        source_query += " GROUP BY f.source"
        
        source_rows = self.conn.execute(source_query, source_params).fetchall()
        for row in source_rows:
            by_source[row["source"]] = row["cnt"]

        # By sentiment
        sentiment_dist = self.get_sentiment_distribution(filters)

        return {
            "total_feedback": total,
            "by_source": by_source,
            "by_sentiment": sentiment_dist,
        }

    def insert_daily_summary(self, summary: dict) -> None:
        """Store the nightly delta summary."""
        self.conn.execute(
            """INSERT OR REPLACE INTO daily_summaries
               (summary_date, total_new, by_source, by_topic,
                top_complaints, growing_patterns, fading_patterns)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                summary["summary_date"],
                summary.get("total_new", 0),
                json.dumps(summary.get("by_source", {})),
                json.dumps(summary.get("by_topic", {})),
                json.dumps(summary.get("top_complaints", [])),
                json.dumps(summary.get("growing_patterns", [])),
                json.dumps(summary.get("fading_patterns", [])),
            ),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Phase 4.5 — Clustering support
    # ------------------------------------------------------------------

    def get_classified_count(self) -> int:
        """Return the number of classified, non-skipped reviews."""
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM feedback WHERE classified_at IS NOT NULL AND skipped = 0"
        ).fetchone()
        return row["cnt"]

    def get_field_values(self, field_name: str) -> list:
        """Return non-null values for a classification field with feedback_ids.

        Returns list of {"feedback_id": str, "value": str}.
        """
        # Validate field_name to prevent SQL injection
        allowed = {"topic", "core_complaint", "behaviour_pattern", "unmet_need"}
        if field_name not in allowed:
            raise ValueError(f"Invalid field: {field_name}. Allowed: {allowed}")

        query = f"""
            SELECT c.feedback_id, c.{field_name} as value
            FROM classifications c
            JOIN feedback f ON f.id = c.feedback_id
            WHERE c.{field_name} IS NOT NULL
              AND c.{field_name} != ''
              AND f.classified_at IS NOT NULL
              AND f.skipped = 0
        """
        rows = self.conn.execute(query).fetchall()
        return [{"feedback_id": row["feedback_id"], "value": row["value"]} for row in rows]

    def get_feedback_content(self, feedback_id: str) -> str:
        """Return the content text for a single feedback record."""
        row = self.conn.execute(
            "SELECT content FROM feedback WHERE id = ?", (feedback_id,)
        ).fetchone()
        return row["content"] if row else ""

    def get_feedback_meta(self, feedback_id: str) -> dict:
        """Return source and country for a feedback record."""
        row = self.conn.execute(
            "SELECT source, country FROM feedback WHERE id = ?", (feedback_id,)
        ).fetchone()
        if row:
            return {"source": row["source"], "country": row["country"] or "unknown"}
        return {}

    def log_clustering_run(self, run_data: dict) -> int:
        """Insert a clustering run log entry, return the run ID."""
        cursor = self.conn.execute(
            """INSERT INTO clustering_runs
               (status, cluster_types)
               VALUES (?, ?)""",
            (
                run_data.get("status", "running"),
                run_data.get("cluster_types", "[]"),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_clustering_run(self, run_id: int, data: dict) -> None:
        """Update a clustering run with final results."""
        self.conn.execute(
            """UPDATE clustering_runs
               SET completed_at = CURRENT_TIMESTAMP,
                   status = ?,
                   total_records = ?,
                   clusters_found = ?,
                   error_message = ?
               WHERE id = ?""",
            (
                data.get("status", "success"),
                data.get("total_records"),
                data.get("clusters_found"),
                data.get("error_message"),
                run_id,
            ),
        )
        self.conn.commit()

    def delete_clusters_by_type(self, cluster_type: str) -> int:
        """Delete existing clusters for a type (before re-clustering)."""
        cursor = self.conn.execute(
            "DELETE FROM theme_clusters WHERE cluster_type = ?",
            (cluster_type,),
        )
        self.conn.commit()
        return cursor.rowcount

    def insert_theme_clusters(
        self, clusters: list, run_id: int, cluster_type: str
    ) -> int:
        """Insert cluster records for a run. Returns count inserted."""
        for c in clusters:
            self.conn.execute(
                """INSERT INTO theme_clusters
                   (cluster_type, label, member_count, percentage,
                    representative_quotes, sources_breakdown,
                    countries_breakdown, member_ids, run_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cluster_type,
                    c.get("label", "unlabelled"),
                    c["member_count"],
                    c.get("percentage", 0.0),
                    json.dumps(c.get("representative_quotes", [])),
                    json.dumps(c.get("sources_breakdown", {})),
                    json.dumps(c.get("countries_breakdown", {})),
                    json.dumps(c.get("member_feedback_ids", [])),
                    run_id,
                ),
            )
        self.conn.commit()
        return len(clusters)

    def get_theme_clusters(self, cluster_type: str = None, filters: DashboardFilters = None) -> list:
        """Retrieve clusters, optionally filtered by type, source, and country."""
        if cluster_type:
            rows = self.conn.execute(
                "SELECT * FROM theme_clusters WHERE cluster_type = ? ORDER BY member_count DESC",
                (cluster_type,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM theme_clusters ORDER BY cluster_type, member_count DESC"
            ).fetchall()
            
        results = []
        for row in rows:
            c = dict(row)
            sources = json.loads(c["sources_breakdown"])
            countries = json.loads(c["countries_breakdown"])
            c["sources_breakdown"] = sources
            c["countries_breakdown"] = countries
            c["representative_quotes"] = json.loads(c["representative_quotes"])
            c["member_ids"] = json.loads(c["member_ids"])
            
            # Apply filters
            if filters:
                if filters.source and filters.source not in sources:
                    continue
                if filters.country and filters.country not in countries:
                    continue
                    
                # Adjust member_count based on filter (approximate if both are used)
                new_count = c["member_count"]
                if filters.source:
                    new_count = min(new_count, sources.get(filters.source, 0))
                if filters.country:
                    new_count = min(new_count, countries.get(filters.country, 0))
                
                c["member_count"] = new_count
                
                if new_count == 0:
                    continue
            results.append(c)
            
        # Re-sort if counts changed
        if filters:
            results.sort(key=lambda x: (x["cluster_type"], x["member_count"]), reverse=True)
            
        return results

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()


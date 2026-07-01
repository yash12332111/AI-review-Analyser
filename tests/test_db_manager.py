"""
Unit tests for DatabaseManager — Phase 1 acceptance tests.

Tests:
- test_initialize_creates_tables — verify all 6 tables exist after initialize()
- test_insert_feedback — insert a record, verify it's retrievable
- test_duplicate_feedback_ignored — insert same (source, source_id) twice, verify only 1 exists
- test_insert_classification — insert classification, verify join query works
- test_get_unclassified — insert 3 feedback records, classify 1, verify get_unclassified() returns 2
- test_filters — insert records with different sources/sentiments, verify filter queries
"""

import os
import tempfile
import pytest
from datetime import datetime

from app.database.db_manager import DatabaseManager
from app.models.feedback import (
    FeedbackRecord,
    ClassificationResult,
    DashboardFilters,
)


@pytest.fixture
def db():
    """Create a temporary database for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    manager = DatabaseManager(path)
    manager.initialize()
    yield manager
    manager.close()
    os.unlink(path)


def _make_feedback(
    source_id: str = "test-123",
    source: str = "appstore",
    content: str = "This is a test review",
    country: str = "US",
) -> FeedbackRecord:
    """Helper to create a FeedbackRecord with sensible defaults."""
    return FeedbackRecord(
        source=source,
        source_id=source_id,
        country=country,
        author="test_user",
        content=content,
        posted_at=datetime(2024, 1, 15, 12, 0, 0),
    )


def _make_classification(
    feedback_id: str,
    sentiment: str = "negative",
    topic: str = "Too many ads",
    core_complaint: str = "Excessive advertising",
) -> ClassificationResult:
    """Helper to create a ClassificationResult with sensible defaults."""
    return ClassificationResult(
        feedback_id=feedback_id,
        topic=topic,
        core_complaint=core_complaint,
        trust_level="low",
        sentiment=sentiment,
        frustration_intensity="moderate",
        user_job_to_be_done="Listen to music without interruptions",
        repeat_listen_reason=None,
        workaround_mentioned=False,
        workaround_description=None,
        behaviour_pattern=None,
        pattern_evidence=None,
        unmet_need="Ad-free listening experience",
    )


class TestInitialize:
    def test_initialize_creates_tables(self, db):
        """Verify all 6 tables exist after initialize()."""
        cursor = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        # Exclude SQLite internal tables (sqlite_sequence is created by AUTOINCREMENT)
        tables = [
            row["name"] for row in cursor.fetchall()
            if not row["name"].startswith("sqlite_")
        ]
        expected = [
            "classifications",
            "clustering_runs",
            "collection_runs",
            "daily_summaries",
            "feedback",
            "theme_clusters",
        ]
        assert sorted(tables) == sorted(expected), (
            f"Expected tables {expected}, got {sorted(tables)}"
        )


class TestInsertFeedback:
    def test_insert_feedback(self, db):
        """Insert a record, verify it's retrievable."""
        record = _make_feedback()
        result = db.insert_feedback(record)
        assert result is True, "First insert should return True (new record)"

        # Verify it's in the DB
        row = db.conn.execute(
            "SELECT * FROM feedback WHERE id = ?", (record.id,)
        ).fetchone()
        assert row is not None
        assert row["source"] == "appstore"
        assert row["content"] == "This is a test review"
        assert row["country"] == "US"

    def test_duplicate_feedback_ignored(self, db):
        """Insert same (source, source_id) twice, verify only 1 exists."""
        record1 = _make_feedback(source_id="dup-1")
        record2 = _make_feedback(source_id="dup-1")

        result1 = db.insert_feedback(record1)
        result2 = db.insert_feedback(record2)

        assert result1 is True, "First insert should succeed"
        assert result2 is False, "Duplicate insert should be ignored"

        count = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM feedback WHERE source_id = 'dup-1'"
        ).fetchone()["cnt"]
        assert count == 1


class TestClassification:
    def test_insert_classification(self, db):
        """Insert classification, verify join query works."""
        feedback = _make_feedback()
        db.insert_feedback(feedback)

        classification = _make_classification(feedback.id)
        db.insert_classification(classification)

        # Verify classification exists
        row = db.conn.execute(
            "SELECT * FROM classifications WHERE feedback_id = ?",
            (feedback.id,),
        ).fetchone()
        assert row is not None
        assert row["topic"] == "Too many ads"
        assert row["sentiment"] == "negative"
        assert row["unmet_need"] == "Ad-free listening experience"

        # Verify feedback.classified_at was updated
        fb_row = db.conn.execute(
            "SELECT classified_at FROM feedback WHERE id = ?",
            (feedback.id,),
        ).fetchone()
        assert fb_row["classified_at"] is not None

    def test_get_unclassified(self, db):
        """Insert 3 feedback records, classify 1, verify get_unclassified() returns 2."""
        records = [
            _make_feedback(source_id=f"unclass-{i}") for i in range(3)
        ]
        for r in records:
            db.insert_feedback(r)

        # Classify only the first one
        classification = _make_classification(records[0].id)
        db.insert_classification(classification)

        unclassified = db.get_unclassified()
        assert len(unclassified) == 2, (
            f"Expected 2 unclassified, got {len(unclassified)}"
        )
        unclass_ids = {r.id for r in unclassified}
        assert records[0].id not in unclass_ids, (
            "Classified record should not be in unclassified list"
        )


class TestFilters:
    def test_filters(self, db):
        """Insert records with different sources/sentiments, verify filter queries."""
        # Insert feedback from different sources
        fb_appstore = _make_feedback(source_id="filter-1", source="appstore")
        fb_playstore = _make_feedback(source_id="filter-2", source="playstore")
        fb_community = _make_feedback(source_id="filter-3", source="spotify_community")

        db.insert_feedback(fb_appstore)
        db.insert_feedback(fb_playstore)
        db.insert_feedback(fb_community)

        # Classify with different sentiments
        db.insert_classification(
            _make_classification(fb_appstore.id, sentiment="negative", topic="Ads")
        )
        db.insert_classification(
            _make_classification(fb_playstore.id, sentiment="positive", topic="Good UX")
        )
        db.insert_classification(
            _make_classification(fb_community.id, sentiment="negative", topic="Ads")
        )

        # Test source filter
        filters = DashboardFilters(source="appstore")
        results = db.query_feedback(filters)
        assert len(results) == 1
        assert results[0].source == "appstore"

        # Test sentiment distribution
        all_filters = DashboardFilters()
        sentiment = db.get_sentiment_distribution(all_filters)
        assert sentiment.get("negative", 0) == 2
        assert sentiment.get("positive", 0) == 1

        # Test topic distribution
        topics = db.get_topic_distribution(all_filters)
        assert topics.get("Ads", 0) == 2
        assert topics.get("Good UX", 0) == 1

        # Test summary stats
        stats = db.get_summary_stats(all_filters)
        assert stats["total_feedback"] == 3


class TestCollectionRuns:
    def test_log_collection_run(self, db):
        """Test logging a collection run and retrieving last collection time."""
        from app.models.feedback import CollectionRunLog

        log = CollectionRunLog(
            source="appstore",
            started_at=datetime(2024, 1, 15, 0, 0, 0),
            completed_at=datetime(2024, 1, 15, 0, 5, 0),
            records_fetched=50,
            records_new=10,
            status="success",
        )
        run_id = db.log_collection_run(log)
        assert run_id is not None
        assert run_id > 0

        # Verify last collection time
        last_time = db.get_last_collection_time("appstore")
        assert last_time is not None
        assert last_time.year == 2024

        # Verify no collection time for a source that hasn't run
        no_time = db.get_last_collection_time("playstore")
        assert no_time is None

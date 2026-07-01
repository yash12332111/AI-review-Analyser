"""
Tests for Phase 4 — EmbeddingPipeline and FeedbackRetriever.

Uses a temporary ChromaDB directory and SQLite database per test
to ensure isolation.
"""
from __future__ import annotations

import os
import tempfile
import shutil
from datetime import datetime
from typing import List

import pytest

from app.models.feedback import (
    FeedbackRecord,
    ClassificationResult,
    ClassifiedFeedback,
    DashboardFilters,
    ChatFilters,
)
from app.database.db_manager import DatabaseManager
from app.embeddings.embed_pipeline import EmbeddingPipeline
from app.retrieval.retriever import FeedbackRetriever


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dirs():
    """Create temporary directories for DB and ChromaDB."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    chroma_dir = os.path.join(tmp, "chroma")
    os.makedirs(chroma_dir, exist_ok=True)
    yield db_path, chroma_dir
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def db(tmp_dirs):
    """Create and initialize a test database."""
    db_path, _ = tmp_dirs
    mgr = DatabaseManager(db_path)
    mgr.initialize()
    return mgr


@pytest.fixture
def ep(tmp_dirs):
    """Create an EmbeddingPipeline with a temporary ChromaDB directory."""
    _, chroma_dir = tmp_dirs
    return EmbeddingPipeline(persist_dir=chroma_dir)


@pytest.fixture
def sample_records() -> List[ClassifiedFeedback]:
    """5 sample classified feedback records with varied content and metadata."""
    return [
        ClassifiedFeedback(
            id="rec-1",
            source="appstore",
            country="US",
            source_id="as-001",
            content="Discover Weekly keeps suggesting the same artists every single week, it's like the algorithm is stuck in a loop and never explores new genres for me.",
            collected_at=datetime(2026, 6, 15, 10, 0),
            topic="Discover Weekly repetition",
            core_complaint="algorithm stuck in a loop",
            sentiment="negative",
            frustration_intensity="severe",
            trust_level="low",
            behaviour_pattern="relies on algorithmic playlists but finds them repetitive",
            workaround_mentioned=False,
            unmet_need="User needs fresh genre exploration but the algorithm keeps recycling the same artists",
        ),
        ClassifiedFeedback(
            id="rec-2",
            source="playstore",
            country="IN",
            source_id="ps-002",
            content="I love how Spotify lets me create collaborative playlists with my friends. The social features are amazing and make music sharing so much fun.",
            collected_at=datetime(2026, 6, 15, 11, 0),
            topic="collaborative playlists",
            sentiment="positive",
            trust_level="high",
            behaviour_pattern="uses collaborative playlists for social music sharing",
            workaround_mentioned=False,
        ),
        ClassifiedFeedback(
            id="rec-3",
            source="appstore",
            country="GB",
            source_id="as-003",
            content="The shuffle feature is completely broken. I have a playlist with 500 songs and it keeps playing the same 20 over and over. I've started using a third-party app to randomize properly.",
            collected_at=datetime(2026, 6, 15, 12, 0),
            topic="shuffle broken",
            core_complaint="shuffle plays same songs repeatedly",
            sentiment="negative",
            frustration_intensity="severe",
            trust_level="broken",
            behaviour_pattern="uses third-party tools to work around broken shuffle",
            workaround_mentioned=True,
            workaround_description="uses a third-party app to randomize properly",
            unmet_need="User needs true random shuffle but the built-in shuffle repeats the same songs",
        ),
        ClassifiedFeedback(
            id="rec-4",
            source="playstore",
            country="DE",
            source_id="ps-004",
            content="Podcasts are decent but the app drains my battery like crazy. I have to charge my phone twice a day when listening to long podcasts during work.",
            collected_at=datetime(2026, 6, 15, 13, 0),
            topic="battery drain during podcasts",
            core_complaint="excessive battery consumption",
            sentiment="mixed",
            frustration_intensity="moderate",
            trust_level="medium",
            behaviour_pattern="listens to long podcasts during work",
            workaround_mentioned=False,
            unmet_need="User needs to listen to podcasts without excessive battery drain",
        ),
        ClassifiedFeedback(
            id="rec-5",
            source="appstore",
            country="BR",
            source_id="as-005",
            content="Best music app ever created. The audio quality is superb and the library is massive. Premium is absolutely worth it.",
            collected_at=datetime(2026, 6, 15, 14, 0),
            topic="audio quality praise",
            sentiment="positive",
            trust_level="high",
            behaviour_pattern="premium subscriber focused on audio quality",
            workaround_mentioned=False,
        ),
    ]


def _insert_samples(db: DatabaseManager, records: List[ClassifiedFeedback]) -> None:
    """Insert sample records into both feedback and classifications tables."""
    for rec in records:
        fb = FeedbackRecord(
            id=rec.id,
            source=rec.source,
            country=rec.country,
            source_id=rec.source_id,
            author=rec.author,
            content=rec.content,
            url=rec.url,
            posted_at=rec.posted_at,
            collected_at=rec.collected_at,
        )
        db.insert_feedback(fb)
        cls = ClassificationResult(
            feedback_id=rec.id,
            topic=rec.topic,
            core_complaint=rec.core_complaint,
            trust_level=rec.trust_level,
            sentiment=rec.sentiment or "neutral",
            frustration_intensity=rec.frustration_intensity,
            user_job_to_be_done=rec.user_job_to_be_done,
            repeat_listen_reason=rec.repeat_listen_reason,
            workaround_mentioned=rec.workaround_mentioned,
            workaround_description=rec.workaround_description,
            behaviour_pattern=rec.behaviour_pattern,
            pattern_evidence=rec.pattern_evidence,
            unmet_need=rec.unmet_need,
        )
        db.insert_classification(cls)


# ──────────────────────────────────────────────────────────────────
# EmbeddingPipeline tests
# ──────────────────────────────────────────────────────────────────

class TestEmbeddingPipeline:
    """Tests for app/embeddings/embed_pipeline.py."""

    def test_embed_and_retrieve(self, ep, sample_records):
        """Embed 5 records, query for similar, verify results."""
        embedded = ep.embed_and_store(sample_records)
        assert embedded == 5
        assert ep.get_collection_count() == 5

        # Query for something similar to record 1
        results = ep.query("algorithm recommendations stuck repeating")
        assert len(results) > 0

        # The top result should be about Discover Weekly / shuffle
        top_ids = [r["id"] for r in results[:3]]
        assert "rec-1" in top_ids or "rec-3" in top_ids, (
            f"Expected rec-1 or rec-3 in top results, got {top_ids}"
        )

    def test_metadata_filtering(self, ep, sample_records):
        """Embed records, filter by sentiment."""
        ep.embed_and_store(sample_records)

        # Only negative reviews
        results = ep.query(
            "problems with the app",
            where={"sentiment": "negative"},
        )

        for r in results:
            assert r["metadata"]["sentiment"] == "negative"

    def test_upsert_idempotent(self, ep, sample_records):
        """Running embed_and_store twice should not create duplicates."""
        ep.embed_and_store(sample_records)
        assert ep.get_collection_count() == 5

        # Re-run — should upsert, not duplicate
        ep.embed_and_store(sample_records)
        assert ep.get_collection_count() == 5

    def test_short_content_skipped(self, ep):
        """Content shorter than 30 chars should not be embedded."""
        short = ClassifiedFeedback(
            id="short-1",
            source="appstore",
            source_id="short-001",
            content="bad app",  # 7 chars — below threshold
            collected_at=datetime(2026, 6, 15),
            sentiment="negative",
        )
        embedded = ep.embed_and_store([short])
        assert embedded == 0
        assert ep.get_collection_count() == 0

    def test_none_metadata_handled(self, ep):
        """Records with None in optional fields should embed without error."""
        rec = ClassifiedFeedback(
            id="none-1",
            source="appstore",
            source_id="none-001",
            content="This is a review with many null classification fields but enough text.",
            collected_at=datetime(2026, 6, 15),
            sentiment="neutral",
            # Everything else is None
        )
        embedded = ep.embed_and_store([rec])
        assert embedded == 1

        results = ep.query("null fields")
        assert len(results) == 1
        # Verify None was converted to "" not passed as None
        meta = results[0]["metadata"]
        assert meta["topic"] == ""
        assert meta["core_complaint"] == ""


# ──────────────────────────────────────────────────────────────────
# FeedbackRetriever tests
# ──────────────────────────────────────────────────────────────────

class TestFeedbackRetriever:
    """Tests for app/retrieval/retriever.py."""

    def test_structured_query(self, db, ep, sample_records):
        """Structured query returns results filtered by source."""
        _insert_samples(db, sample_records)
        retriever = FeedbackRetriever(db, ep)

        results = retriever.structured_query(
            DashboardFilters(source="appstore")
        )
        assert all(r.source == "appstore" for r in results)
        assert len(results) == 3  # rec-1, rec-3, rec-5

    def test_semantic_search(self, db, ep, sample_records):
        """Semantic search returns relevant results."""
        _insert_samples(db, sample_records)
        ep.embed_and_store(sample_records)
        retriever = FeedbackRetriever(db, ep)

        results = retriever.semantic_search(
            "shuffle keeps repeating same songs"
        )
        assert len(results) > 0
        # rec-3 (shuffle broken) should be in top results
        top_ids = [r.id for r in results[:3]]
        assert "rec-3" in top_ids, f"Expected rec-3 in top results, got {top_ids}"

    def test_hybrid_search_merges_results(self, db, ep, sample_records):
        """Hybrid search combines vector + SQL results without duplicates."""
        _insert_samples(db, sample_records)
        ep.embed_and_store(sample_records)
        retriever = FeedbackRetriever(db, ep)

        results = retriever.hybrid_search(
            "broken shuffle feature",
            filters=ChatFilters(sentiment="negative"),
        )
        # Should have no duplicate IDs
        ids = [r.id for r in results]
        assert len(ids) == len(set(ids)), "Hybrid search returned duplicates"

    def test_semantic_search_with_filter(self, db, ep, sample_records):
        """Semantic search with metadata filter narrows results."""
        _insert_samples(db, sample_records)
        ep.embed_and_store(sample_records)
        retriever = FeedbackRetriever(db, ep)

        results = retriever.semantic_search(
            "music quality",
            filters=ChatFilters(sentiment="positive"),
        )
        for r in results:
            assert r.sentiment == "positive"

    def test_empty_results_handled(self, db, ep, sample_records):
        """Query with impossible filters returns empty list, not error."""
        _insert_samples(db, sample_records)
        ep.embed_and_store(sample_records)
        retriever = FeedbackRetriever(db, ep)

        # No trustpilot reviews in sample data
        results = retriever.semantic_search(
            "anything",
            filters=ChatFilters(source="trustpilot"),
        )
        assert results == []


# ──────────────────────────────────────────────────────────────────
# Backfill-specific tests
# ──────────────────────────────────────────────────────────────────

class TestBackfill:
    """Tests for the backfill workflow (db → embed pipeline)."""

    def test_get_classified_feedback(self, db, sample_records):
        """DB method returns only classified, non-skipped records."""
        _insert_samples(db, sample_records)
        records = db.get_classified_feedback()
        assert len(records) == 5

    def test_get_classified_excludes_skipped(self, db, sample_records):
        """Skipped records are excluded from backfill query."""
        _insert_samples(db, sample_records)
        db.mark_skipped("rec-2")
        records = db.get_classified_feedback()
        ids = [r.id for r in records]
        assert "rec-2" not in ids
        assert len(records) == 4

    def test_backfill_excludes_existing(self, db, ep, sample_records):
        """Backfill skips records already in ChromaDB."""
        _insert_samples(db, sample_records)

        # Embed first 3
        ep.embed_and_store(sample_records[:3])
        assert ep.get_collection_count() == 3

        # Get records to backfill, excluding already-embedded
        existing = ep.get_embedded_ids()
        to_embed = db.get_classified_feedback(exclude_ids=existing)
        assert len(to_embed) == 2  # rec-4 and rec-5

        ep.embed_and_store(to_embed)
        assert ep.get_collection_count() == 5

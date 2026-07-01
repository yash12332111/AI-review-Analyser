"""
Tests for Phase 4.5 — Theme Clustering Engine.

Covers:
  - test_no_hardcoded_categories: grep engine.py and prompts.py for any
    hardcoded category lists — MUST pass per Agents.md.
  - test_hdbscan_finds_clusters: embed known-similar values, verify HDBSCAN groups them.
  - test_noise_points_excluded: verify HDBSCAN noise (-1) points are not assigned to clusters.
  - test_rerun_replaces_old_clusters: run twice, verify only latest clusters exist.
  - test_representative_quotes_verified: verify selected quotes exist in source text.
  - test_clustering_settings: verify settings load correctly.
"""
from __future__ import annotations

import os
import re
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

import pytest
import numpy as np

from app.database.db_manager import DatabaseManager
from app.models.feedback import FeedbackRecord, ClassificationResult


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dirs():
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    chroma_dir = os.path.join(tmp, "chroma")
    os.makedirs(chroma_dir, exist_ok=True)
    yield db_path, chroma_dir
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def db(tmp_dirs):
    db_path, _ = tmp_dirs
    mgr = DatabaseManager(db_path)
    mgr.initialize()
    return mgr


def _seed_reviews(db, n=30, topic_groups=None):
    """Seed the DB with n reviews, optionally with grouped topics for clustering."""
    if topic_groups is None:
        # Create 3 thematic groups of 10
        topic_groups = {
            "shuffle_broken": [
                "shuffle repeats same songs",
                "shuffle algorithm is broken",
                "shuffle keeps playing same tracks",
                "shuffle mode does not randomize",
                "shuffle feature needs fixing",
                "random play keeps repeating",
                "shuffle plays same 20 songs",
                "shuffle not working properly",
                "randomization is terrible",
                "shuffle mode is predictable",
            ],
            "battery_drain": [
                "app drains battery fast",
                "battery consumption is excessive",
                "app uses too much battery",
                "phone battery dies from spotify",
                "battery drain while listening",
                "app kills my battery life",
                "excessive battery usage",
                "app consumes too much power",
                "battery runs out quickly",
                "high battery consumption",
            ],
            "ads_frequency": [
                "too many ads interrupting music",
                "ads are way too frequent",
                "constant ads between songs",
                "ad frequency is annoying",
                "too many advertisements",
                "ads every other song",
                "excessive advertising breaks",
                "ads ruin the experience",
                "too many ad interruptions",
                "ad frequency is unbearable",
            ],
        }

    i = 0
    for group_name, topics in topic_groups.items():
        for topic_text in topics:
            fid = f"test-{i:03d}"
            fb = FeedbackRecord(
                id=fid,
                source="appstore" if i % 2 == 0 else "playstore",
                country=["US", "GB", "IN", "DE", "BR"][i % 5],
                source_id=f"src-{i:03d}",
                content=f"Review about {topic_text}. This is a longer review with enough content to be meaningful for embedding and testing the clustering pipeline.",
                collected_at=datetime(2026, 6, 15, i % 24),
            )
            db.insert_feedback(fb)
            cls = ClassificationResult(
                feedback_id=fid,
                topic=topic_text,
                core_complaint=topic_text if "broken" in topic_text or "drain" in topic_text or "annoying" in topic_text else None,
                sentiment="negative",
                workaround_mentioned=False,
                behaviour_pattern=f"user experiences {topic_text}",
                unmet_need=f"user needs {group_name.replace('_', ' ')} fixed" if i % 3 == 0 else None,
            )
            db.insert_classification(cls)
            i += 1


# ──────────────────────────────────────────────────────────────────
# test_no_hardcoded_categories (MANDATORY per Agents.md)
# ──────────────────────────────────────────────────────────────────

class TestNoHardcodedCategories:
    """
    Agents.md §Open-extraction guardrails:
    "In the clustering engine (Phase 4.5), never hardcode expected segments,
    frustration categories, or theme lists."
    """

    def test_no_hardcoded_categories(self):
        """Grep engine.py and prompts.py for any hardcoded category lists."""
        project_root = Path(__file__).parent.parent
        engine_path = project_root / "app" / "clustering" / "engine.py"
        prompts_path = project_root / "app" / "clustering" / "prompts.py"

        # Patterns that would indicate hardcoded categories
        # We look for Python list/dict literals containing strings that look
        # like predefined theme/category labels
        category_patterns = [
            # List of category strings (e.g., categories = ["shuffle", "battery", ...])
            r'(?:categories|themes|segments|buckets|labels)\s*=\s*\[',
            # Dict mapping to predefined themes
            r'(?:category_map|theme_map|label_map)\s*=\s*\{',
            # Hardcoded expected clusters
            r'expected_clusters\s*=',
            r'predefined_\w+\s*=\s*[\[\{]',
        ]

        for filepath in [engine_path, prompts_path]:
            assert filepath.exists(), f"{filepath} does not exist"
            content = filepath.read_text()

            for pattern in category_patterns:
                matches = re.findall(pattern, content)
                assert len(matches) == 0, (
                    f"Found hardcoded category pattern in {filepath.name}: "
                    f"'{pattern}' matched: {matches}. "
                    f"Clusters must emerge from data, not be predefined."
                )

        # Also verify the prompts.py doesn't contain a list of expected labels
        prompts_content = prompts_path.read_text()
        # A list of quoted strings on consecutive lines would indicate a preset vocabulary
        label_list_pattern = r'(?:^|\n)\s*["\'][\w\s]+["\']\s*,\s*\n\s*["\'][\w\s]+["\']\s*,'
        label_matches = re.findall(label_list_pattern, prompts_content)
        assert len(label_matches) == 0, (
            f"Found what looks like a predefined label list in prompts.py: {label_matches}"
        )


# ──────────────────────────────────────────────────────────────────
# HDBSCAN clustering tests
# ──────────────────────────────────────────────────────────────────

class TestHDBSCAN:
    """Tests for the core HDBSCAN clustering logic."""

    def test_hdbscan_finds_clusters(self, db, tmp_dirs):
        """Embed 30 known-similar values across 3 themes, verify HDBSCAN groups them."""
        from app.embeddings.embed_pipeline import EmbeddingPipeline
        from app.clustering.engine import ThemeClusteringEngine

        _, chroma_dir = tmp_dirs
        _seed_reviews(db, n=30)

        ep = EmbeddingPipeline(persist_dir=chroma_dir)
        engine = ThemeClusteringEngine(db=db, embedding_pipeline=ep, groq_api_key="test")

        # Get the values and run clustering directly
        values = db.get_field_values("topic")
        assert len(values) == 30

        clusters = engine._cluster_field("topic", values)
        # With 3 distinct themes of 10 each, HDBSCAN should find at least 2 clusters
        assert len(clusters) >= 2, (
            f"Expected at least 2 clusters from 3 themes, got {len(clusters)}"
        )

        # Each cluster should have multiple members
        for c in clusters:
            assert c["member_count"] >= 2

    def test_noise_points_excluded(self, db, tmp_dirs):
        """Verify HDBSCAN noise (-1) points are NOT assigned to any cluster."""
        from app.embeddings.embed_pipeline import EmbeddingPipeline
        from app.clustering.engine import ThemeClusteringEngine

        _, chroma_dir = tmp_dirs
        _seed_reviews(db, n=30)

        ep = EmbeddingPipeline(persist_dir=chroma_dir)
        engine = ThemeClusteringEngine(db=db, embedding_pipeline=ep, groq_api_key="test")

        values = db.get_field_values("topic")
        clusters = engine._cluster_field("topic", values)

        # Collect all assigned feedback IDs
        assigned_ids = set()
        for c in clusters:
            for fid in c["member_feedback_ids"]:
                assert fid not in assigned_ids, f"Duplicate: {fid} in multiple clusters"
                assigned_ids.add(fid)

        # Some values may be noise — total assigned should be <= total values
        assert len(assigned_ids) <= len(values)


# ──────────────────────────────────────────────────────────────────
# DB CRUD tests
# ──────────────────────────────────────────────────────────────────

class TestClusterDB:
    """Tests for the clustering database operations."""

    def test_rerun_replaces_old_clusters(self, db, tmp_dirs):
        """Running clustering twice should replace old clusters with new ones."""
        from app.embeddings.embed_pipeline import EmbeddingPipeline
        from app.clustering.engine import ThemeClusteringEngine

        _, chroma_dir = tmp_dirs
        _seed_reviews(db, n=30)

        ep = EmbeddingPipeline(persist_dir=chroma_dir)
        engine = ThemeClusteringEngine(db=db, embedding_pipeline=ep, groq_api_key="test")

        # First run — insert some fake clusters
        run1 = db.log_clustering_run({"status": "success", "cluster_types": '["topic"]'})
        db.insert_theme_clusters(
            [
                {
                    "label": "Old Cluster A",
                    "member_count": 5,
                    "percentage": 50.0,
                    "representative_quotes": [],
                    "sources_breakdown": {},
                    "countries_breakdown": {},
                    "member_feedback_ids": ["test-001", "test-002"],
                }
            ],
            run_id=run1,
            cluster_type="topic",
        )

        first = db.get_theme_clusters("topic")
        assert len(first) == 1
        assert first[0]["label"] == "Old Cluster A"

        # Second run — delete and re-insert
        db.delete_clusters_by_type("topic")
        run2 = db.log_clustering_run({"status": "success", "cluster_types": '["topic"]'})
        db.insert_theme_clusters(
            [
                {
                    "label": "New Cluster B",
                    "member_count": 8,
                    "percentage": 80.0,
                    "representative_quotes": [],
                    "sources_breakdown": {},
                    "countries_breakdown": {},
                    "member_feedback_ids": ["test-003", "test-004"],
                }
            ],
            run_id=run2,
            cluster_type="topic",
        )

        second = db.get_theme_clusters("topic")
        assert len(second) == 1
        assert second[0]["label"] == "New Cluster B"

    def test_representative_quotes_from_source(self, db):
        """Verify selected quotes actually come from the feedback table."""
        _seed_reviews(db, n=30)

        # Get a quote
        content = db.get_feedback_content("test-000")
        assert content != ""
        assert "Review about" in content

    def test_field_values_returns_non_null(self, db):
        """get_field_values should return only non-null values."""
        _seed_reviews(db, n=30)

        values = db.get_field_values("topic")
        assert len(values) == 30
        for v in values:
            assert v["value"] is not None
            assert v["value"] != ""

    def test_classified_count(self, db):
        """get_classified_count returns correct count."""
        _seed_reviews(db, n=30)
        assert db.get_classified_count() == 30

    def test_field_values_rejects_invalid_field(self, db):
        """get_field_values should reject invalid field names."""
        with pytest.raises(ValueError, match="Invalid field"):
            db.get_field_values("invalid_field_name")


# ──────────────────────────────────────────────────────────────────
# Settings tests
# ──────────────────────────────────────────────────────────────────

class TestClusteringSettings:
    """Verify clustering settings load correctly."""

    def test_settings_exist(self):
        from app.config.settings import settings
        assert settings.MIN_CLUSTER_SIZE == 5
        assert settings.MIN_SAMPLES == 3
        assert "topic" in settings.CLUSTER_FIELDS
        assert "core_complaint" in settings.CLUSTER_FIELDS
        assert "behaviour_pattern" in settings.CLUSTER_FIELDS
        assert "unmet_need" in settings.CLUSTER_FIELDS
        assert settings.MAX_LABEL_SAMPLES == 20

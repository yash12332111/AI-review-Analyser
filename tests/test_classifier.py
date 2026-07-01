"""
Tests for the classification engine.
Includes both mocked unit tests and a live Groq API test (when API key is set).
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from app.classifier.engine import ClassificationEngine
from app.classifier.prompts import CLASSIFICATION_SYSTEM_PROMPT
from app.models.feedback import ClassificationResult, FeedbackRecord
from app.database.db_manager import DatabaseManager


@pytest.fixture
def db(tmp_path):
    """Provide a fresh, initialized database for each test."""
    db_path = tmp_path / "test.db"
    manager = DatabaseManager(str(db_path))
    manager.initialize()
    yield manager
    manager.close()


# --- Unit Tests (mocked, no API calls) ---

@pytest.mark.asyncio
async def test_short_content_skipped(db):
    """Content < 20 chars should return None without calling the API."""
    engine = ClassificationEngine(db)
    result = await engine.classify_single("too short", "test-id")
    assert result is None


@pytest.mark.asyncio
async def test_validation_catches_bad_enums(db):
    """Feed in JSON with invalid enum values, verify fuzzy mapping handles them."""
    engine = ClassificationEngine(db)

    # Valid JSON but with non-standard enum values
    mock_json = json.dumps({
        "topic": "test topic",
        "core_complaint": "test complaint",
        "trust_level": "very low",  # Should map to "low"
        "sentiment": "negative",
        "frustration_intensity": "extremely frustrated",  # Should map to "severe"
        "user_job_to_be_done": None,
        "repeat_listen_reason": None,
        "workaround_mentioned": False,
        "workaround_description": None,
        "behaviour_pattern": None,
        "pattern_evidence": None,
        "unmet_need": None,
    })

    result = engine._parse_and_validate(mock_json, "test-id")
    assert result.trust_level == "low"  # Fuzzy mapped from "very low"
    assert result.frustration_intensity == "severe"  # Fuzzy mapped
    assert result.feedback_id == "test-id"


@pytest.mark.asyncio
async def test_clean_response_strips_markdown():
    """Verify markdown code fences are stripped from responses."""
    engine_cls = ClassificationEngine

    # Test markdown code fence stripping
    wrapped = '```json\n{"topic": "test"}\n```'
    cleaned = engine_cls._clean_response(wrapped)
    assert cleaned == '{"topic": "test"}'

    # Test extra text before JSON
    with_prefix = 'Here is the analysis:\n{"topic": "test"}'
    cleaned = engine_cls._clean_response(with_prefix)
    assert cleaned == '{"topic": "test"}'


@pytest.mark.asyncio
async def test_retry_on_invalid_json(db):
    """Mock a first invalid response, verify retry succeeds."""
    engine = ClassificationEngine(db)

    valid_response = json.dumps({
        "topic": "app not working",
        "core_complaint": "app crashes on startup",
        "trust_level": "low",
        "sentiment": "negative",
        "frustration_intensity": "moderate",
        "user_job_to_be_done": "listen to music",
        "repeat_listen_reason": None,
        "workaround_mentioned": False,
        "workaround_description": None,
        "behaviour_pattern": None,
        "pattern_evidence": None,
        "unmet_need": "wants a stable app",
    })

    call_count = 0

    async def mock_call_groq(messages, attempt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "not valid json at all {{{}"
        return valid_response

    with patch.object(engine, "_call_groq", side_effect=mock_call_groq):
        result = await engine.classify_single(
            "The app keeps crashing every time I open it, very frustrating experience.",
            "retry-test-id"
        )

    assert result is not None
    assert result.topic == "app not working"
    assert call_count == 2  # First failed, second succeeded


@pytest.mark.asyncio
async def test_batch_classification(db):
    """Insert 3 unclassified records, run batch, verify all classified."""
    # Insert test records
    for i in range(3):
        record = FeedbackRecord(
            source="test",
            source_id=f"batch_test_{i}",
            content=f"This is test review number {i} about Spotify music discovery features and how they work.",
        )
        db.insert_feedback(record)

    engine = ClassificationEngine(db)

    valid_response = json.dumps({
        "topic": "music discovery features",
        "core_complaint": None,
        "trust_level": None,
        "sentiment": "neutral",
        "frustration_intensity": None,
        "user_job_to_be_done": None,
        "repeat_listen_reason": None,
        "workaround_mentioned": False,
        "workaround_description": None,
        "behaviour_pattern": None,
        "pattern_evidence": None,
        "unmet_need": None,
    })

    async def mock_call_groq(messages, attempt):
        return valid_response

    with patch.object(engine, "_call_groq", side_effect=mock_call_groq):
        classified = await engine.classify_batch(batch_size=10)

    assert classified == 3

    # Verify all are now classified in DB
    remaining = db.get_unclassified(limit=100)
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_off_topic_skipped(db):
    """Off-topic reviews should return None."""
    engine = ClassificationEngine(db)

    async def mock_call_groq(messages, attempt):
        return json.dumps({"off_topic": True})

    with patch.object(engine, "_call_groq", side_effect=mock_call_groq):
        result = await engine.classify_single(
            "This review is about Apple Music not Spotify at all.",
            "offtopic-test-id"
        )

    assert result is None

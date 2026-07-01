"""
Pydantic data models for the AI Feedback Intelligence System.

These models mirror the SQLite schema and provide type-safe data flow
across all phases of the pipeline.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Optional, List, Literal

from pydantic import BaseModel, Field


class FeedbackRecord(BaseModel):
    """Raw feedback from any source — this is what collectors produce."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str                              # appstore | playstore | spotify_community | trustpilot
    country: Optional[str] = None            # e.g., 'US', 'GB', 'IN' (for app stores)
    source_id: str                           # Original ID from the platform
    author: Optional[str] = None
    content: str
    url: Optional[str] = None
    posted_at: Optional[datetime] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    raw_json: Optional[str] = None


class ClassificationResult(BaseModel):
    """11-field AI classification output — this is what the classifier produces.

    Fields (per Agents.md schema discipline):
      topic, core_complaint, trust_level, sentiment, frustration_intensity,
      user_job_to_be_done, repeat_listen_reason, workaround_mentioned,
      workaround_description, behaviour_pattern, pattern_evidence
      (plus unmet_need)
    """
    feedback_id: str
    topic: Optional[str] = None
    core_complaint: Optional[str] = None
    trust_level: Optional[Literal["high", "medium", "low", "broken"]] = None
    sentiment: Literal["positive", "negative", "mixed", "neutral"]
    frustration_intensity: Optional[Literal["mild", "moderate", "severe", "churned"]] = None
    user_job_to_be_done: Optional[str] = None
    repeat_listen_reason: Optional[str] = None
    workaround_mentioned: bool = False
    workaround_description: Optional[str] = None
    behaviour_pattern: Optional[str] = None
    pattern_evidence: Optional[str] = None
    quote_translated: Optional[str] = None
    unmet_need: Optional[str] = None


class ClassifiedFeedback(BaseModel):
    """Joined model — feedback + classification. Used in API responses."""
    # FeedbackRecord fields
    id: str
    source: str
    country: Optional[str] = None
    source_id: str
    author: Optional[str] = None
    content: str
    url: Optional[str] = None
    posted_at: Optional[datetime] = None
    collected_at: datetime
    # ClassificationResult fields
    topic: Optional[str] = None
    core_complaint: Optional[str] = None
    trust_level: Optional[str] = None
    sentiment: Optional[str] = None
    frustration_intensity: Optional[str] = None
    user_job_to_be_done: Optional[str] = None
    repeat_listen_reason: Optional[str] = None
    workaround_mentioned: bool = False
    workaround_description: Optional[str] = None
    behaviour_pattern: Optional[str] = None
    pattern_evidence: Optional[str] = None
    quote_translated: Optional[str] = None
    unmet_need: Optional[str] = None


class CollectionRunLog(BaseModel):
    """Metadata for a single collection run."""
    source: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    records_fetched: int = 0
    records_new: int = 0
    status: Literal["running", "success", "failed"]
    error_message: Optional[str] = None


class DashboardFilters(BaseModel):
    """Query parameters for dashboard API endpoints."""
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    source: Optional[str] = None
    country: Optional[str] = None
    sentiment: Optional[str] = None
    topic: Optional[str] = None
    discovery_filter: Optional[bool] = False


class ChatFilters(BaseModel):
    """Query parameters for RAG chat."""
    date_range: Optional[str] = "last_7_days"   # today | last_7_days | last_30_days | custom
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    source: Optional[str] = None
    sentiment: Optional[str] = None
    topic: Optional[str] = None
    signal_type: Optional[str] = None           # workarounds_only | churned_only | high_frustration_only

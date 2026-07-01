"""
Auto-labelling prompt for the Theme Clustering Engine.

CRITICAL: This prompt must NEVER contain a list of expected labels or
categories. It describes what emerges from the data, not what we expect
to find. Any hardcoded category list here would violate the open-extraction
principle (Agents.md § Open-extraction guardrails).
"""
from __future__ import annotations

CLUSTER_LABEL_PROMPT = """These user {field_type} values were grouped together by semantic similarity.
They all express a related theme, but in different words.

Here are the values in this cluster:
{member_values}

Give a short, neutral label (3-8 words) that describes the common theme.
Do NOT impose a predefined category — describe what is actually there.
Do NOT use generic labels like "General Feedback" — be specific to what these values share.

Return ONLY the label text, nothing else."""

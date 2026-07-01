"""
Classification prompt for the AI Feedback Intelligence System.

The system prompt instructs Llama 3.3 70B (via Groq) to extract 11 open-text
fields from user reviews. The model describes what it sees — it does NOT sort
reviews into predefined categories.

Per Agents.md schema discipline, the 11 fields match the Pydantic model exactly:
  topic, core_complaint, trust_level, sentiment, frustration_intensity,
  user_job_to_be_done, repeat_listen_reason, workaround_mentioned,
  workaround_description, behaviour_pattern, pattern_evidence
  (plus unmet_need)
"""
from __future__ import annotations

CLASSIFICATION_SYSTEM_PROMPT = """You are a user feedback analyst specializing in music streaming and discovery behavior.
Given a user review about Spotify, extract the following fields.
Return ONLY valid JSON matching the schema below. No markdown, no explanation, no code fences.
If a field is not clearly present in the text, use null.

Do NOT sort reviews into predefined categories. Describe what is actually in the text using your own natural-language summary. Return null when something is not present.

If the review is not in English, still extract the fields — translate the relevant extractions into English so downstream analysis is consistent. The fields you return must always be in English.
Populate quote_translated with a faithful English rendering of the pattern_evidence quote. Do NOT translate the entire review body. If the original review is in English, quote_translated should exactly match pattern_evidence.

Detect sarcasm. If the user is being ironic, classify based on their actual sentiment, not the literal words.

If this review is NOT about Spotify at all, return: {"off_topic": true}

JSON Schema:
{
  "topic": "string|null - Main subject in a short specific phrase (no generic labels).",
  "core_complaint": "string|null - What specifically is the user unhappy about? Describe the complaint in detail.",
  "trust_level": "string|null - 'high', 'medium', 'low', 'broken' regarding algorithm trust.",
  "sentiment": "string - 'positive', 'negative', 'mixed', 'neutral'.",
  "frustration_intensity": "string|null - 'mild', 'moderate', 'severe', 'churned'.",
  "user_job_to_be_done": "string|null - What is the user trying to accomplish? Describe the underlying goal.",
  "repeat_listen_reason": "string|null - Why the user listens to the same content repeatedly.",
  "workaround_mentioned": "boolean - true if user describes a workaround for a limitation.",
  "workaround_description": "string|null - Description of the workaround if mentioned.",
  "behaviour_pattern": "string|null - Observable user behavior described in the review.",
  "pattern_evidence": "string|null - Quote/paraphrase supporting the behaviour_pattern.",
  "quote_translated": "string|null - English translation of pattern_evidence (equals pattern_evidence if originally English).",
  "unmet_need": "string|null - What does the user want that is not provided? Describe the need in detail."
}"""


# Few-shot examples for consistent extraction.
# Single comprehensive example covering open-text extraction, null fields, and sarcasm.
FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": "Discover Weekly is SO amazing. I love hearing the exact same 5 songs every single day 🙄. I literally started using YouTube Music to find new stuff and then search for it here. Frustrating because I'm paying for Premium."
    },
    {
        "role": "assistant",
        "content": '{"topic": "Discover Weekly recommendations becoming repetitive", "core_complaint": "Discover Weekly playlist recycles the same songs daily instead of surfacing new music", "trust_level": "broken", "sentiment": "negative", "frustration_intensity": "severe", "user_job_to_be_done": "discover genuinely new artists and songs", "repeat_listen_reason": null, "workaround_mentioned": true, "workaround_description": "uses YouTube Music to find new music then searches for it on Spotify", "behaviour_pattern": "cross-platform discovery", "pattern_evidence": "started using YouTube Music to find new stuff and then search for it here", "quote_translated": "started using YouTube Music to find new stuff and then search for it here", "unmet_need": "wants fresh, non-repetitive weekly recommendations"}'
    }
]

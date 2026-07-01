"""
ClassificationEngine — takes unclassified feedback and uses Groq (Llama 3.3 70B)
to extract 11 open-text fields per review.

Key details (per implementation_plan.md):
- Daily cap: MAX_CLASSIFICATIONS_PER_RUN (default 900)
- Temperature: 0.1
- Response format: json_object
- Retry: 2x on invalid JSON, exponential backoff on 429
- Rate limiting: 1-second delay between calls
- Timeout: 30 seconds per request
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Optional, List, Dict

from groq import Groq

from app.config.settings import settings
from app.database.db_manager import DatabaseManager
from app.models.feedback import FeedbackRecord, ClassificationResult
from app.classifier.prompts import CLASSIFICATION_SYSTEM_PROMPT, FEW_SHOT_EXAMPLES

logger = logging.getLogger(__name__)

# Max content length to send to the model (Edge case #8)
MAX_CONTENT_CHARS = 2000

# Fuzzy mapping for enum values the LLM might output (Edge case #4)
TRUST_LEVEL_MAP = {
    "high": "high", "medium": "medium", "low": "low", "broken": "broken",
    "very low": "low", "very high": "high", "none": "broken", "moderate": "medium",
}
SENTIMENT_MAP = {
    "positive": "positive", "negative": "negative", "mixed": "mixed", "neutral": "neutral",
}
FRUSTRATION_MAP = {
    "mild": "mild", "moderate": "moderate", "severe": "severe", "churned": "churned",
    "none": None, "low": "mild", "high": "severe", "very high": "churned",
    "extremely frustrated": "severe",
}


class ClassificationEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db
        
        # Initialize keys from comma-separated list, fallback to single key
        keys_from_env = [k.strip() for k in settings.GROQ_API_KEYS.split(",") if k.strip()]
        if keys_from_env:
            self.api_keys = keys_from_env
        elif settings.GROQ_API_KEY:
            self.api_keys = [settings.GROQ_API_KEY]
        else:
            self.api_keys = []
            
        self.current_key_idx = 0
        if self.api_keys:
            self.client = Groq(api_key=self.api_keys[self.current_key_idx])
            logger.info(f"Initialized with {len(self.api_keys)} API keys.")
        else:
            self.client = Groq(api_key="")
            logger.warning("No Groq API keys found in settings.")

        self._last_error_is_daily_limit = False
        self._all_keys_exhausted = False

    def _rotate_key(self) -> bool:
        if self.current_key_idx + 1 < len(self.api_keys):
            self.current_key_idx += 1
            self.client = Groq(api_key=self.api_keys[self.current_key_idx])
            logger.info(f"Rotated to API key {self.current_key_idx + 1}/{len(self.api_keys)}")
            return True
        self._all_keys_exhausted = True
        return False

    async def classify_batch(self, batch_size: int = 50) -> int:
        """
        1. Fetch unclassified records from DB (limit=batch_size)
        2. For each record, call classify_single()
        3. Store valid results in DB
        4. Return count of successfully classified records
        """
        # Reset stale exhaustion state from any previous batch/run so we
        # re-try with fresh Groq daily quotas.
        self._all_keys_exhausted = False
        self._last_error_is_daily_limit = False
        self.current_key_idx = 0
        if self.api_keys:
            self.client = Groq(api_key=self.api_keys[0])

        records = self.db.get_unclassified(limit=batch_size)
        if not records:
            logger.info("No unclassified records found.")
            return 0

        logger.info(f"Classifying {len(records)} records...")
        classified_count = 0
        skipped_count = 0
        attempted_count = 0
        daily_limit_hit = False

        for i, record in enumerate(records):
            if self._all_keys_exhausted or daily_limit_hit:
                logger.info(
                    f"Stopping batch — all API keys exhausted. "
                    f"{classified_count} classified, {len(records) - i} remaining for next run."
                )
                break

            attempted_count += 1
            try:
                result = await self.classify_single(record.content, record.id)
                if result is not None:
                    self.db.insert_classification(result)
                    classified_count += 1
                elif result is None and self._last_error_is_daily_limit:
                    daily_limit_hit = True
                    # Do NOT mark as skipped — this is a TPD failure, not a content decision.
                    # It will be retried next run (classified_at stays NULL, skipped stays 0).
                else:
                    # Off-topic or all-null: a content decision, not an API error.
                    # Mark skipped so it's retained for audit but excluded from future runs.
                    self.db.mark_skipped(record.id)
                    skipped_count += 1
                    logger.debug(f"Marked {record.id} as skipped (off-topic/all-null)")

                # Progress logging every 10 records
                if attempted_count % 10 == 0:
                    logger.info(
                        f"Progress: {attempted_count}/{len(records)} "
                        f"({classified_count} classified, {skipped_count} skipped)"
                    )

                # Rate limiting: 2-second delay between API calls
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Unexpected error classifying {record.id}: {e}")
                skipped_count += 1

        skip_rate = (skipped_count / attempted_count * 100) if attempted_count else 0
        logger.info(
            f"Batch complete: {classified_count} classified, "
            f"{skipped_count} skipped ({skip_rate:.1f}% of {attempted_count} attempted)"
        )
        return classified_count

    async def classify_single(
        self, content: str, feedback_id: str
    ) -> Optional[ClassificationResult]:
        """
        Classify a single review:
        1. Skip if content < 20 characters
        2. Build messages (system prompt + few-shot + user content)
        3. Call Groq API with temperature=0.1, response_format=json
        4. Parse JSON response
        5. Validate against ClassificationResult model
        6. Retry up to 2x on invalid JSON
        7. Return ClassificationResult or None on failure
        """
        self._last_error_is_daily_limit = False

        # Edge case #8: skip ultra-short content
        if len(content.strip()) < 20:
            logger.debug(f"Skipping {feedback_id}: content too short ({len(content.strip())} chars)")
            return None

        # Edge case #8: truncate very long content
        truncated = self._truncate_content(content)

        messages = self._build_messages(truncated)
        max_retries = 2
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                raw_json = await self._call_groq(messages, attempt)

                # Check for off-topic response (Edge case #6)
                parsed = json.loads(raw_json)
                if parsed.get("off_topic"):
                    logger.debug(f"Skipping {feedback_id}: off-topic review")
                    return None

                result = self._parse_and_validate(raw_json, feedback_id)
                return result

            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1}: "
                    f"Invalid JSON for {feedback_id}: {e}"
                )
                # On retry, append a correction instruction
                if attempt < max_retries:
                    messages.append({
                        "role": "user",
                        "content": "Your previous response was not valid JSON. Return ONLY valid JSON matching the schema, no markdown, no explanation."
                    })

            except Exception as e:
                last_error = e
                error_str = str(e)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1}: "
                    f"Error classifying {feedback_id}: {e}"
                )

                # Detect daily TPD limit
                if "tokens per day" in error_str.lower() or "tpd" in error_str:
                    logger.warning(f"Daily token limit reached on current key ({self.current_key_idx + 1}/{len(self.api_keys)}).")
                    if self._rotate_key():
                        # Give it another shot without penalizing the attempt counter
                        max_retries += 1
                        continue
                    else:
                        logger.warning(f"All keys exhausted — stopping retries for {feedback_id}")
                        self._last_error_is_daily_limit = True
                        return None

                if attempt < max_retries:
                    # Exponential backoff for rate limits
                    backoff = 2 ** (attempt + 1)
                    logger.info(f"Backing off {backoff}s before retry...")
                    await asyncio.sleep(backoff)

        logger.error(f"All {max_retries + 1} attempts failed for {feedback_id}: {last_error}")
        return None

    async def _call_groq(self, messages: List[Dict], attempt: int) -> str:
        """Call the Groq API and return the raw response content."""
        # Use asyncio.to_thread since the Groq client is synchronous
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=1024,
            timeout=30.0,
        )

        raw = response.choices[0].message.content
        if not raw:
            raise ValueError("Groq returned empty response")

        # Edge case #1 & #2: strip markdown code fences and extract JSON
        raw = self._clean_response(raw)
        return raw

    def _build_messages(self, content: str) -> List[Dict]:
        """Construct the system + few-shot + user message list."""
        messages = [{"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT}]
        # Add few-shot examples
        messages.extend(FEW_SHOT_EXAMPLES)
        # Add the actual review to classify
        messages.append({"role": "user", "content": content})
        return messages

    def _parse_and_validate(
        self, raw_json: str, feedback_id: str
    ) -> ClassificationResult:
        """Parse JSON string, fuzzy-map enums, validate with Pydantic."""
        data = json.loads(raw_json)

        # Inject feedback_id
        data["feedback_id"] = feedback_id

        # Fuzzy-map enum values (Edge case #4)
        if data.get("trust_level") is not None:
            mapped = TRUST_LEVEL_MAP.get(
                str(data["trust_level"]).lower().strip()
            )
            data["trust_level"] = mapped  # None if not mappable

        if data.get("sentiment") is not None:
            mapped = SENTIMENT_MAP.get(
                str(data["sentiment"]).lower().strip()
            )
            if mapped:
                data["sentiment"] = mapped
            else:
                data["sentiment"] = "neutral"  # Safe fallback

        if data.get("frustration_intensity") is not None:
            mapped = FRUSTRATION_MAP.get(
                str(data["frustration_intensity"]).lower().strip()
            )
            data["frustration_intensity"] = mapped  # None if "none"

        # Ensure workaround_mentioned is boolean
        if "workaround_mentioned" in data:
            data["workaround_mentioned"] = bool(data["workaround_mentioned"])

        # Edge case #5: check if everything meaningful is null
        if (
            data.get("topic") is None
            and data.get("core_complaint") is None
            and data.get("behaviour_pattern") is None
            and data.get("sentiment") == "neutral"
        ):
            logger.debug(f"All meaningful fields null for {feedback_id} — likely off-topic")

        return ClassificationResult(**data)

    @staticmethod
    def _clean_response(raw: str) -> str:
        """Strip markdown fences and extract JSON object."""
        raw = raw.strip()

        # Remove markdown code fences
        if raw.startswith("```"):
            # Remove opening fence (```json or ```)
            raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw)

        # If there's text before the JSON, extract the first {...} block
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return match.group(0)

        return raw

    @staticmethod
    def _truncate_content(content: str) -> str:
        """Truncate long content, preserving first and last paragraphs."""
        if len(content) <= MAX_CONTENT_CHARS:
            return content

        # Keep first ~1500 chars and last ~500 chars
        first = content[:1500]
        last = content[-500:]
        return f"{first}\n\n[...truncated...]\n\n{last}"

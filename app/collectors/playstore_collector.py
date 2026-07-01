"""
Play Store Collector — fetches Spotify reviews from Google Play using google-play-scraper.

Iterates over PLAY_STORE_COUNTRIES from settings, using country-appropriate
language codes so each market returns genuinely different reviews.
Uses asyncio.to_thread to wrap the synchronous google-play-scraper calls.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict

from google_play_scraper import reviews, Sort

from app.collectors.base_collector import AbstractCollector
from app.config.settings import settings
from app.models.feedback import FeedbackRecord

logger = logging.getLogger(__name__)

SPOTIFY_PACKAGE = "com.spotify.music"

# Map country codes to their primary language codes.
# Using native languages ensures each market returns genuinely distinct reviews
# rather than the same global English pool.
COUNTRY_LANG_MAP = {
    "US": "en",
    "GB": "en",   # Will overlap with US; mitigated by fetching more per-country
    "IN": "hi",   # Hindi — India's most common non-English Play Store language
    "BR": "pt",   # Portuguese
    "DE": "de",   # German
    "FR": "fr",   # French
    "ES": "es",   # Spanish
    "JP": "ja",   # Japanese
    "MX": "es",   # Spanish (Mexico)
    "IT": "it",   # Italian
}


class PlayStoreCollector(AbstractCollector):
    source_name = "playstore"

    async def collect(self, since: datetime) -> List[Dict]:
        """Fetch reviews from Google Play for each configured country,
        using country-appropriate language codes for distinct results."""
        all_reviews: List[Dict] = []
        seen_ids: set = set()  # Track IDs to prevent cross-country dupes at collection time

        for country in settings.PLAY_STORE_COUNTRIES:
            country_upper = country.upper()
            country_lower = country.lower()
            lang = COUNTRY_LANG_MAP.get(country_upper, "en")

            try:
                result, _ = await asyncio.to_thread(
                    reviews,
                    SPOTIFY_PACKAGE,
                    lang=lang,
                    country=country_lower,
                    sort=Sort.NEWEST,
                    count=settings.MAX_RECORDS_PER_SOURCE_PER_RUN,
                )

                # Deduplicate at collection time — if US/GB both use 'en',
                # the second one will only add reviews not already seen.
                new_for_country = 0
                for review in result:
                    rid = review.get("reviewId", "")
                    if rid and rid not in seen_ids:
                        seen_ids.add(rid)
                        review["_country"] = country_upper
                        review["_lang"] = lang
                        all_reviews.append(review)
                        new_for_country += 1

                logger.info(
                    f"[playstore/{country_lower}({lang})] "
                    f"Fetched {len(result)}, {new_for_country} unique new"
                )

            except Exception as e:
                logger.warning(f"[playstore/{country_lower}] Failed: {e}")

            # Small delay between country requests
            await asyncio.sleep(1)

        return all_reviews

    def normalize(self, raw: dict) -> FeedbackRecord:
        """Convert a google-play-scraper review dict into a FeedbackRecord."""
        content = raw.get("content", "")
        review_id = raw.get("reviewId", "")
        author = raw.get("userName", "")

        # google-play-scraper returns datetime objects for 'at'
        posted_at = raw.get("at")
        if posted_at and not isinstance(posted_at, datetime):
            try:
                posted_at = datetime.fromisoformat(str(posted_at))
            except (ValueError, TypeError):
                posted_at = None

        return FeedbackRecord(
            source="playstore",
            source_id=review_id or self.content_hash(content),
            country=raw.get("_country", "US"),
            author=author or None,
            content=content,
            url=f"https://play.google.com/store/apps/details?id={SPOTIFY_PACKAGE}",
            posted_at=posted_at,
            raw_json=json.dumps(raw, ensure_ascii=False, default=str),
        )

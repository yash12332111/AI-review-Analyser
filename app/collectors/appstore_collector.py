"""
App Store Collector — fetches Spotify reviews from Apple's official RSS feed.

Uses the public iTunes customer reviews JSON endpoint:
  https://itunes.apple.com/{country}/rss/customerreviews/id=324684580/sortBy=mostRecent/json

Iterates over APP_STORE_COUNTRIES from settings, tagging each review with its country.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Dict

import httpx

from app.collectors.base_collector import AbstractCollector
from app.config.settings import settings
from app.models.feedback import FeedbackRecord

logger = logging.getLogger(__name__)

SPOTIFY_APP_ID = "324684580"
RSS_URL_TEMPLATE = (
    "https://itunes.apple.com/{country}/rss/customerreviews"
    f"/id={SPOTIFY_APP_ID}/sortBy=mostRecent/json"
)


class AppStoreCollector(AbstractCollector):
    source_name = "appstore"

    async def collect(self, since: datetime) -> List[Dict]:
        """Fetch reviews from Apple RSS feed for each configured country."""
        all_reviews: List[Dict] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for country in settings.APP_STORE_COUNTRIES:
                country_lower = country.lower()
                url = RSS_URL_TEMPLATE.format(country=country_lower)
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()

                    entries = data.get("feed", {}).get("entry", [])
                    # First entry is often app metadata, not a review — skip if it
                    # doesn't have an "im:rating" key (reviews always have ratings)
                    reviews = [
                        e for e in entries
                        if "im:rating" in e
                    ]

                    # Tag each review with its country
                    for review in reviews:
                        review["_country"] = country.upper()

                    all_reviews.extend(reviews)
                    logger.info(
                        f"[appstore/{country_lower}] Fetched {len(reviews)} reviews"
                    )

                except httpx.HTTPStatusError as e:
                    logger.warning(
                        f"[appstore/{country_lower}] HTTP {e.response.status_code}: {e}"
                    )
                except Exception as e:
                    logger.warning(f"[appstore/{country_lower}] Failed: {e}")

                # Small delay between country requests to be polite
                import asyncio
                await asyncio.sleep(1)

        return all_reviews

    def normalize(self, raw: dict) -> FeedbackRecord:
        """Convert an Apple RSS review entry into a FeedbackRecord."""
        # Extract fields from the RSS JSON structure
        title = raw.get("title", {}).get("label", "")
        content = raw.get("content", {}).get("label", "")
        author = raw.get("author", {}).get("name", {}).get("label", "")
        review_id = raw.get("id", {}).get("label", "")

        # Combine title and content for full review text
        full_text = f"{title}\n{content}".strip() if title else content.strip()

        # Parse the "updated" field for posted_at
        updated = raw.get("updated", {}).get("label", "")
        posted_at = None
        if updated:
            try:
                # Apple RSS dates look like "2024-01-15T12:00:00-07:00"
                posted_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return FeedbackRecord(
            source="appstore",
            source_id=review_id or self.content_hash(full_text),
            country=raw.get("_country", "US"),
            author=author or None,
            content=full_text,
            url=f"https://apps.apple.com/{raw.get('_country', 'us').lower()}/app/spotify-music/id{SPOTIFY_APP_ID}",
            posted_at=posted_at,
            raw_json=json.dumps(raw, ensure_ascii=False, default=str),
        )

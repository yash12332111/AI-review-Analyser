"""
Trustpilot Collector — scrapes public Trustpilot reviews for Spotify.

Uses httpx + BeautifulSoup4. This is an OPTIONAL/NON-CRITICAL source.
If the layout changes or scraping is blocked, it fails gracefully and
the pipeline continues with the other 3 collectors.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict

import httpx
from bs4 import BeautifulSoup

from app.collectors.base_collector import AbstractCollector
from app.models.feedback import FeedbackRecord

logger = logging.getLogger(__name__)

TRUSTPILOT_URL = "https://www.trustpilot.com/review/www.spotify.com"

# Full, realistic browser headers to reduce chance of 403
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}


class TrustpilotCollector(AbstractCollector):
    source_name = "trustpilot"

    async def collect(self, since: datetime) -> List[Dict]:
        """Scrape reviews from Trustpilot's Spotify page."""
        all_reviews: List[Dict] = []

        async with httpx.AsyncClient(
            timeout=30.0, headers=HEADERS, follow_redirects=True
        ) as client:
            # Fetch first 2 pages to get recent reviews
            for page in range(1, 3):
                url = f"{TRUSTPILOT_URL}?page={page}"
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    page_reviews = self._parse_reviews_page(response.text)
                    all_reviews.extend(page_reviews)
                    logger.info(
                        f"[trustpilot] Page {page}: found {len(page_reviews)} reviews"
                    )
                except httpx.HTTPStatusError as e:
                    logger.warning(
                        f"[trustpilot] HTTP {e.response.status_code} on page {page} — "
                        "Trustpilot may be blocking the request. "
                        "This is a non-critical source; pipeline continues."
                    )
                    break
                except Exception as e:
                    logger.warning(f"[trustpilot] Failed page {page}: {e}")
                    break

                await asyncio.sleep(3)  # Longer delay to be polite

        if not all_reviews:
            logger.warning(
                "[trustpilot] 0 reviews fetched — "
                "this is a non-critical optional source, pipeline continues"
            )

        return all_reviews

    def _parse_reviews_page(self, html: str) -> List[Dict]:
        """Parse a Trustpilot review page and extract review data."""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Trustpilot uses data-service-review-card-paper or article elements
        review_cards = soup.select(
            "[data-service-review-card-paper], "
            "article.review-card, "
            ".styles_reviewCardInner__EsrRC"
        )

        for card in review_cards:
            try:
                # Extract review text — try multiple selectors
                text_el = (
                    card.select_one("[data-service-review-text-typography]")
                    or card.select_one(".review-content__text")
                    or card.select_one("p")
                )
                content = text_el.get_text(strip=True) if text_el else ""

                # Extract title
                title_el = (
                    card.select_one("[data-service-review-title-typography]")
                    or card.select_one("h2")
                    or card.select_one(".review-content__title")
                )
                title = title_el.get_text(strip=True) if title_el else ""

                # Combine
                full_text = f"{title}\n{content}".strip() if title else content

                if not full_text:
                    continue

                # Extract author
                author_el = card.select_one(
                    "[data-consumer-name-typography], "
                    ".consumer-information__name"
                )
                author = author_el.get_text(strip=True) if author_el else ""

                # Extract date
                time_el = card.select_one("time")
                posted_at = None
                if time_el:
                    dt_str = time_el.get("datetime", "")
                    if dt_str:
                        try:
                            posted_at = datetime.fromisoformat(
                                dt_str.replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                results.append({
                    "content": full_text,
                    "author": author,
                    "posted_at": posted_at,
                    "source_id": self.content_hash(full_text),
                })

            except Exception as e:
                logger.debug(f"[trustpilot] Failed to parse one card: {e}")
                continue

        return results

    def normalize(self, raw: dict) -> FeedbackRecord:
        """Convert a scraped Trustpilot review into a FeedbackRecord."""
        content = raw.get("content", "")
        posted_at = raw.get("posted_at")
        if posted_at and not isinstance(posted_at, datetime):
            try:
                posted_at = datetime.fromisoformat(str(posted_at))
            except (ValueError, TypeError):
                posted_at = None

        return FeedbackRecord(
            source="trustpilot",
            source_id=raw.get("source_id", self.content_hash(content)),
            country=None,  # Trustpilot doesn't provide country per review
            author=raw.get("author") or None,
            content=content,
            url=TRUSTPILOT_URL,
            posted_at=posted_at,
            raw_json=json.dumps(raw, ensure_ascii=False, default=str),
        )

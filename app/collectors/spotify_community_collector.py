"""
Spotify Community Collector — scrapes community.spotify.com forum threads.

Strategy:
1. Scrape the Ongoing-Issues board listing pages (server-rendered, has
   `.custom-message-tile` elements) to discover thread URLs.
2. Follow each thread URL and extract individual user replies
   (`.lia-message-body-content` elements) as feedback records.

Other boards (iOS, Android, Live-Ideas, etc.) are JS-rendered SPAs that
return no thread content in the HTML, so we focus on Ongoing-Issues which
is the only board with server-side rendered thread listings.
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
from app.config.settings import settings
from app.models.feedback import FeedbackRecord

logger = logging.getLogger(__name__)

# Board listing pages that are server-rendered
BOARD_URLS = [
    "https://community.spotify.com/t5/Ongoing-Issues/bd-p/Ongoing_Issues",
    "https://community.spotify.com/t5/Ongoing-Issues/bd-p/Ongoing_Issues/page/2",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

BASE_URL = "https://community.spotify.com"


class SpotifyCommunityCollector(AbstractCollector):
    source_name = "spotify_community"

    async def collect(self, since: datetime) -> List[Dict]:
        """
        Two-phase collection:
        1. Scrape board listing pages to get thread URLs
        2. Scrape each thread page to get user replies
        """
        all_posts: List[Dict] = []

        async with httpx.AsyncClient(
            timeout=30.0, headers=HEADERS, follow_redirects=True
        ) as client:
            # Phase 1: Get thread URLs from board listing
            thread_urls = await self._get_thread_urls(client)
            logger.info(
                f"[spotify_community] Discovered {len(thread_urls)} thread URLs"
            )

            if not thread_urls:
                logger.warning(
                    "[spotify_community] 0 threads discovered — "
                    "board HTML structure may have changed"
                )
                return all_posts

            # Phase 2: Scrape user replies from each thread
            # Limit to first N threads to stay within reasonable bounds
            max_threads = min(len(thread_urls), 10)
            for i, (thread_title, thread_url) in enumerate(thread_urls[:max_threads]):
                try:
                    replies = await self._scrape_thread(client, thread_title, thread_url)
                    all_posts.extend(replies)
                    logger.info(
                        f"[spotify_community] Thread {i+1}/{max_threads}: "
                        f"{len(replies)} replies from '{thread_title[:50]}...'"
                    )
                except Exception as e:
                    logger.warning(
                        f"[spotify_community] Failed to scrape thread '{thread_title[:40]}': {e}"
                    )

                await asyncio.sleep(1.5)  # Polite delay between thread requests

        return all_posts

    async def _get_thread_urls(self, client: httpx.AsyncClient) -> List[tuple]:
        """Scrape board listing pages to discover thread URLs."""
        threads = []
        seen_urls = set()

        for board_url in BOARD_URLS:
            try:
                response = await client.get(board_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

                tiles = soup.select(".custom-message-tile")
                for tile in tiles:
                    # Find the thread link (contains /idi-p/ in href)
                    for a in tile.select("a"):
                        href = a.get("href", "")
                        text = a.get_text(strip=True)
                        if text and "/idi-p/" in href and href not in seen_urls:
                            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                            seen_urls.add(href)
                            threads.append((text, full_url))
                            break  # Only take the first thread link per tile

                logger.info(
                    f"[spotify_community] Board page: {len(tiles)} tiles found"
                )
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"[spotify_community] HTTP {e.response.status_code} from {board_url}"
                )
            except Exception as e:
                logger.warning(f"[spotify_community] Failed board page: {e}")

            await asyncio.sleep(1)

        return threads

    async def _scrape_thread(
        self, client: httpx.AsyncClient, thread_title: str, thread_url: str
    ) -> List[Dict]:
        """Scrape a single thread page for user replies."""
        response = await client.get(thread_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        posts = []
        message_bodies = soup.select(".lia-message-body-content")

        for i, body in enumerate(message_bodies):
            text = body.get_text(strip=True)
            if not text or len(text) < 20:
                continue

            # Try to find the parent message container for author/date
            # The actual DOM uses .lia-quilt-idea-message as the container
            # that holds both the body and the timestamp in sibling quilt-rows.
            parent = (
                body.find_parent(class_="lia-quilt-idea-message")
                or body.find_parent(class_="lia-message")
                or body.find_parent("div")
            )
            
            author = ""
            posted_at = None

            if parent:
                # Try to find author
                author_el = parent.select_one(
                    ".lia-user-name-link, .UserName a, .lia-component-message-view-widget-author-username a"
                )
                if author_el:
                    author = author_el.get_text(strip=True)

                # Try to find timestamp — .local-friendly-date has the actual
                # datetime in its 'title' attr; .DateTime is the outer wrapper
                # without it.  Try inner first to avoid getting the wrong element.
                time_el = (
                    parent.select_one(".local-friendly-date")
                    or parent.select_one("time")
                    or parent.select_one(".DateTime")
                )
                if time_el:
                    # Actual datetime is stored in the 'title' attribute
                    # e.g. title="2026-04-15T13:34:54+02:00" or title="‎2026-06-11 01:59 PM"
                    dt_str = time_el.get("title") or time_el.get("datetime") or time_el.get_text(strip=True)
                    # Strip leading invisible chars (LRM \u200e etc.)
                    dt_str = dt_str.lstrip("\u200e\u200f\u00a0 ")
                    try:
                        posted_at = datetime.fromisoformat(
                            dt_str.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        # Try common format "2026-06-11 01:59 PM"
                        try:
                            posted_at = datetime.strptime(dt_str, "%Y-%m-%d %I:%M %p")
                        except (ValueError, TypeError):
                            pass

            # Use thread URL + reply index as unique ID
            source_id = f"{thread_url}#reply-{i}"

            posts.append({
                "title": thread_title,
                "content": text,
                "author": author,
                "url": thread_url,
                "posted_at": posted_at,
                "source_id": source_id,
            })

        return posts

    def normalize(self, raw: dict) -> FeedbackRecord:
        """Convert a scraped community post into a FeedbackRecord."""
        content = raw.get("content", "")

        posted_at = raw.get("posted_at")
        if posted_at and not isinstance(posted_at, datetime):
            try:
                posted_at = datetime.fromisoformat(str(posted_at))
            except (ValueError, TypeError):
                posted_at = None

        return FeedbackRecord(
            source="spotify_community",
            source_id=raw.get("source_id", self.content_hash(content)),
            country=None,  # Community posts don't have country info
            author=raw.get("author") or None,
            content=content,
            url=raw.get("url"),
            posted_at=posted_at,
            raw_json=json.dumps(raw, ensure_ascii=False, default=str),
        )

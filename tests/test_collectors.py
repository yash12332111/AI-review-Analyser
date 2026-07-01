"""
Integration tests for data collectors.
Tests mock out the actual network calls and verify orchestration, normalization, and deduplication.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.collectors.appstore_collector import AppStoreCollector
from app.collectors.playstore_collector import PlayStoreCollector
from app.collectors.spotify_community_collector import SpotifyCommunityCollector
from app.collectors.trustpilot_collector import TrustpilotCollector
from app.collectors.orchestrator import CollectionOrchestrator
from app.database.db_manager import DatabaseManager


@pytest.fixture
def db(tmp_path):
    """Provide a fresh, initialized database for each test."""
    db_path = tmp_path / "test.db"
    manager = DatabaseManager(str(db_path))
    manager.initialize()
    yield manager
    manager.close()


# --- Mock Data ---

MOCK_APPSTORE_RSS = {
    "feed": {
        "entry": [
            {
                # App metadata (should be skipped by collector because no im:rating)
                "id": {"label": "metadata"}
            },
            {
                "id": {"label": "12345"},
                "author": {"name": {"label": "iOS User"}},
                "title": {"label": "Great App"},
                "content": {"label": "I love Spotify on my iPhone. This is a long enough review to pass the 20 char limit."},
                "im:rating": {"label": "5"},
                "updated": {"label": "2024-01-15T12:00:00-07:00"}
            }
        ]
    }
}

MOCK_PLAYSTORE_REVIEWS_EN = [
    {
        "reviewId": "en_review_001",
        "userName": "English User",
        "content": "Works fine but sometimes offline downloads fail to sync. Just need it to be longer.",
        "score": 4,
        "at": datetime(2024, 1, 15, 12, 0, 0)
    }
]

MOCK_PLAYSTORE_REVIEWS_DE = [
    {
        "reviewId": "de_review_001",
        "userName": "German User",
        "content": "Die App ist immer mehr verbugt und spinnt rum. Brauche dringend ein Update.",
        "score": 2,
        "at": datetime(2024, 1, 15, 12, 0, 0)
    }
]

MOCK_COMMUNITY_BOARD_HTML = """
<html><body>
    <div class="custom-message-tile">
        <a href="/t5/user/viewprofilepage/user-id/123"></a>
        <a href="/t5/Ongoing-Issues/Test-Thread/idi-p/12345">Test Thread Title Is Long Enough</a>
    </div>
    <div class="custom-message-tile">
        <a href="/t5/user/viewprofilepage/user-id/456"></a>
        <a href="/t5/Ongoing-Issues/Another-Thread/idi-p/67890">Another Thread Title Is Also Long Enough</a>
    </div>
</body></html>
"""

MOCK_COMMUNITY_THREAD_HTML = """
<html><body>
    <div class="lia-message">
        <div class="lia-message-body-content">
            We've been receiving reports from users who say the app won't play on their devices. The Play button only appears as loading.
        </div>
        <a class="lia-user-name-link">ModUser</a>
    </div>
    <div class="lia-message">
        <div class="lia-message-body-content">
            I'm having the same issue on my phone. Tried reinstalling but it doesn't help at all.
        </div>
        <a class="lia-user-name-link">RegularUser</a>
    </div>
</body></html>
"""

MOCK_TRUSTPILOT_HTML = """
<html><body>
    <article class="review-card">
        <h2 class="review-content__title">Terrible support</h2>
        <p class="review-content__text">They double charged me and support took weeks to respond. Very frustrating experience.</p>
        <div class="consumer-information__name">Angry Customer</div>
        <time datetime="2024-01-15T12:00:00Z"></time>
    </article>
</body></html>
"""


# --- Tests ---

@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_appstore_collector(mock_get, db):
    """Test AppStoreCollector fetches and normalizes data properly."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_APPSTORE_RSS
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    collector = AppStoreCollector(db)
    since = datetime.utcnow() - timedelta(days=1)

    with patch("app.config.settings.settings.APP_STORE_COUNTRIES", ["US"]):
        raw_items = await collector.collect(since)

    assert len(raw_items) == 1
    assert raw_items[0]["_country"] == "US"

    record = collector.normalize(raw_items[0])
    assert record.source == "appstore"
    assert record.country == "US"
    assert record.author == "iOS User"
    assert "Great App" in record.content
    assert "long enough" in record.content
    assert record.posted_at is not None


@pytest.mark.asyncio
@patch("app.collectors.playstore_collector.reviews")
async def test_playstore_collector_multicountry(mock_reviews, db):
    """Test PlayStoreCollector uses different languages per country
    and produces genuinely different reviews per market."""
    # Return different reviews for different lang values
    def side_effect(app_id, lang=None, country=None, sort=None, count=None):
        if lang == "de":
            return (MOCK_PLAYSTORE_REVIEWS_DE, None)
        return (MOCK_PLAYSTORE_REVIEWS_EN, None)

    mock_reviews.side_effect = side_effect

    collector = PlayStoreCollector(db)
    since = datetime.utcnow() - timedelta(days=1)

    with patch("app.config.settings.settings.PLAY_STORE_COUNTRIES", ["US", "DE"]):
        raw_items = await collector.collect(since)

    # Should have 2 distinct reviews (different IDs)
    assert len(raw_items) == 2
    countries = {r["_country"] for r in raw_items}
    assert countries == {"US", "DE"}

    # Verify the German review was fetched with lang='de'
    de_items = [r for r in raw_items if r["_country"] == "DE"]
    assert len(de_items) == 1
    assert de_items[0]["reviewId"] == "de_review_001"


@pytest.mark.asyncio
async def test_spotify_community_collector(db):
    """Test SpotifyCommunityCollector discovers threads and scrapes replies."""
    collector = SpotifyCommunityCollector(db)

    # Mock the httpx client — accepts self (AsyncClient instance) + url
    async def mock_get(self_or_url, url=None, **kwargs):
        # Handle both patch as method (self, url) and direct call (url)
        actual_url = url if url is not None else self_or_url
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "bd-p" in actual_url or "idb-p" in actual_url:
            resp.text = MOCK_COMMUNITY_BOARD_HTML
        elif "idi-p" in actual_url:
            resp.text = MOCK_COMMUNITY_THREAD_HTML
        else:
            resp.text = "<html></html>"
        return resp

    with patch("httpx.AsyncClient.get", new=mock_get):
        raw_items = await collector.collect(datetime.utcnow() - timedelta(days=1))

    # Should have found 2 threads from mock board, each with 2 replies
    assert len(raw_items) == 4  # 2 threads × 2 replies each

    # Check normalization
    record = collector.normalize(raw_items[0])
    assert record.source == "spotify_community"
    assert record.country is None
    assert "reports from users" in record.content


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_trustpilot_collector(mock_get, db):
    mock_resp = MagicMock()
    mock_resp.text = MOCK_TRUSTPILOT_HTML
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    collector = TrustpilotCollector(db)
    since = datetime.utcnow() - timedelta(days=1)

    raw_items = await collector.collect(since)
    # It scrapes 2 pages, so we get 2 results
    assert len(raw_items) == 2

    record = collector.normalize(raw_items[0])
    assert record.source == "trustpilot"
    assert record.author == "Angry Customer"
    assert "double charged me" in record.content


@pytest.mark.asyncio
@patch.object(AppStoreCollector, "collect")
@patch.object(PlayStoreCollector, "collect")
@patch.object(SpotifyCommunityCollector, "collect")
@patch.object(TrustpilotCollector, "collect")
async def test_orchestrator_handles_failure(mock_trustpilot, mock_community, mock_play, mock_app, db):
    """Test the Orchestrator runs all and handles failure (Edge case #12)."""
    mock_app.return_value = [{"title": {"label": "Title"}, "content": {"label": "This is a valid long review for App Store."}, "_country": "US", "id": {"label": "1"}}]
    mock_play.return_value = [{"content": "This is a valid long review for Play Store.", "_country": "US", "reviewId": "2"}]
    mock_community.return_value = [{"title": "Community thread", "content": "Community thread that is long enough for testing.", "source_id": "3", "url": "https://example.com", "author": "", "posted_at": None}]

    # Simulate a crash in Trustpilot
    mock_trustpilot.side_effect = Exception("Trustpilot blocked scraper")

    orchestrator = CollectionOrchestrator(db)
    logs = await orchestrator.run_all()

    # 3 successes
    assert logs["appstore"].status == "success"
    assert logs["appstore"].records_new == 1
    assert logs["playstore"].status == "success"
    assert logs["spotify_community"].status == "success"

    # 1 failure — but pipeline continued
    assert logs["trustpilot"].status == "failed"
    assert "Trustpilot blocked" in logs["trustpilot"].error_message

    # Verify DB has exactly 3 records
    cursor = db.conn.execute("SELECT COUNT(*) as count FROM feedback")
    assert cursor.fetchone()["count"] == 3


@pytest.mark.asyncio
@patch.object(AppStoreCollector, "collect")
async def test_deduplication(mock_app, db):
    """Test deduplication logic in the db_manager via base collector."""
    mock_item = {
        "title": {"label": "Great"},
        "content": {"label": "This is a valid long review for App Store."},
        "_country": "US",
        "id": {"label": "dedup_123"}
    }

    mock_app.return_value = [mock_item]

    collector = AppStoreCollector(db)

    # First run
    log1 = await collector.run()
    assert log1.records_new == 1

    # Second run — same item
    log2 = await collector.run()
    assert log2.records_new == 0  # Should be skipped!

    # DB count should be 1
    cursor = db.conn.execute("SELECT COUNT(*) as count FROM feedback")
    assert cursor.fetchone()["count"] == 1

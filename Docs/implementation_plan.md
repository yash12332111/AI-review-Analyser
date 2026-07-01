# Implementation Plan — AI-Powered User Feedback Intelligence System

> **Purpose:** This is the step-by-step build guide. Each phase lists exactly what to create, in what order, with file paths, commands, dependencies, and acceptance criteria. Check off tasks as you go.
>
> **Related Docs:**
> - [Architecture.md](./Architecture.md) — Technical blueprint and system design
> - [Explanation.md](./Explanation.md) — How the product works with examples
> - [Problem_statement.md](./Problem_statement.md) — Why we're building this

---

## Build Order Overview

```
Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4 ──→ Phase 4.5 ──→ Phase 5 ──→ Phase 6 ──→ Phase 7
Foundation   Collect     Classify     Store &      Theme         Dashboard    RAG Chat    Automate
& Scaffold   Data        with AI      Embed        Clustering    Frontend     Interface   & Harden

  ~1 day      ~2 days     ~1 day       ~1 day       ~1 day        ~2 days      ~2 days     ~1 day
```

> Each phase depends on the one before it. Do not skip ahead — later phases import modules built in earlier ones.

---

## Phase 1 — Foundation & Project Scaffolding

> **Goal:** Create the project skeleton, install dependencies, set up the database, and build the core data models that every other phase depends on.
>
> **Estimated Time:** ~1 day
>
> **Depends On:** Nothing — this is the starting point

---

### Task 1.1 — Create the directory structure

Create every folder and `__init__.py` placeholder so all imports work from day one.

**Action:** Create these directories and files:

```
AI Review Analyser/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── cli.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── feedback.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── schema.sql
│   │   └── db_manager.py
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base_collector.py
│   │   ├── appstore_collector.py
│   │   ├── playstore_collector.py
│   │   ├── spotify_community_collector.py
│   │   ├── trustpilot_collector.py
│   │   └── orchestrator.py
│   ├── classifier/
│   │   ├── __init__.py
│   │   ├── prompts.py
│   │   └── engine.py
│   ├── embeddings/
│   │   ├── __init__.py
│   │   └── embed_pipeline.py
│   ├── clustering/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── prompts.py
│   ├── retrieval/
│   │   ├── __init__.py
│   │   └── retriever.py
│   ├── rag/
│   │   ├── __init__.py
│   │   └── chat_engine.py
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── pipeline.py
│   │   └── scheduler.py
│   └── api/
│       ├── __init__.py
│       ├── dashboard_routes.py
│       ├── chat_routes.py
│       └── health_routes.py
├── frontend/
│   ├── index.html
│   ├── chat.html
│   ├── css/
│   │   └── styles.css
│   └── js/
│       ├── dashboard.js
│       └── chat.js
├── data/                          # .gitignore this — created at runtime
├── tests/
│   ├── __init__.py
│   ├── test_db_manager.py
│   ├── test_collectors.py
│   ├── test_classifier.py
│   ├── test_embeddings.py
│   ├── test_retriever.py
│   └── test_api.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

**Acceptance:** Running `python -c "from app.config import settings"` does not raise an ImportError.

---

### Task 1.2 — Create requirements.txt

**File:** `requirements.txt`

```txt
# Core
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.9.0
pydantic-settings==2.5.0
python-dotenv==1.0.1

# Data Collection
httpx==0.27.0
beautifulsoup4==4.12.3
google-play-scraper==1.2.7

# AI & Embeddings
groq==0.11.0
chromadb==0.5.5
sentence-transformers==3.0.1
hdbscan==0.8.38
scikit-learn==1.5.1

# Scheduling
apscheduler==3.10.4

# Testing
pytest==8.3.2
pytest-asyncio==0.23.8

# Utilities
aiofiles==24.1.0
```

**Command to install:**
```bash
pip install -r requirements.txt
```

**Acceptance:** `pip install` completes without errors.

---

### Task 1.3 — Create .env.example and .gitignore

**File:** `.env.example`

```env
# === API Keys ===
GROQ_API_KEY=your_groq_api_key_here
GROQ_API_KEYS=key1,key2  # Optional: Comma-separated list for rate-limit rotation

# Collector Settings
APP_STORE_COUNTRIES=["US", "GB", "IN", "BR", "DE"]
PLAY_STORE_COUNTRIES=["US", "GB", "IN", "BR", "DE"]

# === Database ===
SQLITE_DB_PATH=data/feedback.db
CHROMA_PERSIST_DIR=data/chroma

# === Model Config ===
GROQ_MODEL=llama-3.3-70b-versatile
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2

# === Collection & Classification Caps ===
MAX_RECORDS_PER_SOURCE_PER_RUN=200
MAX_CLASSIFICATIONS_PER_RUN=900
MIN_PATTERN_SAMPLE=10

# === Scheduler ===
COLLECTION_HOUR=0
COLLECTION_MINUTE=0
```

**File:** `.gitignore`

```gitignore
# Data (runtime-generated)
data/
*.db

# Environment
.env
__pycache__/
*.pyc

# IDE
.vscode/
.idea/

# OS
.DS_Store
```

**Acceptance:** `.env` file is never committed to git.

---

### Task 1.4 — Build the configuration system

**File:** `app/config/settings.py`

Create a Pydantic Settings class that reads all config from `.env`:

```python
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # API Keys
    GROQ_API_KEY: str = ""
    GROQ_API_KEYS: str = ""                    # Comma-separated list for throughput rotation
    
    # Target markets
    APP_STORE_COUNTRIES: list[str] = ["US", "GB", "IN", "BR", "DE"]
    PLAY_STORE_COUNTRIES: list[str] = ["US", "GB", "IN", "BR", "DE"]

    # Database
    SQLITE_DB_PATH: str = "data/feedback.db"
    CHROMA_PERSIST_DIR: str = "data/chroma"

    # Model Config
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # Collection & Classification Caps
    MAX_RECORDS_PER_SOURCE_PER_RUN: int = 200
    MAX_CLASSIFICATIONS_PER_RUN: int = 900
    MIN_PATTERN_SAMPLE: int = 10

    # Scheduler
    COLLECTION_HOUR: int = 0
    COLLECTION_MINUTE: int = 0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

**Acceptance:** After copying `.env.example` to `.env` and filling in at least `GROQ_API_KEY` (or `GROQ_API_KEYS`), running `python -c "from app.config.settings import settings; print(settings.GROQ_MODEL)"` prints `llama-3.3-70b-versatile`.

---

### Task 1.5 — Create the SQLite schema

**File:** `app/database/schema.sql`

Copy the full schema from [Architecture.md — Section 1.3](./Architecture.md#13-sqlite-schema-design). This includes 4 tables:

| Table | Purpose |
|-------|---------|
| `feedback` | Stores raw collected reviews from all 4 sources |
| `classifications` | Stores the 11-field AI classification for each review |
| `collection_runs` | Logs each nightly collection run (per source) |
| `daily_summaries` | Stores auto-generated delta summaries |

Plus 7 indexes for dashboard query performance.

**Acceptance:** The SQL file executes without errors when run against a fresh SQLite database.

---

### Task 1.6 — Build Pydantic data models

**File:** `app/models/feedback.py`

Create these Pydantic models:

```python
class FeedbackRecord(BaseModel):
    """Raw feedback from any source — this is what collectors produce."""
    id: str                        # UUID, generated on creation
    source: str                    # appstore | playstore | spotify_community | trustpilot
    country: Optional[str] = None  # e.g., 'US', 'GB', 'IN' (for app stores)
    source_id: str                 # Original ID from the platform
    author: str | None = None
    content: str
    url: str | None = None
    posted_at: datetime | None = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    raw_json: str | None = None

class ClassificationResult(BaseModel):
    """11-field AI classification output — this is what the classifier produces."""
    feedback_id: str
    topic: str | None = None
    core_complaint: str | None = None
    trust_level: Literal["high", "medium", "low", "broken"] | None = None
    sentiment: Literal["positive", "negative", "mixed", "neutral"]
    frustration_intensity: Literal["mild", "moderate", "severe", "churned"] | None = None
    user_job_to_be_done: str | None = None
    repeat_listen_reason: str | None = None
    workaround_mentioned: bool = False
    workaround_description: str | None = None
    behaviour_pattern: str | None = None
    pattern_evidence: str | None = None
    unmet_need: str | None = None

class ClassifiedFeedback(BaseModel):
    """Joined model — feedback + classification. Used in API responses."""
    # All fields from FeedbackRecord + ClassificationResult

class CollectionRunLog(BaseModel):
    """Metadata for a single collection run."""
    source: str
    started_at: datetime
    completed_at: datetime | None = None
    records_fetched: int = 0
    records_new: int = 0
    status: Literal["running", "success", "failed"]
    error_message: str | None = None

class DashboardFilters(BaseModel):
    """Query parameters for dashboard API endpoints."""
    date_from: date | None = None
    date_to: date | None = None
    source: str | None = None
    sentiment: str | None = None
    topic: str | None = None

class ChatFilters(BaseModel):
    """Query parameters for RAG chat."""
    date_range: str | None = "last_7_days"   # today | last_7_days | last_30_days | custom
    date_from: date | None = None
    date_to: date | None = None
    source: str | None = None
    sentiment: str | None = None
    topic: str | None = None
    signal_type: str | None = None           # workarounds_only | churned_only | high_frustration_only
```

**Acceptance:** All models instantiate correctly with valid data and raise `ValidationError` with invalid enum values.

---

### Task 1.7 — Build the DatabaseManager

**File:** `app/database/db_manager.py`

A class that wraps all SQLite interactions:

```python
class DatabaseManager:
    def __init__(self, db_path: str):
        """Initialize connection and create tables if they don't exist."""

    def initialize(self) -> None:
        """Read schema.sql and execute all CREATE statements."""

    def insert_feedback(self, record: FeedbackRecord) -> bool:
        """INSERT OR IGNORE — returns True if new, False if duplicate."""

    def insert_classification(self, result: ClassificationResult) -> None:
        """Store classification result, update feedback.classified_at."""

    def get_unclassified(self, limit: int = 50) -> list[FeedbackRecord]:
        """Return feedback records where classified_at IS NULL AND skipped = 0."""

    def mark_skipped(self, feedback_id: str) -> None:
        """Set skipped = 1 on a review (off-topic/all-null). Retained for audit,
        excluded from future classification runs and clustering."""

    def get_last_collection_time(self, source: str) -> datetime | None:
        """Return the max completed_at from collection_runs for this source."""

    def log_collection_run(self, log: CollectionRunLog) -> int:
        """Insert a collection run log entry, return the run ID."""

    def query_feedback(self, filters: DashboardFilters, limit: int = 50, offset: int = 0) -> list[ClassifiedFeedback]:
        """Parameterized query joining feedback + classifications with filters."""

    def get_sentiment_distribution(self, filters: DashboardFilters) -> dict[str, int]:
        """COUNT grouped by sentiment."""

    def get_complaint_ranking(self, filters: DashboardFilters) -> list[dict]:
        """COUNT grouped by core_complaint, ordered DESC, with week-over-week delta."""

    def get_topic_distribution(self, filters: DashboardFilters) -> dict[str, int]:
        """COUNT grouped by topic."""

    def get_workarounds(self, filters: DashboardFilters, limit: int = 20) -> list[ClassifiedFeedback]:
        """Return records where workaround_mentioned = 1."""

    def get_topic_trends(self, days: int = 30) -> list[dict]:
        """Daily COUNT by topic for the last N days."""

    def get_summary_stats(self, filters: DashboardFilters) -> dict:
        """Total feedback, by source, by sentiment — high-level summary."""

    def insert_daily_summary(self, summary: dict) -> None:
        """Store the nightly delta summary."""
```

**Acceptance:**
```bash
python -c "
from app.database.db_manager import DatabaseManager
db = DatabaseManager('data/test.db')
db.initialize()
print('✅ All tables created successfully')
"
```

---

### Task 1.8 — Create the FastAPI app skeleton

**File:** `app/main.py`

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="AI Feedback Intelligence", version="1.0.0")

# Serve frontend static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Health check
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

# Routers will be added in later phases:
# from app.api.dashboard_routes import router as dashboard_router
# from app.api.chat_routes import router as chat_router
# app.include_router(dashboard_router, prefix="/api/dashboard")
# app.include_router(chat_router, prefix="/api/chat")
```

**Command to run:**
```bash
uvicorn app.main:app --reload --port 8000
```

**Acceptance:** `http://localhost:8000/api/health` returns `{"status": "healthy", "version": "1.0.0"}`.

---

### Task 1.9 — Write unit tests for the database

**File:** `tests/test_db_manager.py`

Test cases:
- `test_initialize_creates_tables` — verify all 4 tables exist after `initialize()`
- `test_insert_feedback` — insert a record, verify it's retrievable
- `test_duplicate_feedback_ignored` — insert same `(source, source_id)` twice, verify only 1 exists
- `test_insert_classification` — insert classification, verify join query works
- `test_get_unclassified` — insert 3 feedback records, classify 1, verify `get_unclassified()` returns 2
- `test_filters` — insert records with different sources/sentiments, verify filter queries

**Command to run:**
```bash
pytest tests/test_db_manager.py -v
```

**Acceptance:** All tests pass.

---

## Phase 2 — Data Collection Pipeline

> **Goal:** Build collectors for all 4 sources with incremental collection, normalize to a unified format, and orchestrate concurrent runs.
>
> **Estimated Time:** ~2 days
>
> **Depends On:** Phase 1 (DatabaseManager, FeedbackRecord model, settings)

---

### Task 2.1 — Build the AbstractCollector base class

**File:** `app/collectors/base_collector.py`

```python
from abc import ABC, abstractmethod
from datetime import datetime
from app.models.feedback import FeedbackRecord, CollectionRunLog
from app.database.db_manager import DatabaseManager

class AbstractCollector(ABC):
    source_name: str  # e.g., "appstore", "playstore"

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def run(self) -> CollectionRunLog:
        """
        Full lifecycle:
        1. Get last collection timestamp from DB
        2. Call self.collect(since) to fetch raw data (capped at settings.MAX_RECORDS_PER_SOURCE_PER_RUN)
        3. Normalize each raw item into FeedbackRecord
        4. Insert into DB (dedup handled by DB layer)
        5. Log the run and return CollectionRunLog
        """

    @abstractmethod
    async def collect(self, since: datetime) -> list[dict]:
        """Fetch raw data from the source platform since the given timestamp."""

    @abstractmethod
    def normalize(self, raw: dict) -> FeedbackRecord:
        """Convert one source-specific raw dict into a unified FeedbackRecord."""
```

**Acceptance:** The base class can be subclassed and the `run()` method correctly calls the lifecycle hooks.

---

### Task 2.2 — Build the App Store Collector (Multi-Country)

**File:** `app/collectors/appstore_collector.py`

**Action:**
- Uses `httpx` to fetch the official Apple customer reviews RSS JSON feed.
- Iterates over `APP_STORE_COUNTRIES` (e.g. `['us', 'gb', 'in']`), tagging each review with its country.
- Endpoint format: `https://itunes.apple.com/{country}/rss/customerreviews/id=324684580/sortBy=mostRecent/json`
- Normalizes into `FeedbackRecord` with `source="appstore"` and sets `country`.

**Acceptance:** Returns new App Store reviews across multiple countries.

---

### Task 2.3 — Build the Play Store Collector (Multi-Country)

**File:** `app/collectors/playstore_collector.py`

**Action:**
- Uses `google-play-scraper` to fetch reviews.
- Iterates through `PLAY_STORE_COUNTRIES` in config.
- Normalizes into `FeedbackRecord` with `source="playstore"` and sets `country`.

**Acceptance:** Returns Android reviews across multiple countries with correct `country` tags.

---

### Task 2.4 — Build the Spotify Community Collector

**File:** `app/collectors/spotify_community_collector.py`

**What it does:**
- Uses `httpx` + `BeautifulSoup4` to scrape `community.spotify.com`
- Targets forum categories: "Music Discovery", "Your Library", "Spotify Features"
- Extracts post content, author, and timestamp
- Filters posts created after `since`
- Normalizes into `FeedbackRecord` with `source="spotify_community"`

**Required config:** None

**Acceptance:** Returns forum posts as `FeedbackRecord` objects.

---


---

### Task 2.8 — Build the CollectionOrchestrator

**File:** `app/collectors/orchestrator.py`

```python
class CollectionOrchestrator:
    def __init__(self, db: DatabaseManager):
        self.collectors = [
            AppStoreCollector(db),
            PlayStoreCollector(db),
            SpotifyCommunityCollector(db),
            TrustpilotCollector(db),
        ]

    async def run_all(self) -> dict[str, CollectionRunLog]:
        """Run all 4 collectors concurrently using asyncio.gather.
        Return a dict mapping source_name → CollectionRunLog.
        If a collector fails (especially Trustpilot), log the error but don't stop others.
        Enforces MAX_RECORDS_PER_SOURCE_PER_RUN cap per collector."""

    async def run_source(self, source_name: str) -> CollectionRunLog:
        """Run a single collector by name. Useful for manual re-runs."""
```

**Acceptance:**
```bash
python -m app.collect --all
# OR
python -m app.collect --source appstore
```
Both commands run without errors and insert records into the database.

---

### Task 2.9 — Add CLI commands for collection

**File:** `app/cli.py`

Add a `collect` subcommand:
```bash
python -m app.collect --all          # Run all 4 collectors
python -m app.collect --source appstore # Run just App Store
python -m app.collect --source playstore # Run just Play Store
```

**Acceptance:** CLI commands work and print collection results to stdout.

---

### Task 2.10 — Write integration tests

**File:** `tests/test_collectors.py`

- Test each collector with **mocked API responses** (don't hit real APIs in tests)
- Test the orchestrator runs all collectors and handles failures gracefully
- Test deduplication: inserting the same record twice should not create a duplicate

**Acceptance:** `pytest tests/test_collectors.py -v` — all tests pass.

---

### ⚠️ Phase 2 — Edge Cases & Gotchas

| # | Edge Case | What Goes Wrong | How to Handle |
|---|-----------|----------------|---------------|
| 1 | **Collector blocked** | Trustpilot scraper gets HTTP 403 or blocks scraper | Catch the error, log it, mark the source as `failed`, continue with other collectors |
| 2 | **API Rate Limits** | Store scrapers can get rate limited if we request too fast | Build in backoff logic if needed. Keep the `since` timeframe small |
| 3 | **App/Play Store scraper returns stale data** | These libraries sometimes return cached or out-of-order results, not truly "newest first" | Don't rely solely on sort order. Always filter by `posted_at > since` after fetching. Accept that some reviews may be slightly delayed |
| 4 | **Spotify Community HTML structure changes** | The forum redesigns their HTML → BeautifulSoup selectors break → collector returns 0 results | Monitor `records_fetched` count. If a source that normally returns 20+ suddenly returns 0, log a `WARNING`. Have fallback selectors or a manual review flag |
| 5 | **Rate limiting / IP blocking** | Scraping too aggressively → source returns 403 or CAPTCHA | Add configurable delays between requests (e.g., 2 seconds between pages). Use random jitter. Respect `Retry-After` headers |
| 6 | **Empty or garbage content** | A review is just `"👍"` or `"asdfghjkl"` or `"."` | Filter out reviews shorter than 20 characters in the `normalize()` method. Don't store them — they can't be classified |
| 7 | **Cross-platform duplicate content** | A user posts the exact same review on App Store AND the Play Store | Content-hash dedup catches this. Compute `hashlib.sha256(content.strip().lower())` and add a `content_hash` column with a UNIQUE constraint |
| 8 | **First run has no "since" timestamp** | `get_last_collection_time()` returns `None` on the first ever run → collector doesn't know how far back to go | Default to `datetime.utcnow() - timedelta(days=30)` on first run. Configurable via `INITIAL_LOOKBACK_DAYS` setting |
| 9 | **Network timeout mid-collection** | WiFi drops during an API call → partial data collected | Each record is inserted individually. The run log shows `records_fetched` vs `records_new`. A partial run is fine — the next run picks up from where the last successful timestamp was |
| 10 | **Non-English reviews** | App Store and Play Store return reviews in all languages | Add a `LANGUAGE_FILTER = "en"` setting. Filter in the collector where possible (App Store and Play Store support language params). For scraped sources, use a simple heuristic or skip non-ASCII-dominant text |
| 11 | **Collector hangs indefinitely** | A scraper gets stuck on an infinite pagination loop or a socket that never closes | Wrap each collector's `run()` with `asyncio.wait_for(timeout=300)` (5-minute max per source). If it times out, log and mark as `failed` |
| 12 | **One collector failure kills all others** | An unhandled exception in AppStoreCollector propagates and cancels the `asyncio.gather` | Use `asyncio.gather(*tasks, return_exceptions=True)`. This lets other collectors finish even if one throws an exception |

---

### ✅ Phase 2 Checklist

- [ ] `base_collector.py` — AbstractCollector with lifecycle hooks
- [ ] `appstore_collector.py` — fetches multi-country iOS reviews
- [ ] `playstore_collector.py` — fetches multi-country Android reviews
- [ ] `spotify_community_collector.py` — scrapes forum topics
- [ ] `trustpilot_collector.py` — scrapes Trustpilot (with graceful fail)
- [ ] `orchestrator.py` — runs all 4 concurrently with error isolation
- [ ] `cli.py` — `python -m app.collect --all` and `--source <name>` work
- [ ] Integration tests with mocked APIs pass
- [ ] At least one real end-to-end test runs against live APIs and stores data

---

## Phase 3 — AI Classification Engine

> **Goal:** Build the pipeline that takes unclassified feedback and uses Groq (Llama 3.3 70B) to extract 11 open-text fields per review. The model describes what it sees — it does not sort reviews into predefined buckets.
>
> **Estimated Time:** ~1 day
>
> **Depends On:** Phase 1 (DatabaseManager, ClassificationResult model), Phase 2 (data in the feedback table)

---

### Task 3.1 — Write the classification system prompt

**File:** `app/classifier/prompts.py`

This is the most critical piece of the entire system. The prompt must:
1. Define the role clearly ("user feedback analyst for music discovery")
2. List all 11 fields with their types (open-text strings, not enum values)
3. Provide the output JSON schema
4. Include 2–3 few-shot examples for calibration
5. Instruct the model to return `null` for absent fields
6. Instruct the model to extract verbatim evidence from the text
7. **Include this instruction explicitly:** *"Do NOT sort reviews into predefined categories. Describe what is actually in the text. Return null when something is not present."*

```python
CLASSIFICATION_SYSTEM_PROMPT = """You are a user feedback analyst specializing in music discovery behavior.
Given a user review about Spotify, extract the following 11 fields.
Return ONLY valid JSON matching the schema below. No markdown, no explanation.
If a field is not clearly present in the text, use null.

Do NOT sort reviews into predefined categories. Describe what is
actually in the text. Return null when something is not present.
...
"""

# Few-shot examples for consistent extraction (use varied, natural-language
# values — not a fixed vocabulary)
FEW_SHOT_EXAMPLES = [...]
```

**Acceptance:** The prompt, when sent to Groq with a sample review, returns valid JSON matching the `ClassificationResult` schema.

---

### Task 3.2 — Build the ClassificationEngine

**File:** `app/classifier/engine.py`

```python
class ClassificationEngine:
    def __init__(self, db: DatabaseManager):
        # Reads GROQ_API_KEYS (comma-separated list) or falls back to single GROQ_API_KEY
        # All keys use the same model and prompt — keys are throughput only
        self.api_keys = [...]  # parsed from settings
        self.current_key_idx = 0
        self.client = Groq(api_key=self.api_keys[0])
        self.db = db

    async def classify_batch(self, batch_size: int = 50) -> int:
        """
        1. Fetch unclassified records from DB (limit=batch_size, excluding skipped=1)
        2. For each record, call classify_single()
        3. On success: store classification in DB, set classified_at
        4. On off-topic/all-null None: call db.mark_skipped(feedback_id)
        5. On TPD None: rotate key via _rotate_key(); if all exhausted, halt gracefully
        6. Return count of successfully classified records
        """

    async def classify_single(self, content: str, feedback_id: str) -> ClassificationResult | None:
        """
        1. Skip if content < 20 characters
        2. Build messages (system prompt + few-shot + user content)
        3. Call Groq API with temperature=0.1, response_format=json
        4. Parse JSON response
        5. Validate against ClassificationResult model
        6. Retry up to 2x on invalid JSON
        7. Return ClassificationResult or None on failure
        """

    def _rotate_key(self) -> bool:
        """Switch to the next API key in the list. Returns True if a key was
        available, False if all exhausted (triggers batch halt)."""

    def _build_messages(self, content: str) -> list[dict]:
        """Construct the system + few-shot + user message list."""

    def _parse_and_validate(self, raw_json: str, feedback_id: str) -> ClassificationResult:
        """Parse JSON string, fuzzy-map enum values, validate with Pydantic."""
```

**Key implementation details:**
- **Multi-key rotation:** Reads `GROQ_API_KEYS` (comma-separated) at init. On TPD exhaustion (daily token limit 429), calls `_rotate_key()` to switch to the next key. RPM throttles (short-interval 429s) are handled by the Groq client's built-in retry and do NOT trigger rotation. **All keys use the same model and prompt — keys are a throughput mechanism only.**
- **Skip flag:** When `classify_single()` returns `None` for content reasons (off-topic / all-null), `classify_batch()` calls `db.mark_skipped(feedback_id)` setting `skipped = 1`. The review is retained for audit but excluded from future runs and clustering. A TPD-caused `None` does NOT mark the review as skipped — it stays queued for the next run.
- **Daily cap:** Default limit is `MAX_CLASSIFICATIONS_PER_RUN = 900` (leaves headroom under Groq's 1,000/day free tier). Unclassified overflow is picked up on the next nightly run, oldest-first.
- **Temperature:** 0.1 (we want consistent, factual classification — not creative)
- **Response format:** `{"type": "json_object"}` in the Groq API call
- **Retry logic:** On invalid JSON → retry with appended instruction "Return ONLY valid JSON"
- **Rate limiting:** 2-second delay between API calls to stay within Groq free tier RPM limits
- **Timeout:** 30 seconds per request
- **Error handling:** RPM 429 → Groq client auto-retry; TPD 429 → key rotation; 500 → skip and log

**Acceptance:**
```bash
python -m app.classify --batch-size 10
# Should classify 10 records and print results
```

---

### Task 3.3 — Add CLI command for classification

**File:** Update `app/cli.py`

```bash
python -m app.classify --batch-size 50    # Classify up to 50 unclassified records
python -m app.classify --all              # Classify everything unclassified
```

**Acceptance:** CLI runs, classifies records, prints success/failure counts.

---

### Task 3.4 — Write tests for classification

**File:** `tests/test_classifier.py`

- `test_prompt_produces_valid_json` — send a real review to Groq, verify JSON parses
- `test_validation_catches_bad_enums` — feed in JSON with `trust_level: "banana"`, verify rejection
- `test_short_content_skipped` — content < 20 chars returns None
- `test_retry_on_invalid_json` — mock a first invalid response, verify retry succeeds
- `test_batch_classification` — insert 5 unclassified records, run batch, verify 5 classified

**Acceptance:** `pytest tests/test_classifier.py -v` — all tests pass.

---

### ⚠️ Phase 3 — Edge Cases & Gotchas

| # | Edge Case | What Goes Wrong | How to Handle |
|---|-----------|----------------|---------------|
| 1 | **Groq returns markdown-wrapped JSON** | Response is `` ```json\n{...}\n``` `` instead of raw JSON → `json.loads()` fails | Strip markdown code fences before parsing: `response.strip().removeprefix('```json').removesuffix('```').strip()` |
| 2 | **Groq returns extra text before/after JSON** | Response is `"Here is the analysis:\n{...}"` | Use regex to extract the first `{...}` block: `re.search(r'\{.*\}', response, re.DOTALL)` |
| 3 | **Groq RPM rate limit (429)** | Free tier allows ~30 requests/minute. Batch of 50 reviews hits this immediately | Groq client auto-retries with 1-2s backoff. This does NOT trigger key rotation |
| 3a | **Groq TPD daily limit (429)** | Free tier has ~100k tokens/day. Large batch exhausts the daily quota | Rotate to next API key via `_rotate_key()`. If all keys exhausted, halt batch gracefully and save progress. Unclassified reviews stay queued |
| 4 | **Groq returns enum values not in our schema** | LLM outputs `"trust_level": "very low"` instead of `"low"` | In `_parse_and_validate()`, add a fuzzy matching step before Pydantic validation. Map common variants: `"very low"` → `"low"`, `"extremely frustrated"` → `"severe"` |
| 5 | **Groq returns `null` for everything** | The review is about something unrelated (e.g., Spotify pricing, not discovery) → all 11 fields are null | If `topic`, `core_complaint`, AND `behaviour_pattern` are all null, mark the record as `skipped = 1` via `db.mark_skipped()` — retained for audit, excluded from clustering. Don't count it in dashboard stats |
| 6 | **Review is about a different product** | An App Store review mentions Apple Music or Pandora, not Spotify | Add a relevance check in the prompt: *"If this review is NOT about Spotify, return `{"off_topic": true}`"*. Return None → caller marks `skipped = 1` |
| 7 | **Review is sarcastic or ironic** | `"Spotify's recommendations are SO amazing, I love hearing the same 5 songs every day 🙄"` → LLM might classify as positive | Include in the prompt: *"Detect sarcasm. If the user is being ironic, classify based on their actual sentiment, not the literal words."* Add a few-shot example showing sarcasm |
| 8 | **Very long review exceeds Groq token limit** | A 3,000-word blog post excerpt exceeds the model's input limit → API returns 400 | Truncate content to 2,000 characters before sending to Groq. Preserve the first and last paragraphs (people often state their main point at the beginning and end) |
| 9 | **Groq API is completely down** | 503 or connection refused → entire classification batch fails | Don't crash. Log the error, mark the batch as `failed`, and leave records as unclassified. They'll be picked up on the next nightly run |
| 10 | **Classification drift over time** | The LLM starts extracting differently as the model is updated on Groq's side | Log extraction distributions weekly. If a common topic or complaint value suddenly shifts >20% without a real-world event, investigate. Consider adding a "calibration set" of 10 known reviews you re-classify periodically to check consistency |
| 11 | **Duplicate classification** | A record gets classified twice (e.g., manual run + nightly run overlap) | `classifications.feedback_id` is a PRIMARY KEY. Use `INSERT OR REPLACE` — the second classification simply overwrites the first |
| 12 | **Content in non-English language** | A Spanish review sneaks through → LLM classifies it anyway but with lower accuracy | Add to the prompt: *"If the review is not in English, set all fields to null and set `off_topic` to true."* Or: pre-filter with a language detection library like `langdetect` |

---

### ✅ Phase 3 Checklist

- [ ] `prompts.py` — system prompt with 11 open-text extraction fields, "Do NOT sort" instruction, and few-shot examples
- [ ] `engine.py` — ClassificationEngine with batch + single classification
- [ ] Multi-key Groq rotation (TPD-triggered, configurable key count)
- [ ] Skip flag (`skipped` column in `feedback` table) for off-topic/all-null reviews (retained, excluded from clustering)
- [ ] Pydantic validation of Groq responses
- [ ] Retry logic (2x on invalid JSON, exponential backoff on RPM 429, key rotation on TPD 429)
- [ ] Short content filtering (< 20 chars skipped)
- [ ] CLI command: `python -m app.classify --batch-size 50`
- [ ] Classification tests pass
- [ ] End-to-end: collect → classify → verify classified records in DB

---

## Phase 4 — Storage & Embedding Layer

> **Goal:** Set up ChromaDB, build the embedding pipeline, and create the unified FeedbackRetriever that powers both the dashboard and RAG chat.
>
> **Estimated Time:** ~1 day
>
> **Depends On:** Phase 1 (models, DatabaseManager), Phase 3 (classified data in DB)

---

### Task 4.1 — Build the EmbeddingPipeline

**File:** `app/embeddings/embed_pipeline.py`

```python
class EmbeddingPipeline:
    def __init__(self):
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self.collection = self.chroma_client.get_or_create_collection(
            name="feedback",
            metadata={"hnsw:space": "cosine"}
        )

    def embed_and_store(self, records: list[ClassifiedFeedback]) -> int:
        """
        For each classified record:
        1. Generate embedding from content text
        2. Build metadata dict (source, topic, sentiment, behaviour_pattern, etc.)
        3. Upsert into ChromaDB (idempotent — safe to re-run)
        Return count of records embedded.
        """

    def query(self, text: str, n_results: int = 20, where: dict = None) -> list[dict]:
        """
        1. Embed the query text
        2. Search ChromaDB with cosine similarity
        3. Apply metadata filters (where clause)
        4. Return list of {id, document, metadata, distance}
        """

    def get_collection_count(self) -> int:
        """Return total number of documents in the collection."""
```

**Acceptance:**
```bash
python -c "
from app.embeddings.embed_pipeline import EmbeddingPipeline
ep = EmbeddingPipeline()
print(f'Collection count: {ep.get_collection_count()}')
results = ep.query('algorithm recommendations stuck')
print(f'Found {len(results)} results')
"
```

---

### Task 4.2 — Build the FeedbackRetriever

**File:** `app/retrieval/retriever.py`

```python
class FeedbackRetriever:
    def __init__(self, db: DatabaseManager, embedding_pipeline: EmbeddingPipeline):
        self.db = db
        self.ep = embedding_pipeline

    def structured_query(self, filters: DashboardFilters, limit=50, offset=0) -> list[ClassifiedFeedback]:
        """SQL-based query for dashboard — fast, exact filters."""

    def semantic_search(self, query: str, filters: ChatFilters, top_k=20) -> list[ClassifiedFeedback]:
        """
        1. Convert ChatFilters into ChromaDB where clause
        2. Run embedding_pipeline.query() with where clause
        3. Fetch full ClassifiedFeedback from SQLite by IDs
        4. Return ranked results
        """

    def hybrid_search(self, query: str, filters: ChatFilters, top_k=20) -> list[ClassifiedFeedback]:
        """
        1. Run semantic_search() for meaning-based results
        2. Run structured_query() for metadata-matched results
        3. Merge and deduplicate
        4. Re-rank by combined relevance score
        5. Return top_k results
        """
```

**Acceptance:** Hybrid search returns relevant results with metadata from both databases.

---

### Task 4.3 — Build the backfill script

**File:** Add to `app/cli.py`

```bash
python -m app.embed --backfill          # Embed all classified records not yet in ChromaDB
python -m app.embed --count             # Print how many records are in ChromaDB
```

**Acceptance:** After running backfill, `--count` matches the number of classified records in SQLite.

---

### Task 4.4 — Write tests for embeddings and retrieval

**File:** `tests/test_embeddings.py` and `tests/test_retriever.py`

- `test_embed_and_retrieve` — embed 5 records, query for similar, verify results
- `test_metadata_filtering` — embed records with different sentiments, filter by sentiment
- `test_hybrid_search_merges_results` — verify hybrid combines vector + SQL results

**Acceptance:** `pytest tests/test_embeddings.py tests/test_retriever.py -v` — all pass.

---

### ⚠️ Phase 4 — Edge Cases & Gotchas

| # | Edge Case | What Goes Wrong | How to Handle |
|---|-----------|----------------|---------------|
| 1 | **ChromaDB collection doesn't exist on first run** | `get_collection()` fails → crash before any embeddings happen | Always use `get_or_create_collection()`. Never use `get_collection()` alone |
| 2 | **Embedding model download fails** | `SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")` downloads the model on first use (~470MB). If offline → crash | First-time setup should include `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"` to pre-download. Document this in README |
| 3 | **ChromaDB and SQLite out of sync** | A record exists in SQLite but not in ChromaDB (e.g., embedding failed silently) | The backfill script should compare IDs between both databases and re-embed any missing records. Run periodically or as part of health checks |
| 4 | **Duplicate embeddings** | Running backfill twice → same document embedded twice → duplicate results in search | Use `collection.upsert()` (not `add()`). ChromaDB upsert is idempotent — same ID overwrites |
| 5 | **Very short content produces low-quality embeddings** | A 5-word review like `"hate this app"` produces an embedding that's too generic → matches too many queries | Skip embedding for content shorter than 30 characters. These records are already in SQLite for structured queries but don't add value to semantic search |
| 6 | **ChromaDB `where` filter syntax errors** | ChromaDB has a specific filter syntax (`{"$and": [...]}`) that differs from SQLite. Typos cause silent failures | Build a helper function `build_chroma_filter(chat_filters: ChatFilters) -> dict` that safely constructs valid ChromaDB where clauses. Unit test it with all filter combinations |
| 7 | **Hybrid search returns duplicates** | The same record appears in both the vector search results and the SQL results → it shows up twice in the final list | Deduplicate by `feedback_id` after merging. Keep the higher relevance score |
| 8 | **Query returns 0 results** | A question with very specific filters (e.g., `source=trustpilot, sentiment=positive`) has no matching records | Return a clear message: *"No matching feedback found for these filters. Try broadening your search."* Don't send an empty context to the LLM |
| 9 | **ChromaDB disk space grows unboundedly** | After months of daily embedding, the `data/chroma/` folder grows to many GBs | Monitor disk usage in health checks. ChromaDB supports collection deletion and re-creation. Consider a retention policy (e.g., only keep embeddings from the last 6 months) |
| 10 | **Embedding model version mismatch** | You update `sentence-transformers` and the model produces different embeddings than before → old and new embeddings are incomparable | Pin the `sentence-transformers` version in `requirements.txt`. If you must upgrade, run a full re-embed (`--backfill --force`) to regenerate all embeddings |
| 11 | **Metadata field types in ChromaDB** | ChromaDB metadata values must be `str`, `int`, `float`, or `bool`. Passing `None` or a `list` → error | Convert all `None` metadata values to empty string `""` or omit the key. Never pass `None` as a metadata value |

---

## Phase 4.5 — Theme Clustering Engine

> **Goal:** Group the open-text classification fields into emergent themes so the dashboard can answer pattern-level questions ("what are the most common frustrations?", "which user segments face different challenges?", "what unmet needs emerge consistently?") instead of showing thousands of unique strings.
>
> **Critical design constraint:** Clusters must EMERGE from the data, not be predefined. Do NOT hardcode expected segments, frustration categories, or theme lists anywhere. The clustering groups whatever is actually in the data, then auto-labels the resulting groups. This preserves the same open-extraction principle that governs the classifier — imposing predefined buckets would reintroduce the exact confirmation bias the system was built to avoid.
>
> **Quality Guardrail:** The embedding model must be cross-lingual (e.g., `paraphrase-multilingual-MiniLM-L12-v2`). Monolingual models cluster text by language rather than meaning, which would cause HDBSCAN to create false "German clusters" or "Portuguese clusters" instead of genuine theme clusters spanning across markets.
>
> **Estimated Time:** ~1 day
>
> **Depends On:** Phase 4 (ChromaDB with embeddings), Phase 3 (classified data in DB)

---

### Task 4.5.1 — Create the clustering module

**Action:** Create the `app/clustering/` directory with `__init__.py`, `engine.py`, and `prompts.py`.

**Acceptance:** `python -c "from app.clustering.engine import ThemeClusteringEngine"` does not raise an ImportError.

---

### Task 4.5.2 — Build the ThemeClusteringEngine

**File:** `app/clustering/engine.py`

```python
from hdbscan import HDBSCAN
from sentence_transformers import SentenceTransformer
import numpy as np

class ThemeClusteringEngine:
    def __init__(self, db: DatabaseManager, embedding_pipeline: EmbeddingPipeline):
        self.db = db
        self.ep = embedding_pipeline
        self.groq_client = Groq(api_key=settings.GROQ_API_KEY)

    async def run_clustering(self, cluster_types: list[str] = None) -> dict:
        """
        Cluster open-text fields into emergent themes.
        
        cluster_types: which fields to cluster. Defaults to all:
            ['topic', 'core_complaint', 'behaviour_pattern', 'unmet_need']
        
        For each field:
        1. Pull all non-null values + their feedback_ids from classifications table
        2. Embed each value using sentence-transformers (reuses existing model)
        3. Run HDBSCAN to find density-based clusters (no predefined k)
        4. For each cluster, auto-generate a label via Groq
        5. Select 3-5 representative quotes (verified against source text)
        6. Compute source/country breakdown from feedback table
        7. DELETE old clusters for this type, INSERT new ones (re-runnable)
        8. Store in theme_clusters table
        
        Returns summary dict with cluster counts per type.
        """

    def _cluster_field(self, field_name: str, values: list[dict]) -> list[dict]:
        """
        Run HDBSCAN on embeddings for one field.
        
        - Embed each open-text value
        - Run HDBSCAN(min_cluster_size=settings.MIN_CLUSTER_SIZE, min_samples=settings.MIN_SAMPLES)
        - Return list of {cluster_id, member_values, member_feedback_ids, centroid}
        - Noise points (label=-1) are NOT assigned to any cluster — this is expected
        """

    async def _auto_label_cluster(self, member_values: list[str]) -> str:
        """
        Send a sample of cluster member values to Groq with the labelling prompt.
        Returns a short, neutral label (3-8 words).
        
        IMPORTANT: The prompt must NOT contain a list of expected categories.
        It describes what is there, it does not sort into a preset list.
        """

    def _select_representative_quotes(self, cluster_feedback_ids: list[str], n: int = 5) -> list[str]:
        """
        From the feedback records in this cluster:
        1. Compute centroid of cluster embeddings
        2. Select the N records closest to the centroid
        3. Verify each quote exists in the source text (same validation as RAG chat)
        4. Return verified verbatim quotes
        """

    def _compute_breakdowns(self, feedback_ids: list[str]) -> tuple[dict, dict]:
        """
        Query feedback table for the given IDs.
        Return (sources_breakdown, countries_breakdown) as dicts.
        """
```

**Key implementation details:**
- **HDBSCAN over k-means:** HDBSCAN automatically determines the number of clusters from data density — no predefined `k`. This aligns with the emergent-theme constraint.
- **Noise tolerance:** HDBSCAN labels some points as noise (-1). This is correct — not every review fits neatly into a theme. Log the noise percentage but don't force-assign noise points.
- **Re-runnability:** Each run DELETEs old clusters for the types being clustered, then INSERTs fresh ones. The `run_id` links to `clustering_runs` for traceability.
- **Groq usage:** Only for auto-labelling (one call per cluster, ~5-20 clusters per field = ~20-80 calls total). Well within free-tier limits since values are short.

**Acceptance:**
```bash
python -m app.cluster
# Should print: "Clustered 4 fields: topic (8 clusters), core_complaint (6 clusters), ..."
```

---

### Task 4.5.3 — Write the auto-labelling prompts

**File:** `app/clustering/prompts.py`

```python
CLUSTER_LABEL_PROMPT = """These user {field_type} values were grouped together by semantic similarity.
They all express a related theme, but in different words.

Here are the values in this cluster:
{member_values}

Give a short, neutral label (3-8 words) that describes the common theme.
Do NOT impose a predefined category — describe what is actually there.
Do NOT use generic labels like "General Feedback" — be specific to what these values share.

Return ONLY the label text, nothing else."""
```

**Critical rule:** This prompt must NEVER contain a list of expected labels or categories. It describes what emerges, not what we expect to find.

**Acceptance:** Prompt generates specific, descriptive labels (e.g., "Algorithm repeats same artists" not "Recommendation Issues").

---

### Task 4.5.4 — Add clustering settings to configuration

**File:** Update `app/config/settings.py`

```python
# Clustering (Phase 4.5)
MIN_CLUSTER_SIZE: int = 5          # HDBSCAN minimum cluster size — clusters smaller than this are treated as noise
MIN_SAMPLES: int = 3               # HDBSCAN min_samples parameter — higher = more conservative clustering
CLUSTER_FIELDS: list[str] = ["topic", "core_complaint", "behaviour_pattern", "unmet_need"]
MAX_LABEL_SAMPLES: int = 20        # Max member values sent to Groq for labelling (keeps prompt short)
```

**Acceptance:** Settings load correctly.

---

### Task 4.5.5 — Add CLI command for clustering

**File:** Update `app/cli.py`

```bash
python -m app.cluster                           # Run clustering on all 4 fields
python -m app.cluster --field topic             # Cluster just one field
python -m app.cluster --field core_complaint    # Cluster just complaints
```

**Acceptance:** CLI command runs clustering and prints results.

---

### Task 4.5.6 — Add theme_clusters and clustering_runs tables to schema

**File:** Update `app/database/schema.sql`

Add the `theme_clusters` and `clustering_runs` tables (see [Architecture.md — Section 1.3](./Architecture.md#13-sqlite-schema-design)).

Add DatabaseManager methods:
```python
def insert_theme_clusters(self, clusters: list[dict], run_id: int) -> int:
    """Insert cluster records for a run. Returns count inserted."""

def delete_clusters_by_type(self, cluster_type: str) -> int:
    """Delete existing clusters for a type (before re-clustering). Returns count deleted."""

def get_theme_clusters(self, cluster_type: str = None) -> list[dict]:
    """Retrieve clusters, optionally filtered by type. Used by dashboard API."""

def log_clustering_run(self, run_data: dict) -> int:
    """Insert a clustering run log entry, return the run ID."""
```

**Acceptance:** Tables exist, CRUD operations work.

---

### Task 4.5.7 — Write clustering tests

**File:** `tests/test_clustering.py`

- `test_hdbscan_finds_clusters` — embed 30 known-similar values, verify HDBSCAN groups them
- `test_auto_label_is_descriptive` — verify Groq generates a specific label, not "General"
- `test_no_hardcoded_categories` — grep `engine.py` and `prompts.py` for any hardcoded category lists; fail if found
- `test_representative_quotes_verified` — verify selected quotes exist in source text
- `test_rerun_replaces_old_clusters` — run twice, verify only latest clusters exist
- `test_noise_points_excluded` — verify HDBSCAN noise (-1) points are not assigned to clusters

**Acceptance:** `pytest tests/test_clustering.py -v` — all pass.

---

### ⚠️ Phase 4.5 — Edge Cases & Gotchas

| # | Edge Case | What Goes Wrong | How to Handle |
|---|-----------|----------------|---------------|
| 1 | **Too few records for clustering** | Only 15 classified reviews → HDBSCAN can't form meaningful clusters | Check record count before clustering. If fewer than `MIN_CLUSTER_SIZE * 3` (e.g., 15), skip clustering and log: *"Not enough data yet — need at least N classified reviews."* |
| 2 | **All values are unique** | Every `topic` value is different → 0 clusters found | Log a warning. The dashboard shows raw values instead of clusters. This is expected early on — clusters emerge as volume grows |
| 3 | **One giant cluster absorbs everything** | HDBSCAN puts 90% of reviews into a single cluster → the label is too generic | If a cluster exceeds 50% of total, try sub-clustering it: run HDBSCAN again on just that cluster's members with a smaller `min_cluster_size`. Or flag it for review |
| 4 | **Groq labels are too generic** | Auto-label returns "User Complaints" instead of something specific | The prompt explicitly says "Do NOT use generic labels." If the label contains generic terms (< 3 words or matches a blocklist like "General", "Feedback", "Issues"), retry with a more specific prompt showing a few example values |
| 5 | **Groq rate limit during labelling** | 20+ clusters to label → hits Groq's per-minute rate limit | Add 2-second delay between labelling calls. Use exponential backoff on 429. Since labelling is the last step, cluster assignments are already computed — only labels are missing |
| 6 | **Embeddings not in sync with classifications** | New classifications exist that haven't been embedded yet → clustering misses recent data | Run `embed --backfill` before clustering. The nightly pipeline does this automatically (embed runs before cluster) |
| 7 | **HDBSCAN performance on large datasets** | 10,000+ values → HDBSCAN is slow (O(n²) in worst case) | Use HDBSCAN's `algorithm='best'` which auto-selects. For very large sets, use `core_dist_n_jobs=-1` for parallelism. Consider sampling if > 50,000 values |
| 8 | **Field has very few non-null values** | `unmet_need` is null for 80% of reviews → only 50 values to cluster | This is fine — HDBSCAN works with small datasets. Just set expectations: fewer values = fewer clusters. Log the null percentage per field |

---

### ✅ Phase 4.5 Checklist

- [ ] `clustering/engine.py` — ThemeClusteringEngine with HDBSCAN + Groq auto-labelling
- [ ] `clustering/prompts.py` — Labelling prompt (open-ended, NO predefined categories)
- [ ] `theme_clusters` and `clustering_runs` SQLite tables with indexes
- [ ] DatabaseManager methods for cluster CRUD
- [ ] CLI: `python -m app.cluster` and `--field <name>`
- [ ] Clustering configuration in `settings.py`
- [ ] Re-runnable: new run replaces old clusters with fresh analysis
- [ ] Representative quotes verified against source text
- [ ] Tests pass, including `test_no_hardcoded_categories`
- [ ] End-to-end: collect → classify → embed → cluster → verify clusters in DB


## Phase 5 — PM Dashboard (Frontend)

> **Goal:** Build the interactive web dashboard to visualize extracted intelligence.
>
> **UI Requirement for Multilingual Data:** To ensure cross-country data is legible and credible to viewers, non-English reviews MUST display the original `pattern_evidence` quote first, with the English `quote_translated` displayed directly beneath it by default (not hidden behind a hover or click). If the original is English, display it once.
>
> The dashboard converts the tool from a "data browser" into a "discovery engine" by visibly answering the brief's six questions on screen: emergent frustration clusters ranked by frequency, emergent user segments (from clustering behaviour_pattern), and consistent unmet needs — each with counts, percentages, and representative quotes.
>
> **Estimated Time:** ~2 days
>
> **Depends On:** Phase 1 (FastAPI, DatabaseManager), Phase 4 (FeedbackRetriever), Phase 4.5 (theme_clusters table)

---

### Task 5.1 — Build dashboard API endpoints

**File:** `app/api/dashboard_routes.py`

Create a FastAPI router with these endpoints:

| # | Endpoint | Method | Returns |
|---|----------|--------|---------|
| 1 | `/api/dashboard/summary` | GET | Total count, count by source, count by sentiment |
| 2 | `/api/dashboard/topics` | GET | Most common topics (open-text tallied): `{value, count, percentage}[]` |
| 3 | `/api/dashboard/complaints` | GET | Top core complaints: `{value, count, delta_pct}[]` |
| 4 | `/api/dashboard/behaviours` | GET | Common behaviour patterns extracted: `{value, count}[]` |
| 5 | `/api/dashboard/workarounds` | GET | Workaround records: `{content, source, sentiment, date}[]` |
| 6 | `/api/dashboard/trends` | GET | Time series: `{date, topic, count}[]` for 30 days |
| 7 | `/api/dashboard/quotes` | GET | Paginated verbatim quotes with full metadata |
| 8 | `/api/dashboard/themes` | GET | All emergent theme clusters: `{cluster_type, label, count, percentage, quotes, sources}[]` |
| 9 | `/api/dashboard/themes/:type` | GET | Clusters for a specific type (topic, complaint, behaviour, unmet_need) |

All endpoints accept query params: `date_from`, `date_to`, `source`, `sentiment`, `topic`

**Acceptance:** Each endpoint returns valid JSON. Test with:
```bash
curl http://localhost:8000/api/dashboard/summary
curl "http://localhost:8000/api/dashboard/topics?source=appstore"
```

---

### Task 5.2 — Register routes in FastAPI app

**File:** Update `app/main.py`

```python
from app.api.dashboard_routes import router as dashboard_router
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
```

**Acceptance:** Routes appear in Swagger docs at `http://localhost:8000/docs`.

---

### Task 5.3 — Build the CSS design system

**File:** `frontend/css/styles.css`

Implement the full design system from [Architecture.md — Section 5.4](./Architecture.md#54-design-system):

- CSS custom properties (dark theme, accent colors, glassmorphism tokens)
- Base resets and typography (Inter font from Google Fonts)
- Card components with glassmorphism (`backdrop-filter: blur(16px)`)
- Navigation bar styles
- Filter bar styles (dropdowns, active states)
- Chart container styles
- Quote card styles (with source badges and sentiment tags)
- Responsive breakpoints (mobile, tablet, desktop)
- Hover effects and micro-animations (transitions, transforms)

**Acceptance:** The CSS file loads without errors and all custom properties resolve correctly.

---

### Task 5.4 — Build the dashboard HTML page

**File:** `frontend/index.html`

Layout (matching [Architecture.md — Section 5.1](./Architecture.md#51-dashboard-layout)):

```
Nav:     Logo + [Dashboard] [Research Chat] tabs
Filters: [Date Range] [Platform] [Sentiment] [Topic]
Row 1:   Sentiment Donut Chart | Top Complaints Cards
Row 2:   Common Topics Bar Chart | Workaround Tracker
Row 3:   Topic Trends Line Chart (full width)
Row 4:   Verbatim Quotes Feed (paginated, full width)
```

- Use semantic HTML5 (`<nav>`, `<main>`, `<section>`, `<article>`)
- Each chart gets a `<canvas>` element for Chart.js
- Include Chart.js via CDN
- Include Google Fonts Inter
- All interactive elements have unique IDs

**Acceptance:** Page loads at `http://localhost:8000/static/index.html` with correct layout (data may be empty).

---

### Task 5.5 — Build the dashboard JavaScript

**File:** `frontend/js/dashboard.js`

Responsibilities:
1. **On page load:** Fetch all 7 API endpoints concurrently
2. **Render charts:** Initialize Chart.js donut (sentiment), horizontal bar (top topics), line (topic trends over time)
3. **Render cards:** Top complaints with delta arrows (↑/↓), workaround verbatims, quote feed
4. **Filter handling:** On filter change → re-fetch all endpoints with filter params → re-render
5. **Pagination:** "Load more" button on quotes feed
6. **High-cardinality awareness:** Topic and complaint charts may have many unique labels; show only the top N and group the rest as "Other" for readability

**Acceptance:** Dashboard shows real data from the database with working filters and charts.

---

### Task 5.6 — Write API tests for dashboard

**File:** `tests/test_api.py`

- Test each of the 7 endpoints returns 200 with correct schema
- Test filter parameters are applied correctly
- Test pagination on quotes endpoint

**Acceptance:** `pytest tests/test_api.py -v` — all pass.

---

### ⚠️ Phase 5 — Edge Cases & Gotchas

| # | Edge Case | What Goes Wrong | How to Handle |
|---|-----------|----------------|---------------|
| 1 | **Database is empty on first visit** | PM opens the dashboard before any data has been collected → all charts are blank, page looks broken | Show a friendly empty state: *"No data yet. Run the collection pipeline to get started."* with a link to the README. Charts should render with zero data gracefully (Chart.js handles this, but test it) |
| 2 | **Division by zero in percentages** | Sentiment distribution calculates `count / total * 100`, but `total = 0` | Guard every division: `percentage = (count / total * 100) if total > 0 else 0` |
| 3 | **Week-over-week delta when last week had 0** | A new frustration category appears this week (e.g., 15 occurrences) but last week had 0 → delta is mathematically infinite | If last week's count is 0 and this week's count is > 0, display `"NEW"` instead of a percentage. If both are 0, display `"—"` |
| 4 | **Filter combination returns 0 results** | PM filters by `Trustpilot` + `Negative sentiment` + `Last 7 days` and gets nothing | Show an inline message: *"No results match these filters"* instead of blank charts. Suggest removing a filter |
| 5 | **Date range filter has `date_from` after `date_to`** | User somehow enters an inverted range → SQL query returns nothing | Validate on both frontend (disable invalid combos) and backend (swap dates if inverted, or return 400 error) |
| 6 | **Extremely long workaround descriptions** | A user wrote a 500-word workaround → the workaround card overflows | Truncate to 200 characters in the card view with a "Show full text" toggle. Store the full text, only truncate for display |
| 7 | **Chart.js canvas not resizing on window resize** | PM resizes their browser → chart stays at old dimensions, looks clipped | Set Chart.js `responsive: true` and `maintainAspectRatio: false`. Add a `window.addEventListener('resize', ...)` that calls `chart.resize()` |
| 8 | **API calls fail due to CORS** | Frontend served from `localhost:8000/static/` makes API calls to `localhost:8000/api/` → CORS blocks it | Since both are on the same origin, CORS shouldn't be an issue. But if serving frontend separately during development, add `CORSMiddleware` to FastAPI with `allow_origins=["*"]` for dev mode only |
| 9 | **Pagination offset exceeds total records** | User clicks "Load more" repeatedly → offset goes past the end → empty results but no indicator | Return `{data: [], has_more: false}` from the API. Frontend hides the "Load more" button when `has_more` is false |
| 10 | **Special characters in open-text filter values** | A topic like `"Discover Weekly — stale playlists"` has a dash and quotes → URL encoding issues in query params | Use `encodeURIComponent()` on the frontend. FastAPI auto-decodes URL params, but verify with a test |
| 11 | **Chart.js canvas not resizing on window resize** | PM resizes their browser → chart stays at old dimensions, looks clipped | Set Chart.js `responsive: true` and `maintainAspectRatio: false`. Add a `window.addEventListener('resize', ...)` that calls `chart.resize()` |
| 12 | **Mobile layout breaks** | On a phone screen, the donut chart and complaint cards overlap | Test at 375px width (iPhone SE). Use CSS `@media (max-width: 768px)` to stack cards vertically. Charts should shrink proportionally |
| 13 | **High-cardinality open-text labels** | Topic and complaint charts show 50+ unique labels → chart is unreadable | Show only the top 10–15 by frequency; collapse the rest into an "Other" bucket. Add a "View all" link for full details. Note: this is a UI-only grouping, not a schema-level clustering |

---

### ✅ Phase 5 Checklist

- [ ] 9 dashboard API endpoints in `dashboard_routes.py` (7 data + 2 theme)
- [ ] Routes registered in `main.py`
- [ ] `styles.css` — full design system with dark theme and glassmorphism
- [ ] `index.html` — dashboard layout with chart containers, filter bar, and Discovery Themes section
- [ ] `dashboard.js` — fetch data, render Chart.js charts, handle filters, render theme clusters
- [ ] Donut chart (sentiment), bar chart (topics), line chart (topic trends) render correctly
- [ ] **Discovery Themes view** showing emergent clusters with counts, %, representative quotes
- [ ] Themes mapped to brief's 6 questions (frustrations, segments, unmet needs)
- [ ] Top complaint cards show Δ week-over-week
- [ ] Workaround tracker shows verbatim descriptions
- [ ] Quotes feed is paginated with source/sentiment badges
- [ ] Filters update all visualizations
- [ ] High-cardinality labels handled (top-N + "Other")
- [ ] Responsive layout works on mobile/tablet
- [ ] API tests pass

---



## Phase 6 — RAG-Powered Research Chat

> **Goal:** Build the chat interface where PMs ask natural language questions and get synthesized, sourced answers.
>
> **Estimated Time:** ~2 days
>
> **Depends On:** Phase 4 (FeedbackRetriever, EmbeddingPipeline), Phase 5 (FastAPI routes pattern, CSS system)

---

### Task 6.1 — Build the RAG chat engine

**File:** `app/rag/chat_engine.py`

```python
class ChatEngine:
    def __init__(self, retriever: FeedbackRetriever):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.retriever = retriever

    async def answer(self, question: str, filters: ChatFilters) -> dict:
        """
        Full RAG pipeline:
        1. Retrieve relevant feedback using hybrid_search(question, filters, top_k=20)
        2. Build context block from retrieved records (numbered, with metadata)
        3. Construct messages: system prompt + context + user question
        4. Call Groq API
        5. Return {answer: str, sources: list[dict], metadata: dict}
        """

    def _build_context(self, records: list[ClassifiedFeedback]) -> str:
        """Format retrieved records as numbered context with metadata."""

    def _build_messages(self, context: str, question: str, history: list = None) -> list[dict]:
        """System prompt + optional conversation history + context + question."""

    def get_suggested_questions(self) -> list[str]:
        """Return 5-6 starter questions based on what's in the database."""
```

**Key implementation details:**
- **System prompt:** [Architecture.md — Section 6.2](./Architecture.md#62-rag-system-prompt) — rules about grounding, citing, honesty, and NEVER inventing quotes
- **Context window:** Max 20 reviews in context (fits within Llama's context window)
- **Temperature:** 0.3 (balanced — more creative than classification, but still grounded)
- **Verbatim quote validation:** After the LLM generates its answer, extract all quoted strings and verify each one exists (whitespace-normalized, case-insensitive) as a substring of a retrieved source document. Drop any unverified quote. This is the single biggest credibility feature.
- ~~Conversation history: Carry last 5 messages for follow-up questions~~ → **Deferred to v2**

**Acceptance:** Calling `answer("Why do users complain about Discover Weekly?", filters)` returns a structured response with cited quotes.

---

### Task 6.2 — Build chat API endpoints

**File:** `app/api/chat_routes.py`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Accept `{message, filters}`, return `{answer, sources, metadata}` |
| `/api/chat/suggest` | GET | Return suggested questions |

> **v1 Note:** SSE streaming endpoint (`/api/chat/stream`) is deferred to v2. The chat uses standard request/response.

Register in `app/main.py`:
```python
from app.api.chat_routes import router as chat_router
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
```

**Acceptance:** `POST /api/chat` with a question returns a sourced answer.

---

### Task 6.3 — Build the chat HTML page

**File:** `frontend/chat.html`

Layout (matching [Architecture.md — Section 6.5](./Architecture.md#65-chat-ui-layout)):

```
Nav:        Logo + [Dashboard] [Research Chat] tabs (shared with dashboard)
Left:       Filter sidebar (Date, Platform, Sentiment, Topic, Signal Type)
            + Suggested questions at bottom
Right:      Chat thread (scrollable message area)
            + Input bar at bottom (text input + send button)
```

- Messages alternate between user (right-aligned) and AI (left-aligned)
- AI messages include expandable source cards
- Each source card shows: quote snippet, platform badge, sentiment tag, date
- Loading state: animated typing indicator while waiting for response

**Acceptance:** Chat page loads at `http://localhost:8000/static/chat.html` with correct layout.

---

### Task 6.4 — Build the chat JavaScript

**File:** `frontend/js/chat.js`

Responsibilities:
1. **Send message:** POST to `/api/chat` with message + current filter values
2. **Render messages:** Append user message (right) and AI response (left) to chat thread
3. **Render source cards:** Collapsible cards under each AI message
4. **Suggested questions:** On click, populate input and send
5. **Filter changes:** Persist filter state for next message
6. **Enter key:** Send on Enter, newline on Shift+Enter

> **v1 Note:** SSE streaming (render tokens as they arrive) is deferred to v2.

**Acceptance:** Full chat flow works: type question → see loading → receive answer with source cards.

---

### Task 6.5 — Write tests for chat

**File:** Update `tests/test_api.py`

- `test_chat_returns_answer` — POST a question, verify response has `answer` and `sources`
- `test_chat_with_filters` — verify filters are applied to retrieval
- `test_suggest_returns_questions` — verify suggestions endpoint returns a list
- `test_chat_empty_db` — verify graceful handling when no data exists
- `test_quote_validation` — verify that fabricated quotes are stripped from the response

**Acceptance:** `pytest tests/test_api.py -v` — all chat tests pass.

---

### ⚠️ Phase 6 — Edge Cases & Gotchas

| # | Edge Case | What Goes Wrong | How to Handle |
|---|-----------|----------------|---------------|
| 1 | **No relevant feedback found for a question** | PM asks a very niche question → hybrid search returns 0 results → LLM gets an empty context and hallucinates | Check result count before calling the LLM. If 0 results: return *"I couldn't find any user feedback matching your question and filters. Try broadening your filters or rephrasing your question."* Never send an empty context to the LLM |
| 2 | **LLM hallucinates quotes** | The model invents a fake user quote that doesn't exist in the provided context | The system prompt must explicitly say: *"NEVER invent, fabricate, or paraphrase quotes. Only use EXACT text from the provided context."* Post-process: verify that every quoted string in the answer actually appears in the source records |
| 3 | **Question is completely off-topic** | PM asks `"What's the weather today?"` → system tries to find feedback about weather | Add a relevance check: if the top semantic search result has a cosine distance > 0.7 (very dissimilar), return: *"Your question doesn't seem related to user feedback about music discovery. Try asking about topics, complaints, or user patterns."* |
| 4 | **SSE connection drops mid-stream** | Network hiccup during streaming → the PM sees a half-rendered answer | Frontend should detect stream errors (`EventSource.onerror`). Show: *"Connection lost. Here's the partial answer:"* with a "Retry" button. Also persist the non-streaming answer as a fallback |
| 5 | **Conversation history exceeds token limit** | After 10+ back-and-forth messages, the accumulated history + context + question exceeds Llama's context window | Keep only the last 5 messages in history. If still too long, summarize older messages into a 2-sentence summary and prepend that instead |
| 6 | **PM asks a follow-up without context** | PM says `"Tell me more about that"` → the system doesn't know what "that" refers to because no conversation history is sent | Always send the last 3-5 messages as conversation history. The system prompt should say: *"If the user asks a follow-up, use the conversation history to understand what 'that', 'this', or 'those' refers to."* |
| 7 | **Filter + question mismatch** | PM asks about "shuffle problems" but has the filter set to `topic: Discover Weekly` → confusing results | The retrieval respects filters strictly. Consider adding a note in the response: *"Note: Results are filtered to 'Discover Weekly' only. Your question mentions shuffle — consider changing the topic filter."* Or: detect the mismatch and override the filter |
| 8 | **Very long AI response** | LLM generates a 2,000-word essay instead of a concise summary | Add `max_tokens=1500` to the Groq API call. Also include in the prompt: *"Keep your answer concise — aim for 300-500 words. Use bullet points for clarity."* |
| 9 | **Groq API timeout during chat** | The PM waits 30+ seconds with no response and thinks the app is broken | Set a 30-second timeout. If exceeded, return: *"The AI is taking longer than expected. Please try again or simplify your question."* Show a progress indicator with elapsed time on the frontend |
| 10 | **Rapid-fire messages** | PM sends 5 messages in 2 seconds → 5 concurrent Groq API calls → rate limit hit | Debounce on the frontend (disable send button while awaiting response). On the backend, queue messages and process sequentially. Return 429 if a previous request is still in-flight for the same session |
| 11 | **Suggested questions are stale** | The suggested questions were generated when the DB had 50 records. Now it has 5,000 and the suggestions no longer reflect the most interesting data | Regenerate suggested questions daily (as part of the nightly pipeline) or dynamically based on the most common topics/complaints in the current data |
| 12 | **XSS in user quotes displayed in chat** | A user review contains `<script>alert('xss')</script>` → it gets rendered in the AI's response as raw HTML | Always escape HTML in user content before rendering: use `textContent` (not `innerHTML`) for quotes, or sanitize with a DOMPurify-like approach. The backend should also strip HTML tags from stored content |

---

### ✅ Phase 6 Checklist

- [ ] `chat_engine.py` — RAG pipeline: retrieve → context → generate
- [ ] `chat_routes.py` — POST `/api/chat`, POST `/api/chat/stream`, GET `/api/chat/suggest`
- [ ] Routes registered in `main.py`
- [ ] `chat.html` — chat layout with filter sidebar, message thread, input bar
- [ ] `chat.js` — send, render, source cards, SSE streaming, suggested questions
- [ ] Source cards show platform badge, sentiment, date, expandable quote
- [ ] Filters persist across messages
- [ ] Conversation history carried (last 5 messages)
- [ ] Loading/typing indicator during AI response
- [ ] Chat tests pass
- [ ] End-to-end: type question → get sourced answer from real data

---

## Phase 7 — Automation, Scheduling & Production Hardening

> **Goal:** Wire everything into a fully automated nightly pipeline, add health monitoring, and polish for daily use.
>
> **Estimated Time:** ~1 day
>
> **Depends On:** All previous phases (Phases 1-6)

---

### Task 7.1 — Build the NightlyPipeline

**File:** `app/scheduler/pipeline.py`

```python
class NightlyPipeline:
    def __init__(self):
        self.db = DatabaseManager(settings.SQLITE_DB_PATH)
        self.orchestrator = CollectionOrchestrator(self.db)
        self.classifier = ClassificationEngine(self.db)
        self.embedding = EmbeddingPipeline()

    async def run(self) -> dict:
        """
        Execute the full pipeline:
        1. COLLECT — run all 4 collectors (capped at MAX_RECORDS_PER_SOURCE_PER_RUN per source)
        2. CLASSIFY — classify up to MAX_CLASSIFICATIONS_PER_RUN unclassified records (oldest first)
        3. EMBED — embed all newly classified records into ChromaDB
        4. CLUSTER — re-run theme clustering (HDBSCAN + Groq auto-labels)
        5. DELTA — generate daily summary comparing to 7-day avg (MIN_PATTERN_SAMPLE guard)
        6. LOG — record pipeline run results
        Return summary dict with counts and timing.
        """

    async def generate_delta_summary(self) -> dict:
        """
        Compare today's classifications to the 7-day rolling average:
        - Only report trends if category has >= MIN_PATTERN_SAMPLE (10) records
        - Growing patterns: open-text topics/complaints up >15% (if sample large enough)
        - Fading patterns: topics/complaints down >15% (if sample large enough)
        - New workarounds: descriptions not seen before
        - Store in daily_summaries table
        """
```

**Acceptance:** `python -m app.pipeline` runs the full pipeline end-to-end.

---

### Task 7.2 — Set up the scheduler

**File:** `app/scheduler/scheduler.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.add_job(
        NightlyPipeline().run,
        trigger=CronTrigger(hour=settings.COLLECTION_HOUR, minute=settings.COLLECTION_MINUTE),
        id="nightly_pipeline",
        name="Nightly Feedback Pipeline",
        misfire_grace_time=3600,
        replace_existing=True
    )
    scheduler.start()
```

**File:** Update `app/main.py` to start scheduler on app startup using `lifespan` context manager (not deprecated `@app.on_event`):

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db.initialize()
    start_scheduler()
    yield
    # Shutdown
    scheduler.shutdown()

app = FastAPI(title="AI Review Analyser", lifespan=lifespan)
```

> **Why lifespan?** `@app.on_event("startup")` is deprecated in current FastAPI. It works now but throws warnings and will eventually break. The `lifespan` pattern is the official replacement.

**Acceptance:** When the server starts, the scheduler is active. The pipeline runs at the configured time.

---

### Task 7.3 — Build health check endpoints

**File:** `app/api/health_routes.py`

| Endpoint | Returns |
|----------|---------|
| `/api/health` | System status, DB size, total records, last pipeline run, next scheduled run |
| `/api/health/sources` | Per-source: last success time, total records, error rate |
| `/api/health/pipeline` | Last pipeline run: duration, records collected/classified/embedded, errors |

Register in `main.py`:
```python
from app.api.health_routes import router as health_router
app.include_router(health_router, prefix="/api/health", tags=["Health"])
```

**Acceptance:** `/api/health` returns complete system status JSON.

---

### Task 7.4 — Complete the CLI interface

**File:** `app/cli.py`

Final CLI commands:

```bash
# Full pipeline
python -m app.pipeline                          # Run collect → classify → embed → delta

# Individual steps
python -m app.collect --all                     # Collect from all sources
python -m app.collect --source appstore           # Collect from one source
python -m app.classify --batch-size 50          # Classify N records
python -m app.embed --backfill                  # Embed all unembedded records
python -m app.embed --count                     # Show ChromaDB document count
python -m app.cluster                           # Run theme clustering (HDBSCAN + Groq labels)

# Server
python -m app.serve --port 8000                 # Start FastAPI + scheduler

# Status
python -m app.health                            # Print system health to stdout
```

**Acceptance:** All CLI commands work as documented.

---

### Task 7.5 — Add logging

Configure Python logging throughout the application:
- **File:** `app/config/logging_config.py`
- Log to `data/logs/app.log` with rotation (10MB max, keep 5 files)
- Log levels: INFO for normal ops, WARNING for retries, ERROR for failures
- Each pipeline step logs start/end with timing

**Acceptance:** After a pipeline run, `data/logs/app.log` contains detailed execution log.

---

### Task 7.6 — Write README.md

**File:** `README.md`

Sections:
1. Project overview (1 paragraph)
2. Features list
3. Tech stack table
4. Prerequisites (Python 3.11+, API keys needed)
5. Installation steps (clone, venv, pip install, .env setup)
6. Quick start (run collect → classify → embed → serve)
7. CLI reference table
8. API reference table
9. Configuration reference (.env variables)
10. **Automation disclaimer:** *"The pipeline runs on schedule while the server is running. APScheduler is in-process — the job only fires if the server process is alive."*
11. Development (running tests, project structure)

**Acceptance:** A new developer can go from clone to running dashboard by following the README.

---

### ⚠️ Phase 7 — Edge Cases & Gotchas

| # | Edge Case | What Goes Wrong | How to Handle |
|---|-----------|----------------|---------------|
| 1 | **Pipeline runs twice simultaneously** | Server restarts at 11:59 PM, scheduler fires twice → duplicate collection and classification | APScheduler's `replace_existing=True` prevents duplicate job registration. Additionally, add a lock: check `collection_runs` table for a `running` status before starting. If one exists from the last 30 minutes, skip |
| 2 | **Pipeline starts but server crashes mid-run** | Power outage or OOM kill during classification step → some records classified, some not, collection log says `running` forever | On startup, check for stale `running` entries in `collection_runs` (started > 1 hour ago). Mark them as `failed`. Unclassified records will be picked up on the next run automatically |
| 3 | **Midnight pipeline conflicts with PM using the dashboard** | PM is running queries while the pipeline is inserting new records → stale reads or slowdowns | SQLite WAL mode (from Phase 1) handles this. Readers don't block writers and vice versa. No special handling needed, but document this behavior |
| 4 | **Scheduler misfire** | The machine was asleep/off at midnight → the scheduled job was missed entirely | `misfire_grace_time=3600` allows the job to run up to 1 hour late. If the machine was off for 12 hours, the job runs immediately when the server restarts. APScheduler handles this automatically |
| 5 | **Delta summary on day 1** | The first nightly run has no historical data to compare → growing/fading patterns are meaningless | If there are fewer than 7 days of data, skip delta calculation and set `growing_patterns` and `fading_patterns` to empty lists. Show *"Trends available after 7 days of data"* on the dashboard |
| 6 | **All 4 collectors fail** | Every source is down simultaneously (unlikely but possible during a mass API outage) | The pipeline should still complete with 0 new records. Log a `CRITICAL` warning. Delta summary notes: *"0 records collected — all sources failed."* Dashboard still shows historical data |
| 7 | **Log file grows indefinitely** | After months of running, `app.log` is 5GB → fills the disk | Use Python's `RotatingFileHandler(maxBytes=10*1024*1024, backupCount=5)` — max 10MB per file, keep 5 rotated files (50MB total max) |
| 8 | **System clock changes (DST or NTP sync)** | The system clock jumps backward → `since` timestamp is in the future → collector thinks it already has everything | Always use UTC internally (`datetime.utcnow()`). Never use local time for timestamps. Store all times as UTC in the database |
| 9 | **Groq API key expires or billing runs out** | The pipeline collects data successfully but classification fails for every record | Separate collection and classification status. Collection still succeeds → raw data is preserved. Classification is retried on the next run. Health endpoint should flag: *"Classification: FAILING — 0 records classified in last 24h"* |
| 10 | **Database file corruption** | Rare but possible: power loss during a write corrupts the SQLite file | Enable WAL mode (reduces corruption risk). Implement daily backup: copy `feedback.db` to `feedback.db.bak` at the start of each pipeline run, before writing anything. Health endpoint reports DB integrity: `PRAGMA integrity_check` |
| 11 | **Memory spike during embedding backfill** | Backfilling 10,000 records at once → `sentence-transformers` loads all into memory → OOM | Process embeddings in batches of 100. The `embed_and_store()` method should accept a `batch_size` parameter and process iteratively |
| 12 | **Health endpoint reveals sensitive info** | `/api/health` exposes API keys, file paths, or internal error messages to anyone who accesses it | Never include API keys in health responses. Sanitize error messages (show category, not full stack trace). Consider adding basic auth to health endpoints in production |
| 13 | **Trustpilot consistently blocked** | Trustpilot returns 403 Forbidden | Treat as an optional source. If `trustpilot_collector` fails, catch the error, log a warning, and allow the pipeline to succeed with the other sources. Do NOT count it as a pipeline failure |

---

### ✅ Phase 7 Checklist

- [ ] `pipeline.py` — NightlyPipeline: collect → classify → embed → cluster → delta → log
- [ ] `scheduler.py` — APScheduler cron at midnight
- [ ] Scheduler starts on app startup
- [ ] `health_routes.py` — 3 health check endpoints
- [ ] `cli.py` — all CLI commands work (pipeline, collect, classify, embed, serve, health)
- [ ] `logging_config.py` — file logging with rotation
- [ ] `README.md` — complete setup and usage guide
- [ ] Full end-to-end test: start server → scheduler triggers → data flows → dashboard updates
- [ ] Pipeline handles source failures gracefully (other sources continue)
- [ ] Pipeline handles classification failures gracefully (records retried next run)

---

## Summary — All Phases at a Glance

| Phase | Tasks | Key Files | Estimated Time |
|-------|-------|-----------|----------------|
| **Phase 1** — Foundation | 9 tasks | `settings.py`, `schema.sql`, `feedback.py`, `db_manager.py`, `main.py` | ~1 day |
| **Phase 2** — Collection | 10 tasks | `base_collector.py`, 4 collectors, `orchestrator.py`, `cli.py` | ~2 days |
| **Phase 3** — Classification | 4 tasks | `prompts.py`, `engine.py` | ~1 day |
| **Phase 4** — Embeddings | 4 tasks | `embed_pipeline.py`, `retriever.py` | ~1 day |
| **Phase 4.5** — Clustering | 3 tasks | `clustering/engine.py`, `clustering/prompts.py`, `theme_clusters` table | ~1 day |
| **Phase 5** — Dashboard | 7 tasks | `dashboard_routes.py`, `index.html`, `styles.css`, `dashboard.js` | ~2 days |
| **Phase 6** — RAG Chat | 5 tasks | `chat_engine.py`, `chat_routes.py`, `chat.html`, `chat.js` | ~2 days |
| **Phase 7** — Automation | 6 tasks | `pipeline.py`, `scheduler.py`, `health_routes.py`, `README.md` | ~1 day |
| **Total** | **~48 tasks** | **~33 files** | **~11 days** |

---

## Verification Milestones

These are key "it works" moments you should hit along the way:

| After Phase | You Should Be Able To... |
|-------------|--------------------------|
| **Day 1 Slice** | Run a throwaway script that pulls 10 App Store reviews, classifies them through Groq, and prints valid 11-field JSON |
| **Phase 1** | Start the server, hit `/api/health`, insert/query records in SQLite |
| **Phase 2** | Run `python -m app.collect --all` and see real reviews stored in the DB |
| **Phase 3** | Run `python -m app.classify --batch-size 10` and see 11-field classifications in DB |
| **Phase 4** | Search ChromaDB semantically and get relevant reviews back |
| **Phase 4.5** | Run `python -m app.cluster` and see emergent theme clusters with auto-generated labels in the DB |
| **Phase 5** | Open the dashboard in a browser and see charts, trends, quotes, AND the Discovery Themes view answering the brief's 6 questions |
| **Phase 6** | Ask "Why do users hate Discover Weekly?" and get a sourced answer with verified quotes |
| **Phase 7** | Leave it running overnight and find new data in the dashboard the next morning |

---

## Build Order Recommendation — Read Before Starting Phase 1

> **Do a one-day vertical slice BEFORE the full Phase 1 scaffold.**

The current plan builds all scaffolding first and doesn't validate the core risk — *does the AI classification actually produce clean JSON?* — until Phase 3, several days in.

Instead, on day one, build a throwaway slice that goes end to end:

1. Pull 10 reviews from the App Store using the official Apple RSS feed (via `httpx`) (one collector, minimal)
2. Classify them through Groq with the 11-field prompt
3. Write the results to a SQLite table (or just print to console)

**If** the JSON comes back clean and scraping works, the whole project is de-risked and you proceed to the real Phase 1 scaffold with confidence.

**If** Groq's output is messy or scraper fights you, you find out on day one instead of day five.

After the slice works, **delete it** and build the proper phased version.

---

> **Ready to start?** Begin with the **vertical slice** (see above) to de-risk AI output quality, then move on to [Phase 1, Task 1.1](#task-11--create-the-directory-structure) — create the directory structure.

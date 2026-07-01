# Phase Tracking — Files by Phase

> Which files were created or modified in each phase.  
> All files live in the same project tree — phases build on each other.

---

## Phase 1 — Foundation & Scaffolding ✅

**Status:** Complete  
**Date:** 2026-06-18

### Files Created

| File | Purpose |
|------|---------|
| `requirements.txt` | Pinned dependencies for the entire project |
| `.env.example` | Environment variable template |
| `.gitignore` | Git exclusions (data/, .env, __pycache__/) |
| `app/__init__.py` | Package marker |
| `app/main.py` | FastAPI app skeleton with `/api/health` |
| `app/cli.py` | CLI entry point (placeholder) |
| `app/config/__init__.py` | Package marker |
| `app/config/settings.py` | Pydantic Settings — reads all config from `.env` |
| `app/models/__init__.py` | Package marker |
| `app/models/feedback.py` | Pydantic models: FeedbackRecord, ClassificationResult (11 fields), ClassifiedFeedback, CollectionRunLog, DashboardFilters, ChatFilters |
| `app/database/__init__.py` | Package marker |
| `app/database/schema.sql` | Full SQLite schema — 6 tables, 8 indexes |
| `app/database/db_manager.py` | DatabaseManager with full CRUD for feedback, classifications, collection runs, summaries, and dashboard queries |
| `app/collectors/__init__.py` | Package marker (placeholder for Phase 2) |
| `app/classifier/__init__.py` | Package marker (placeholder for Phase 3) |
| `app/embeddings/__init__.py` | Package marker (placeholder for Phase 4) |
| `app/clustering/__init__.py` | Package marker (placeholder for Phase 4.5) |
| `app/retrieval/__init__.py` | Package marker (placeholder for Phase 6) |
| `app/rag/__init__.py` | Package marker (placeholder for Phase 6) |
| `app/scheduler/__init__.py` | Package marker (placeholder for Phase 7) |
| `app/api/__init__.py` | Package marker (placeholder for Phase 5) |
| `frontend/index.html` | Dashboard HTML (placeholder for Phase 5) |
| `frontend/chat.html` | Chat HTML (placeholder for Phase 6) |
| `frontend/css/styles.css` | Stylesheet (placeholder for Phase 5) |
| `frontend/js/dashboard.js` | Dashboard JS (placeholder for Phase 5) |
| `frontend/js/chat.js` | Chat JS (placeholder for Phase 6) |
| `tests/__init__.py` | Package marker |
| `tests/test_db_manager.py` | 7 unit tests for DatabaseManager |

### Acceptance Checks Passed

- `from app.config.settings import settings` — ✅ no ImportError
- `settings.GROQ_MODEL` prints `llama-3.3-70b-versatile` — ✅
- `DatabaseManager.initialize()` creates all 6 tables — ✅
- `curl localhost:8000/api/health` returns `{"status":"healthy","version":"1.0.0"}` — ✅
- `pytest tests/test_db_manager.py -v` — ✅ 7/7 passed

---

## Phase 2 — Data Collection Pipeline ✅

**Status:** Complete  
**Date:** 2026-06-18

### Files Created/Modified

| File | Purpose |
|------|---------|
| `app/collectors/base_collector.py` | AbstractCollector with lifecycle, rate-limiting, dedup |
| `app/collectors/appstore_collector.py` | Fetches multi-country App Store reviews via Apple RSS |
| `app/collectors/playstore_collector.py` | Fetches multi-country Play Store reviews via google-play-scraper |
| `app/collectors/spotify_community_collector.py` | Scrapes Spotify Community forum via httpx/BS4 |
| `app/collectors/trustpilot_collector.py` | Scrapes Trustpilot (optional, handles failures gracefully) |
| `app/collectors/orchestrator.py` | Concurrently runs all collectors |
| `app/collect.py` | CLI entry point (`python -m app.collect`) |
| `tests/test_collectors.py` | Integration tests with mocked responses & failure handling |

### Acceptance Checks Passed

- `pytest tests/test_collectors.py -v` — ✅ 6/6 passed (tests orchestration, dedup, extraction)
- `python -m app.collect --all` — ✅ Ran successfully against live APIs.
- App Store returns multi-country tagged reviews — ✅ (DB has US, GB, IN, BR tags)
- Play Store deduplication works — ✅ (scraper returns global reviews regardless of country param, dedup prevents duplicates)
- Trustpilot graceful failure — ✅ (Returns 403, pipeline handles it, logs it, and continues)

---

## Phase 3 — AI Classification Engine

**Status:** Not started

---

## Phase 4 — Embedding & Storage

**Status:** Not started

---

## Phase 4.5 — Theme Clustering Engine

**Status:** Not started

---

## Phase 5 — PM Dashboard (Frontend)

**Status:** Not started

---

## Phase 6 — RAG Chat Interface

**Status:** Not started

---

## Phase 7 — Automation & Hardening

**Status:** Not started

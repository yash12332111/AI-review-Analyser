# AI-Powered User Feedback Intelligence System

This project is a centralized, AI-driven intelligence system for analyzing user feedback across multiple platforms (App Store, Play Store, Spotify Community, and Trustpilot). It automatically collects reviews, uses Llama 3.3 70B to consistently extract unstructured themes and sentiments, builds semantic embeddings, and provides a polished dashboard and RAG-powered research chat to query the insights.

## Features
- **Multi-Source Collection**: Seamlessly scrapes and normalizes feedback from 4 sources.
- **LLM-Powered Classification**: Extracts 11 structured fields (topic, core complaint, sentiment, workarounds) without relying on rigid predefined buckets.
- **Semantic Search & RAG**: Vector-based semantic search via ChromaDB, driving a conversational interface that cites specific user quotes.
- **Automated Theme Clustering**: Uses HDBSCAN and LLM auto-labeling to detect emergent topics and patterns across the userbase.
- **Nightly Automation**: Built-in APScheduler pipeline runs collection, classification, embedding, and clustering overnight.
- **Real-Time PM Dashboard**: A fast, client-side rendered dashboard to explore trends, quotes, and themes.

## Tech Stack

| Component | Technology |
|---|---|
| **Backend Framework** | FastAPI (Python 3.9+) |
| **Database (Relational)** | SQLite (WAL mode) |
| **Database (Vector)** | ChromaDB |
| **Embeddings** | sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`) |
| **LLM Inference** | Groq (`llama-3.3-70b-versatile`) |
| **Clustering** | HDBSCAN + scikit-learn |
| **Frontend** | Vanilla HTML/CSS/JS |
| **Scheduling** | APScheduler |

## Prerequisites
- Python 3.9+ (3.11+ recommended)
- A Groq API key for LLM inference (supports key rotation for rate limits)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "AI Review Analyser"
   ```

2. **Set up the virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   Copy `.env.example` to `.env` and configure your API keys:
   ```bash
   cp .env.example .env
   # Edit .env and add your GROQ_API_KEY
   ```

## Quick Start

You can manually trigger the pipeline steps to seed your database before starting the server.

```bash
# 1. Collect raw feedback from all sources
python -m app.collect --all

# 2. Classify the raw feedback via Groq
python -m app.classify --all

# 3. Embed classified records into ChromaDB
python -m app.embed --backfill

# 4. Detect emerging themes
python -m app.cluster

# 5. Serve the Dashboard and Chat API
python -m app.serve --port 8000
```
Then, open `http://localhost:8000/static/index.html` in your browser.

## CLI Reference

| Command | Description |
|---|---|
| `python -m app.pipeline` | Run the full nightly pipeline (collect → classify → embed → cluster → delta) |
| `python -m app.collect --all` | Collect from all sources |
| `python -m app.collect --source <name>` | Collect from a specific source |
| `python -m app.classify --batch-size N` | Classify N unclassified records |
| `python -m app.classify --all` | Classify all unclassified records |
| `python -m app.embed --backfill` | Embed all unembedded records |
| `python -m app.embed --count` | Show ChromaDB document count |
| `python -m app.cluster` | Run theme clustering |
| `python -m app.serve --port <port>` | Start FastAPI + scheduler |
| `python -m app.health` | Print system health to stdout |

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Global health check |
| `/api/health/sources` | GET | Per-source collection health |
| `/api/health/pipeline` | GET | Recent pipeline execution logs |
| `/api/dashboard/summary` | GET | High-level feedback counts |
| `/api/dashboard/topics` | GET | Most common topics |
| `/api/dashboard/complaints`| GET | Top core complaints |
| `/api/dashboard/quotes` | GET | Paginated classified feedback |
| `/api/chat` | POST | RAG query returning an LLM answer with sourced quotes |
| `/api/chat/suggest` | GET | Return suggested questions |

## Configuration Reference (`.env`)

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Your Groq API key |
| `GROQ_API_KEYS` | Comma-separated list of keys for rate-limit rotation (optional) |
| `SQLITE_DB_PATH` | Path to the SQLite database |
| `CHROMA_PERSIST_DIR` | Path to the ChromaDB directory |
| `MAX_RECORDS_PER_SOURCE_PER_RUN` | Cap on raw records fetched per run |
| `MAX_CLASSIFICATIONS_PER_RUN` | Daily cap to prevent blowing Groq token quotas |
| `COLLECTION_HOUR` / `MINUTE` | Time the nightly pipeline executes (UTC) |

> **Automation disclaimer:** *The pipeline runs on schedule while the server is running. APScheduler is in-process — the job only fires if the server process is alive.*

## Development

The project is structured entirely within `app/`, `frontend/`, and `tests/`.

- **Run tests:**
  ```bash
  pytest tests/ -v
  ```
- **Logs:** Review `data/logs/app.log` for runtime application and pipeline traces.

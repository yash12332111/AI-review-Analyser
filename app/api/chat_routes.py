from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.models.feedback import ChatFilters, DashboardFilters
from app.rag.chat_engine import ChatEngine
from app.database.db_manager import DatabaseManager
from app.config.settings import settings

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    filters: Optional[ChatFilters] = None

# Lightweight SQL-only retriever — no PyTorch, no ChromaDB, no OOM.
class SQLOnlyRetriever:
    """Retrieves feedback using SQL full-text keyword search only.
    No sentence-transformers or ChromaDB are loaded — safe on 512 MB RAM.
    """
    def __init__(self, db: DatabaseManager):
        self.db = db

    def hybrid_search(self, query: str, filters: Optional[ChatFilters], top_k: int = 20):
        """Keyword-based SQL search across content and classifications."""
        dash_filters = DashboardFilters(
            source=filters.source if filters else None,
            sentiment=filters.sentiment if filters else None,
            topic=filters.topic if filters else None,
            date_from=filters.date_from if filters else None,
            date_to=filters.date_to if filters else None,
        )
        # Broad pull then Python-side keyword re-ranking
        results = self.db.query_feedback(dash_filters, limit=200)

        if not results:
            return []

        # Simple keyword relevance: count how many query words appear in content
        words = [w.lower() for w in query.split() if len(w) > 3]
        def score(rec):
            text = (rec.content or "").lower()
            return sum(1 for w in words if w in text)

        results.sort(key=score, reverse=True)
        return results[:top_k]

# Cache at module level so DB connection is reused
_db = None

def get_chat_engine() -> ChatEngine:
    global _db
    if _db is None:
        _db = DatabaseManager(settings.SQLITE_DB_PATH)
    retriever = SQLOnlyRetriever(_db)
    return ChatEngine(retriever)

@router.post("")
async def chat(request: ChatRequest, engine: ChatEngine = Depends(get_chat_engine)):
    filters = request.filters or ChatFilters()
    result = await engine.answer(request.message, filters)
    return result

@router.get("/suggest")
async def suggest_questions():
    return {"suggestions": [
        "Why do users complain about Discover Weekly?",
        "What frustrates users most about shuffle?",
        "Why do users keep hearing the same songs?",
        "What workarounds do users use to find new music?",
        "Are there different challenges between iOS and Android users?",
        "What are consistent unmet needs across different sources?"
    ]}

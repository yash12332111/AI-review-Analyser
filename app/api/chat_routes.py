from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.models.feedback import ChatFilters
from app.rag.chat_engine import ChatEngine
from app.database.db_manager import DatabaseManager
from app.embeddings.embed_pipeline import EmbeddingPipeline
from app.retrieval.retriever import FeedbackRetriever
from app.config.settings import settings

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    filters: Optional[ChatFilters] = None

# We can cache these at the module level or app level so we don't reload embeddings every request
_db = None
_ep = None
_retriever = None

def get_chat_engine() -> ChatEngine:
    global _db, _ep, _retriever
    if _db is None:
        _db = DatabaseManager(settings.SQLITE_DB_PATH)
    if _ep is None:
        _ep = EmbeddingPipeline(settings.EMBEDDING_MODEL)
    if _retriever is None:
        _retriever = FeedbackRetriever(_db, _ep)
    return ChatEngine(_retriever)

@router.post("")
async def chat(request: ChatRequest, engine: ChatEngine = Depends(get_chat_engine)):
    filters = request.filters or ChatFilters()
    result = await engine.answer(request.message, filters)
    return result

@router.get("/suggest")
async def suggest_questions(engine: ChatEngine = Depends(get_chat_engine)):
    return {"suggestions": engine.get_suggested_questions()}

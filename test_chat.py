import asyncio
from app.config.settings import settings
from app.database.db_manager import DatabaseManager
from app.embeddings.embed_pipeline import EmbeddingPipeline
from app.retrieval.retriever import FeedbackRetriever
from app.rag.chat_engine import ChatEngine
from app.models.feedback import ChatFilters

async def main():
    print("Initializing...")
    db = DatabaseManager(settings.SQLITE_DB_PATH)
    ep = EmbeddingPipeline(settings.EMBEDDING_MODEL)
    retriever = FeedbackRetriever(db, ep)
    engine = ChatEngine(retriever)
    print("Engine ready. Calling answer()...")
    
    filters = ChatFilters()
    try:
        res = await engine.answer("What are the most common frustrations with music recommendations?", filters)
        print("RESULT:")
        print(res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from app.database.db_manager import DatabaseManager
from app.embeddings.embed_pipeline import EmbeddingPipeline
from app.retrieval.retriever import FeedbackRetriever
from app.config.settings import settings

db = DatabaseManager(settings.SQLITE_DB_PATH)
ep = EmbeddingPipeline(settings.EMBEDDING_MODEL)
retriever = FeedbackRetriever(db, ep)

def get_dist(q):
    res = ep.query(text=q, n_results=1)
    if res and res[0].get("distance") is not None:
        return res[0]["distance"]
    return 999.0

queries = [
    "what is the weather",
    "what time is it",
    "why do users repeat the same songs?",
    "what frustrates users about shuffle?",
    "why do users complain about discover weekly?",
    "is the app too expensive?",
    "how to cook pasta",
    "the cat sat on the mat"
]

for q in queries:
    print(f"'{q}' -> {get_dist(q):.4f}")


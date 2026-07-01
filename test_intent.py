import asyncio
import logging
from app.rag.chat_engine import ChatEngine
from app.config.settings import settings

logging.basicConfig(level=logging.INFO)

class DummyRetriever:
    def hybrid_search(self, *args, **kwargs):
        return []

async def test():
    engine = ChatEngine(retriever=DummyRetriever())
    res = await engine.answer("hi", None)
    print("RESULT:", res)

asyncio.run(test())

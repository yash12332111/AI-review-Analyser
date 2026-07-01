import asyncio
import json
from app.api.chat_routes import get_chat_engine
from app.models.feedback import ChatFilters

async def run_tests():
    engine = get_chat_engine()
    
    questions = [
        "Why do users complain about Discover Weekly?",
        "What frustrates users most about shuffle?",
        "Why do users keep repeating the same songs?",
        "What are the main workarounds users have for finding new music?",
        "Are there different challenges between iOS and Android users?",
        "What are consistent unmet needs across different sources?",
        "What are user complaints regarding the new Tesla car integration?" # Gap question
    ]
    
    for q in questions:
        print(f"\n{'='*80}\nQ: {q}\n{'-'*80}")
        try:
            res = await engine.answer(q, ChatFilters())
            print(f"A: {res['answer']}\n")
            print(f"Sources: {len(res['sources'])} retrieved")
            for i, s in enumerate(res['sources'][:2]):
                print(f"  [{i}] {s['source']} | Sentiment: {s['sentiment']} | {s['country']} - {s['quote'][:100]}...")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_tests())

import asyncio
import json
import httpx

questions = [
    "Why do users complain about Discover Weekly?",
    "What frustrates users most about shuffle?",
    "Why do users keep repeating the same songs?",
    "What are the main workarounds users have for finding new music?",
    "Are there different challenges between iOS and Android users?",
    "What are consistent unmet needs across different sources?"
]

async def main():
    async with httpx.AsyncClient() as client:
        for i, q in enumerate(questions):
            print(f"\n--- Question {i+1}: {q} ---")
            response = await client.post("http://127.0.0.1:8000/api/chat", json={"message": q, "filters": {}}, timeout=60.0)
            if response.status_code == 200:
                data = response.json()
                print("ANSWER:\n" + data["answer"])
            else:
                print(f"Error {response.status_code}")

if __name__ == "__main__":
    asyncio.run(main())

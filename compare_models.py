"""
Compare classification quality between 8b and 70b models.
"""
import asyncio
import json
import sqlite3
import sys
from typing import Dict, Any

from groq import AsyncGroq
from app.config.settings import settings
from app.classifier.prompts import CLASSIFICATION_SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
from app.classifier.engine import ClassificationEngine

async def classify_with_model(client: AsyncGroq, model: str, content: str) -> Dict[str, Any]:
    messages = [{"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT}]
    messages.extend(FEW_SHOT_EXAMPLES)
    messages.append({"role": "user", "content": content})
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=1024,
            timeout=30.0,
        )
        raw = response.choices[0].message.content
        cleaned = ClassificationEngine._clean_response(raw)
        return json.loads(cleaned)
    except Exception as e:
        return {"error": str(e)}

async def main():
    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    
    conn = sqlite3.connect(settings.SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Get 12 mixed reviews (English and non-English) that are substantial in length
    cursor = conn.execute('''
        SELECT id, source, country, content 
        FROM feedback 
        WHERE length(content) > 50
        ORDER BY RANDOM()
        LIMIT 12
    ''')
    reviews = cursor.fetchall()
    
    print("# Model Quality Comparison: 8b vs 70b\n", flush=True)
    
    for i, r in enumerate(reviews):
        print(f"## Review {i+1} [{r['source']}/{r['country']}]", flush=True)
        print(f"**Text:** {r['content'][:300]}...\n", flush=True)
        
        # 8b
        res_8b = await classify_with_model(client, "llama-3.1-8b-instant", r['content'])
        
        # 70b (with 3s sleep to avoid rate limits)
        await asyncio.sleep(3)
        res_70b = await classify_with_model(client, "llama-3.3-70b-versatile", r['content'])
        
        print("| Field | 8b | 70b |", flush=True)
        print("|-------|----|-----|", flush=True)
        
        if "error" in res_8b or "error" in res_70b:
            print(f"| Error | {res_8b.get('error', 'None')} | {res_70b.get('error', 'None')} |", flush=True)
            print("\n", flush=True)
            continue
            
        for field in ['core_complaint', 'user_job_to_be_done', 'unmet_need']:
            val_8b = str(res_8b.get(field, 'null')).replace('\n', ' ')
            val_70b = str(res_70b.get(field, 'null')).replace('\n', ' ')
            print(f"| **{field}** | {val_8b} | {val_70b} |", flush=True)
        
        print("\n" + "-"*50 + "\n", flush=True)
        
        # Respect limits
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())

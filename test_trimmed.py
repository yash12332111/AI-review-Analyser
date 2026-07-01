import asyncio
import json
import sqlite3
import sys
from typing import Dict, Any

from groq import AsyncGroq
from app.config.settings import settings
from app.classifier.prompts import CLASSIFICATION_SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
from app.classifier.engine import ClassificationEngine

TEXT_1 = "war Mal gut - wird immer schlimmer! erst wird man dazu gezwungen ein neues Widget zu verwenden, dass doppelt so groß ist wie das Alte, was natürlich die gesamte App Anordnung durcheinander bringt! außerdem geht seit dem neuen Widget nichts mehr! die App öffnet sich nicht mal mehr bei mir, trotz Neuinstallation. absolute Katastrophe und definitiv keinen Cent wert, den man hier lässt."
TEXT_2 = "Wie viele andere Kunden bin ich nur noch enttäuscht und frustriert. In Listen Titel ausblenden hatte früher den Effekt, das man diesen auch nicht hören musste (wozu sollte die Funktion auch sonst gut sein!?) Nun kann man die Titel zwar nach wie vor ausblenden aber abgespielt wird er dann trotzdem. J... und Preissteigerung ohne Qualitätsverbesserung."
TEXT_3 = "काम में लेना ही बंद कर दिया इतना अच्छा ऐप जो था स्पोटीफाई वाले कभी भी user id का नाम सीधा सादा कभी नहीं रखते मुझे आज तक मेरी id का user name हो नहीं पता और ये ऐप वाले रखते है इतना रहस्यमय प्रीमियम और लिया था 299 का lossless क्वालिटी सुनने के लिए ये भी धोखा है मेरे गाने मेरे डिवाइस में ही रहते है और ..."

REVIEWS = [
    ("German 1 (App won't open)", TEXT_1),
    ("German 2 (Hide song & price)", TEXT_2),
    ("Hindi (Username & lossless)", TEXT_3)
]

async def classify_with_model(client: AsyncGroq, content: str) -> Dict[str, Any]:
    messages = [{"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT}]
    messages.extend(FEW_SHOT_EXAMPLES)
    messages.append({"role": "user", "content": content})
    
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=1024,
            timeout=30.0,
        )
        raw = response.choices[0].message.content
        cleaned = ClassificationEngine._clean_response(raw)
        result = json.loads(cleaned)
        result["_usage"] = response.usage.total_tokens
        return result
    except Exception as e:
        return {"error": str(e)}

async def main():
    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    
    print("# Trimmed Prompt Quality Verification\n")
    sys.stdout.flush()
    total_tokens_used = 0
    successful_calls = 0
    
    for title, text in REVIEWS:
        print(f"## {title}")
        print(f"**Text:** {text[:150]}...\n")
        sys.stdout.flush()
        
        res = await classify_with_model(client, text)
        
        if "error" in res:
            print(f"Error: {res['error']}\n")
            sys.stdout.flush()
            continue
            
        print("| Field | Trimmed 70b Extraction |")
        print("|-------|------------------------|")
        for field in ['core_complaint', 'user_job_to_be_done', 'unmet_need']:
            val = str(res.get(field, 'null')).replace('\n', ' ')
            print(f"| **{field}** | {val} |")
        
        tokens = res.get('_usage', 0)
        print(f"\nTokens used for this review: {tokens}\n")
        sys.stdout.flush()
        
        total_tokens_used += tokens
        successful_calls += 1
        
        await asyncio.sleep(2)
        
    if successful_calls > 0:
        avg_tokens = total_tokens_used / successful_calls
        reviews_per_day = int(100000 / avg_tokens)
        print("---")
        print(f"**Average Tokens per Review:** {avg_tokens:.0f}")
        print(f"**Estimated Reviews per Day (100k Limit):** {reviews_per_day}")
        sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())

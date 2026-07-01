import os
import json
import asyncio
import sys
import re

sys.path.append(os.getcwd())
from app.config.settings import settings
from groq import AsyncGroq

async def generate_synthesis(client, data_for_synthesis):
    prompt = """You are synthesizing UX research findings on music discovery.
    
Below is a JSON list of user reviews relating to discovery and listening behavior, and the research questions they map to.

Please generate two sections for a markdown report based ONLY on this data:
1. EMERGENT PATTERNS: Cluster items by what naturally recurs (emergent grouping, NOT a predefined list). For each cluster: provide a one-line description, review count (prevalence), surface(s) and question(s) it concerns, 2–3 representative verbatim quotes, and whether it spans multiple countries/stores or is concentrated.
2. COVERAGE GAPS: For any of Q1–Q6 with little or no evidence in the reviews, say so explicitly. Do not fabricate signal.

Output ONLY the markdown for these two sections starting with "## 3. EMERGENT PATTERNS". Do not include anything else.
"""
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(data_for_synthesis, indent=2)}
            ],
            temperature=0.2,
            max_tokens=3000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating synthesis: {e}")
        return "## 3. EMERGENT PATTERNS\nError generating patterns.\n\n## 4. COVERAGE GAPS\nError generating gaps."

async def main():
    api_key = settings.GROQ_API_KEY
    if hasattr(settings, "GROQ_API_KEYS") and settings.GROQ_API_KEYS:
        api_key = settings.GROQ_API_KEYS.split(",")[0].strip()
    client = AsyncGroq(api_key=api_key)
    
    with open("secondary_research_appstore_playstore.md", "r") as f:
        lines = f.readlines()
        
    data = []
    in_table = False
    for line in lines:
        if line.startswith("| Quote | Surface"):
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("|"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 10:
                quote = parts[1]
                surface = parts[2]
                mechanism = parts[3]
                mapped = parts[9]
                if quote:
                    data.append({
                        "quote": quote,
                        "surface": surface,
                        "mechanism": mechanism,
                        "mapped_questions": mapped
                    })
        if in_table and not line.startswith("|") and line.strip() != "":
            if line.startswith("## 3. EMERGENT PATTERNS"):
                in_table = False
                break
                
    print(f"Extracted {len(data)} items for synthesis.")
    
    # We will split data into 2 batches if it's too large, but 162 small dicts is very small.
    # We can take just quote, surface, mapped_questions
    minimal_data = [{"q": d["quote"], "s": d["surface"], "m": d["mapped_questions"]} for d in data if d["mapped_questions"]]
    
    # If minimal_data is still large, let's just pass minimal_data
    print(f"JSON length: {len(json.dumps(minimal_data))}")
    synthesis_md = await generate_synthesis(client, minimal_data)
    
    # Replace the error part in the file
    out_lines = []
    for line in lines:
        if line.startswith("## 3. EMERGENT PATTERNS"):
            break
        out_lines.append(line)
        
    out_lines.append(synthesis_md)
    out_lines.append("\n")
    
    with open("secondary_research_appstore_playstore.md", "w") as f:
        f.write("".join(out_lines))
        
    print("Fixed document successfully.")

if __name__ == "__main__":
    asyncio.run(main())

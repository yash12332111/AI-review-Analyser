import os
import json
import sqlite3
import asyncio
import sys
import re

sys.path.append(os.getcwd())
from app.config.settings import settings
from groq import AsyncGroq

async def extract_reviews(client, batch):
    prompt = """You are a rigorous UX researcher extracting signals from app reviews.
    
Your task: Apply a Scope Filter to the provided batch of reviews, and for those that pass, extract specific fields.

SCOPE FILTER:
Include a review ONLY if it relates to music DISCOVERY or LISTENING BEHAVIOR (e.g., recommendations, finding new music, repetition, Discover Weekly, Daily Mix, Release Radar, Home feed, radio/autoplay, Daylist, AI DJ, search-for-music, playlists as a discovery tool, or going off-platform to find music).
EXCLUDE reviews whose core complaint is ads, pricing/paywall, billing, crashes, login, audio quality, or playback bugs — UNLESS the review explicitly ties that to discovery. For mixed reviews, keep only the discovery-relevant portion.

FOR EACH INCLUDED REVIEW, extract exactly what is present:
{
  "verbatim_quote": "<the exact discovery-related quote>",
  "surface": "<the app surface mentioned, e.g. Discover Weekly, Home Feed, Radio>",
  "mechanism": "<open description of how it works or fails>",
  "user_goal": "<user's goal or 'unstated'>",
  "emotion": "<user's exact words describing emotion/reaction>",
  "store": "<pass through from input>",
  "country": "<pass through from input>",
  "rating": "unknown",
  "questions": ["Q1", "Q3"] // Array of mapped questions from the list below (or empty list if none)
}

RESEARCH QUESTIONS TO MAP:
- Q1 — what users BELIEVE the algorithm does (mental model vs reality)
- Q2 — whether repeat-listening is a problem for the USER vs just the business
- Q3 — evidence that repetition IS the user's desired discovery / comfort-by-choice
- Q4 — what distinguishes discovery that "worked" from discovery that "failed"
- Q5 — for users who TRIED to discover, what made them retreat
- Q6 — what users DO when opening the app with no specific track in mind

Return ONLY a valid JSON list of objects. No markdown formatting, no explanation. Just the JSON array.
"""
    
    user_content = "REVIEWS BATCH:\n"
    for r in batch:
        user_content += f"ID: {r['id']}\nStore: {r['source']}\nCountry: {r['country']}\nContent: {r['content']}\n\n"
        
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.0,
            max_tokens=4000
        )
        content = response.choices[0].message.content.strip()
        # strip markdown code blocks if present
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        return json.loads(content)
    except Exception as e:
        print(f"Error processing batch: {e}")
        return []

async def generate_synthesis(client, all_extracted):
    prompt = """You are synthesizing UX research findings on music discovery.
    
Below is a JSON list of all extracted user reviews related to discovery and listening behavior.

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
                {"role": "user", "content": json.dumps(all_extracted, indent=2)}
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
    
    conn = sqlite3.connect(settings.SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # We only want to process unique reviews so we group by feedback.id
    # But for scoping, let's pre-filter lightly in SQL if possible to save tokens?
    # No, the prompt says "apply first" meaning the LLM applies it. 
    # But passing all 530 might take 15 batches. Let's do it.
    rows = conn.execute("""
        SELECT f.id, f.source, f.country, f.content 
        FROM feedback f 
        WHERE f.source IN ('appstore', 'playstore')
    """).fetchall()
    
    # Optional: we can pre-filter in python to save API calls
    keywords = ['discover', 'recommend', 'new music', 'playlist', 'repeat', 'algorithm', 'radio', 'shuffle', 'mix', 'ai dj', 'daylist', 'home', 'find', 'explore', 'similar', 'same song', 'tired of']
    filtered_rows = []
    for r in rows:
        content_lower = r['content'].lower()
        if any(k in content_lower for k in keywords):
            filtered_rows.append(r)
            
    print(f"Total rows: {len(rows)}, Pre-filtered (keyword match) to: {len(filtered_rows)}")
    # Wait, the instructions say "use the existing... classification". If I use the keyword pre-filter I might miss some.
    # Actually let's just process all 530 rows without keyword filter to be perfectly safe, or use the classification columns!
    # Let's query using the classification columns!
    query = """
        SELECT f.id, f.source, f.country, f.content, c.topic, c.core_complaint, c.behaviour_pattern 
        FROM feedback f 
        JOIN classifications c ON f.id = c.feedback_id 
        WHERE f.source IN ('appstore', 'playstore')
    """
    rows_with_class = conn.execute(query).fetchall()
    
    discovery_rows = []
    for r in rows_with_class:
        combined_text = f"{r['content']} {r['topic']} {r['core_complaint']} {r['behaviour_pattern']}".lower()
        # Let's use a broad keyword match on the combined text to reduce noise but keep everything relevant
        if any(k in combined_text for k in keywords):
            discovery_rows.append(r)
        else:
            # If it's short and might be related, just let it pass or rely on keywords
            pass
            
    # Actually, 530 rows is small. Let's just pass all 530 rows to the LLM to be 100% compliant with "do not miss".
    batch_size = 20
    all_extracted = []
    total_processed = 0
    
    print(f"Processing {len(rows_with_class)} reviews in batches of {batch_size}...")
    for i in range(0, len(rows_with_class), batch_size):
        batch = rows_with_class[i:i+batch_size]
        extracted = await extract_reviews(client, batch)
        if isinstance(extracted, list):
            all_extracted.extend(extracted)
        total_processed += len(batch)
        print(f"Processed {total_processed}/{len(rows_with_class)} - Extracted {len(extracted)} relevant items.")
        
    print(f"Total relevant reviews extracted: {len(all_extracted)}")
    
    # Generate Synthesis
    print("Generating emergent patterns and coverage gaps...")
    synthesis_md = await generate_synthesis(client, all_extracted)
    
    # Format the final Markdown document
    store_set = set(r['store'] for r in all_extracted if 'store' in r)
    country_set = set(r['country'] for r in all_extracted if 'country' in r and r['country'])
    
    md_lines = []
    md_lines.append("# Discovery & Listening Behavior: Secondary Research")
    md_lines.append(f"\n## 1. Header")
    md_lines.append(f"- **Total Reviews Scanned**: {len(rows_with_class)}")
    md_lines.append(f"- **Passed Discovery Scope Filter**: {len(all_extracted)}")
    md_lines.append(f"- **Stores Covered**: {', '.join(store_set) if store_set else 'appstore, playstore'}")
    md_lines.append(f"- **Countries Covered**: {', '.join(country_set) if country_set else 'Various'}")
    md_lines.append(f"- **Date Range**: As ingested in SQLite database")
    
    md_lines.append(f"\n## 2. EVIDENCE TABLE\n")
    md_lines.append("| Quote | Surface | Mechanism | User Goal | Emotion | Store | Country | Rating | Questions Mapped |")
    md_lines.append("|-------|---------|-----------|-----------|---------|-------|---------|--------|------------------|")
    
    for item in all_extracted:
        quote = str(item.get('verbatim_quote', '')).replace('\n', ' ').replace('|', '-')
        surface = str(item.get('surface', '')).replace('\n', ' ').replace('|', '-')
        mechanism = str(item.get('mechanism', '')).replace('\n', ' ').replace('|', '-')
        goal = str(item.get('user_goal', '')).replace('\n', ' ').replace('|', '-')
        emotion = str(item.get('emotion', '')).replace('\n', ' ').replace('|', '-')
        store = str(item.get('store', '')).replace('\n', ' ').replace('|', '-')
        country = str(item.get('country', '')).replace('\n', ' ').replace('|', '-')
        rating = str(item.get('rating', 'unknown')).replace('\n', ' ').replace('|', '-')
        qs = item.get('questions', [])
        q_str = ', '.join(qs) if isinstance(qs, list) else str(qs)
        
        md_lines.append(f"| {quote} | {surface} | {mechanism} | {goal} | {emotion} | {store} | {country} | {rating} | {q_str} |")
        
    md_lines.append("\n" + synthesis_md)
    
    with open("secondary_research_appstore_playstore.md", "w") as f:
        f.write("\n".join(md_lines))
        
    print("Document successfully written to secondary_research_appstore_playstore.md")

if __name__ == "__main__":
    asyncio.run(main())

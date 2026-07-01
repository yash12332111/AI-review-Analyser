import asyncio
import os
import json
import httpx
from dotenv import load_dotenv
from groq import AsyncGroq
from pydantic import BaseModel, Field
from typing import Optional

# Load environment variables
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("❌ ERROR: Missing GROQ_API_KEY in .env file.")
    print("Please copy .env.example to .env and add your API key.")
    exit(1)

# Initialize Groq client
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

# Define the Pydantic schema for structured output
class ClassificationResult(BaseModel):
    off_topic: bool = Field(description="True if the review is NOT about Spotify (e.g., about Apple Music, YouTube Music, or completely unrelated).")
    topic: Optional[str] = Field(description="The main subject of the review (e.g., 'Discover Weekly is stale', 'Too many ads', 'App crashing'). Null if off_topic.")
    core_complaint: Optional[str] = Field(description="The specific underlying problem the user is experiencing. Null if off_topic.")
    sentiment: Optional[str] = Field(description="The sentiment of the review: 'positive', 'neutral', or 'negative'. Null if off_topic.")
    frustration_intensity: Optional[str] = Field(description="The level of user frustration: 'low', 'moderate', or 'severe'. Null if off_topic or not frustrated.")
    trust_level: Optional[str] = Field(description="The user's trust in the product: 'high', 'moderate', 'low', or 'broken'. Null if off_topic.")
    churn_risk: Optional[bool] = Field(description="True if the user mentions canceling, switching to a competitor, or deleting the app. Null if off_topic.")
    behaviour_pattern: Optional[str] = Field(description="Any specific way the user changed their behavior due to the app's limitations (e.g., 'manually creates playlists', 'uses last.fm instead'). Null if off_topic.")
    workaround_mentioned: Optional[bool] = Field(description="True if the user describes a workaround they use. Null if off_topic.")
    user_job_to_be_done: Optional[str] = Field(description="The underlying goal the user is trying to achieve (e.g., 'Wants to discover new indie artists', 'Needs a workout playlist'). Null if off_topic.")
    unmet_need: Optional[str] = Field(description="The specific user need that the product is currently failing to meet. Null if off_topic.")

# The prompt instructions
SYSTEM_PROMPT = f"""
You are an expert UX Researcher analyzing user feedback for Spotify.
Your goal is to extract deep insights from the user's review.

Analyze the provided review and extract the 11 specific fields defined in the JSON schema.
Focus specifically on finding workarounds, broken trust, and the core 'job to be done'.

IMPORTANT EDGE CASE RULES:
1. If the review is sarcastic or ironic, classify based on their ACTUAL sentiment, not the literal words.
2. If the review is NOT about Spotify, set off_topic to true and null out the rest.
3. If topic, core_complaint, AND behaviour_pattern are all null, mark the record as off_topic (it has no extractable insights).

Here is the EXACT JSON schema you must follow:
{json.dumps(ClassificationResult.model_json_schema(), indent=2)}
"""

async def classify_review(content: str) -> str:
    """Passes the review to Groq and returns the structured JSON string."""
    try:
        response = await groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content}
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            temperature=0,
        )
        return response.choices[0].message.content
    except Exception as e:
        return json.dumps({"error": str(e)})

async def main():
    print("🚀 Starting Day 1 Vertical Slice (App Store RSS -> Groq)")
    print("-" * 50)
    
    print("📡 Fetching reviews from the App Store RSS Feed...")
    url = "https://itunes.apple.com/us/rss/customerreviews/id=324684580/sortBy=mostRecent/json"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Extract entries, skipping the first one which is usually metadata about the app itself
            entries = data.get("feed", {}).get("entry", [])[1:11]
            
            if not entries:
                print("⚠️ No reviews fetched from the App Store RSS.")
                return
            
    except Exception as e:
        print(f"❌ Failed to fetch reviews: {e}")
        return

    print(f"✅ Fetched {len(entries)} reviews. Classifying through Groq...")
    print("-" * 50)

    for i, review in enumerate(entries):
        title = review.get("title", {}).get("label", "")
        content = review.get("content", {}).get("label", "")
        full_text = f"{title}\n{content}".strip()
        
        print(f"\n[{i+1}/{len(entries)}] REVIEW:")
        print(f"\"{full_text[:150]}...\"" if len(full_text) > 150 else f"\"{full_text}\"")
        
        json_result = await classify_review(full_text)
        
        print(f"🧠 EXTRACTION:")
        try:
            parsed = json.loads(json_result)
            print(json.dumps(parsed, indent=2))
        except:
            print(json_result)
            
        print("-" * 50)
        
        # Adding a small delay to avoid hitting rate limits instantly
        await asyncio.sleep(1)

    print("✨ POC Complete! The 11-field extraction is working on real App Store RSS data.")

if __name__ == "__main__":
    asyncio.run(main())

import re
import logging
from typing import List, Dict, Any
from groq import Groq, RateLimitError

from app.config.settings import settings
from app.retrieval.retriever import FeedbackRetriever
from app.models.feedback import ChatFilters, ClassifiedFeedback

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a user research assistant for a music product team.
You answer questions by synthesizing insights from real user feedback.

RULES:
1. Answer ONLY from the provided review context.
2. Ground every claim in specific user quotes from the provided context.
3. Cite quotes using [Source: platform, Sentiment: value, Date: date] format.
4. If the provided context doesn't cover the question or lacks enough information, say so plainly. Do not attempt to guess or use outside knowledge.
5. Identify patterns across multiple quotes when possible.
6. NEVER invent, fabricate, or hallucinate facts, numbers, or quotes. Only use EXACT text from the provided context.
7. Structure your answers with clear sections when addressing complex questions.
8. Keep your answer concise — aim for 300-500 words. Use bullet points for clarity.
"""

class ChatEngine:
    def __init__(self, retriever: FeedbackRetriever):
        # Build a rotation pool of Groq clients.
        # Priority order: GROQ_CHAT_API_KEY first, then GROQ_API_KEYS, then GROQ_API_KEY.
        keys: List[str] = []

        if settings.GROQ_CHAT_API_KEY:
            keys.append(settings.GROQ_CHAT_API_KEY)

        if settings.GROQ_API_KEYS:
            for k in settings.GROQ_API_KEYS.split(","):
                k = k.strip()
                if k and k not in keys:
                    keys.append(k)

        if settings.GROQ_API_KEY and settings.GROQ_API_KEY not in keys:
            keys.append(settings.GROQ_API_KEY)

        if not keys:
            raise ValueError("No Groq API keys configured. Set GROQ_CHAT_API_KEY or GROQ_API_KEYS.")

        self.clients = [Groq(api_key=k) for k in keys]
        self._key_index = 0
        logger.info(f"ChatEngine: initialized with {len(self.clients)} key(s) in rotation pool.")
        self.retriever = retriever

    def _call_with_rotation(self, **kwargs) -> Any:
        """Try each client in the pool; rotate on 429 RateLimitError."""
        last_error = None
        for _ in range(len(self.clients)):
            client = self.clients[self._key_index]
            try:
                return client.chat.completions.create(**kwargs)
            except RateLimitError as e:
                logger.warning(f"ChatEngine key [{self._key_index}] hit rate limit, rotating to next key. Error: {e}")
                last_error = e
                self._key_index = (self._key_index + 1) % len(self.clients)
            except Exception:
                raise
        raise last_error

    async def answer(self, question: str, filters: ChatFilters) -> dict:
        # 0. Intent routing
        intent_prompt = (
            "Classify the user's intent into exactly one of two categories:\n"
            "1) 'conversational': greetings, chit-chat, reactions (cool, nice, thanks), or off-topic messages.\n"
            "2) 'research': questions or requests about user feedback, features, frustrations, music discovery, or reviews.\n\n"
            "Return ONLY the single word 'conversational' or 'research'. Do not include any other text, punctuation, or explanation."
        )
        try:
            logger.info(f"--- ENTERING INTENT ROUTING for question: '{question}' ---")
            intent_res = self._call_with_rotation(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": intent_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.0,
                max_tokens=10
            )
            intent_raw = intent_res.choices[0].message.content
            intent = re.sub(r'[^a-zA-Z]', '', intent_raw).lower()
            logger.info(f"--- CLASSIFIER RAW OUTPUT: '{intent_raw}' -> PARSED: '{intent}' ---")
            
            if intent != "research":
                conv_res = self._call_with_rotation(
                    model=settings.GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a friendly research assistant for a music product team. Respond briefly, naturally, and politely to the user's conversational message. Do not cite sources or invent feedback."},
                        {"role": "user", "content": question}
                    ],
                    temperature=0.5,
                    max_tokens=150
                )
                return {
                    "answer": conv_res.choices[0].message.content.strip(),
                    "sources": [],
                    "metadata": {"records_retrieved": 0, "intent": "conversational"}
                }
        except Exception as e:
            logger.error(f"Groq API error during intent routing or conversational generation: {e}")
            return {
                "answer": "The assistant is temporarily unavailable — please try again in a moment.",
                "sources": [],
                "metadata": {"records_retrieved": 0, "error": str(e)}
            }

        # 1. Retrieve relevant feedback
        records = self.retriever.hybrid_search(question, filters, top_k=20)
        
        if not records:
            return {
                "answer": "I couldn't find any user feedback matching your question and filters. Try broadening your filters or rephrasing your question.",
                "sources": [],
                "metadata": {"records_retrieved": 0}
            }

        # 2. Build context
        context_str = self._build_context(records)
        
        # 3. Construct messages
        messages = self._build_messages(context_str, question)
        
        # 4. Call Groq API
        try:
            response = self._call_with_rotation(
                model=settings.GROQ_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=1500
            )
            raw_answer = response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API error in RAG chat generation: {e}")
            return {
                "answer": "The assistant is temporarily unavailable — please try again in a moment.",
                "sources": [],
                "metadata": {"records_retrieved": len(records), "error": str(e)}
            }
            
        # 5. Validate quotes
        validated_answer = self._validate_quotes(raw_answer, records)
        
        # Safety net: If the generated answer indicates no relevant information, force sources to empty.
        lower_answer = validated_answer.lower()
        if "[no relevant quotes available]" in lower_answer or \
           "doesn't cover the question" in lower_answer or \
           "not enough information" in lower_answer or \
           "no information" in lower_answer or \
           "no relevant feedback" in lower_answer:
            records = []
        
        sources = []
        for r in records:
            sources.append({
                "quote": r.content,
                "quote_translated": r.quote_translated,
                "source": r.source,
                "sentiment": r.sentiment,
                "date": r.posted_at.isoformat() if r.posted_at else None,
                "country": r.country
            })
            
        return {
            "answer": validated_answer,
            "sources": sources,
            "metadata": {"records_retrieved": len(records)}
        }

    def _build_context(self, records: List[ClassifiedFeedback]) -> str:
        parts = []
        for idx, r in enumerate(records, 1):
            date_str = r.posted_at.strftime('%Y-%m-%d') if r.posted_at else 'Unknown'
            content = r.content
            if r.quote_translated:
                content += f" (English translation: {r.quote_translated})"
            
            parts.append(f"Review {idx}:\nText: {content}\nSource: {r.source}\nSentiment: {r.sentiment}\nDate: {date_str}\n")
        return "\n".join(parts)

    def _build_messages(self, context: str, question: str) -> List[dict]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context records:\n{context}\n\nQuestion: {question}"}
        ]

    def _validate_quotes(self, answer: str, records: List[ClassifiedFeedback]) -> str:
        # Extract quoted strings (between standard double quotes)
        quotes = re.findall(r'"([^"]*)"', answer)
        
        for q in quotes:
            if len(q.strip()) < 10:
                continue # Skip small words or phrases
            
            q_norm = re.sub(r'\s+', ' ', q.lower().strip())
            found = False
            for r in records:
                r_norm = re.sub(r'\s+', ' ', r.content.lower().strip())
                if q_norm in r_norm:
                    found = True
                    break
                if r.quote_translated:
                    rt_norm = re.sub(r'\s+', ' ', r.quote_translated.lower().strip())
                    if q_norm in rt_norm:
                        found = True
                        break
            
            if not found:
                # Replace hallucinated quote
                answer = answer.replace(f'"{q}"', '[quote could not be verified]')
                
        return answer

    def get_suggested_questions(self) -> List[str]:
        return [
            "Why do users complain about Discover Weekly?",
            "What frustrates users most about shuffle?",
            "Why do users keep repeating the same songs?",
            "What are the main workarounds users have for finding new music?",
            "Are there different challenges between iOS and Android users?",
            "What are consistent unmet needs across different sources?"
        ]

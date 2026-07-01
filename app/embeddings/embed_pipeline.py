from __future__ import annotations
"""
EmbeddingPipeline — embeds classified feedback into ChromaDB for
semantic search and RAG retrieval.

Uses sentence-transformers (all-MiniLM-L6-v2) for embedding and
ChromaDB (persistent, local) for vector storage.  Every document is
upserted with classification metadata so downstream consumers can
apply metadata filters at query time.

Design notes (from Architecture.md §4.2 / implementation_plan.md Task 4.1):
- Uses `get_or_create_collection()`, never `get_collection()` alone.
- Uses `collection.upsert()` (idempotent) so backfills are safe to re-run.
- Metadata values are str | int | float | bool — never None or list.
  None values are converted to "" before storage.
- Content shorter than 30 chars is skipped (produces low-quality embeddings).
"""

import logging
from typing import Optional, List, Dict, Any

from sentence_transformers import SentenceTransformer
import chromadb

from app.config.settings import settings
from app.models.feedback import ClassifiedFeedback

logger = logging.getLogger(__name__)

# Minimum content length worth embedding — shorter texts produce
# embeddings that are too generic and match too many queries.
MIN_EMBED_CONTENT_LENGTH = 30


class EmbeddingPipeline:
    """Embeds classified feedback into ChromaDB and provides semantic search."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        persist_dir: Optional[str] = None,
    ):
        model_name = model_name or settings.EMBEDDING_MODEL
        persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR

        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)

        logger.info(f"Connecting to ChromaDB at: {persist_dir}")
        self.chroma_client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.chroma_client.get_or_create_collection(
            name="feedback",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB collection 'feedback' ready — "
            f"{self.collection.count()} documents"
        )

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def embed_and_store(self, records: List[ClassifiedFeedback]) -> int:
        """Embed classified feedback and upsert into ChromaDB.

        Returns:
            Count of records actually embedded (after length filtering).
        """
        if not records:
            return 0

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for rec in records:
            # Skip content too short for meaningful embeddings
            if len((rec.content or "").strip()) < MIN_EMBED_CONTENT_LENGTH:
                logger.debug(
                    f"Skipping {rec.id} — content too short "
                    f"({len((rec.content or '').strip())} chars)"
                )
                continue

            ids.append(rec.id)
            documents.append(rec.content)
            metadatas.append(self._build_metadata(rec))

        if not ids:
            logger.info("No records met the minimum length for embedding.")
            return 0

        # Batch embed
        embeddings = self.model.encode(documents, show_progress_bar=False)

        # Upsert in chunks of 100 (ChromaDB best practice for large batches)
        chunk_size = 100
        for start in range(0, len(ids), chunk_size):
            end = start + chunk_size
            self.collection.upsert(
                ids=ids[start:end],
                documents=documents[start:end],
                embeddings=[emb.tolist() for emb in embeddings[start:end]],
                metadatas=metadatas[start:end],
            )

        logger.info(
            f"Embedded {len(ids)} records into ChromaDB "
            f"(skipped {len(records) - len(ids)} short)"
        )
        return len(ids)

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def query(
        self,
        text: str,
        n_results: int = 20,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search via cosine similarity.

        Args:
            text:       Natural-language query.
            n_results:  Max results to return.
            where:      Optional ChromaDB metadata filter dict.

        Returns:
            List of dicts with keys: id, document, metadata, distance.
        """
        query_embedding = self.model.encode([text])[0].tolist()

        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, self.collection.count() or 1),
        }
        if where:
            kwargs["where"] = where

        raw = self.collection.query(**kwargs)

        results: List[Dict[str, Any]] = []
        for i in range(len(raw["ids"][0])):
            results.append(
                {
                    "id": raw["ids"][0][i],
                    "document": raw["documents"][0][i] if raw["documents"] else None,
                    "metadata": raw["metadatas"][0][i] if raw["metadatas"] else {},
                    "distance": raw["distances"][0][i] if raw["distances"] else None,
                }
            )
        return results

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_collection_count(self) -> int:
        """Return total number of documents in the collection."""
        return self.collection.count()

    def get_embedded_ids(self) -> List[str]:
        """Return all document IDs currently in ChromaDB."""
        result = self.collection.get(include=[])
        return result["ids"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_metadata(rec: ClassifiedFeedback) -> Dict[str, Any]:
        """Build a ChromaDB-safe metadata dict from a ClassifiedFeedback record.

        ChromaDB metadata values must be str | int | float | bool.
        None is converted to "" (empty string).
        """

        def _safe(val: Any) -> Any:
            """Convert None to empty string; pass through str/int/float/bool."""
            if val is None:
                return ""
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                return val
            return str(val)

        return {
            "source": _safe(rec.source),
            "country": _safe(rec.country),
            "posted_at": rec.posted_at.isoformat() if rec.posted_at else "",
            "topic": _safe(rec.topic),
            "core_complaint": _safe(rec.core_complaint),
            "sentiment": _safe(rec.sentiment),
            "frustration_intensity": _safe(rec.frustration_intensity),
            "trust_level": _safe(rec.trust_level),
            "behaviour_pattern": _safe(rec.behaviour_pattern),
            "workaround_mentioned": rec.workaround_mentioned,
            "has_unmet_need": rec.unmet_need is not None and rec.unmet_need != "",
        }

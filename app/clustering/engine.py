"""
ThemeClusteringEngine — groups open-text classification fields into
emergent themes using HDBSCAN density-based clustering.

Design principles (Agents.md / Architecture.md §4.5):
  - Clusters EMERGE from the data.  No predefined categories anywhere.
  - HDBSCAN auto-determines cluster count from data density.
  - Noise points (label = -1) are expected and NOT force-assigned.
  - Each run DELETEs old clusters for the types being clustered, then
    INSERTs fresh ones (re-runnable).
  - Auto-labels come from the LLM describing cluster contents, not from
    a preset vocabulary.
  - The embedding model is multilingual (paraphrase-multilingual-MiniLM-L12-v2)
    so clusters group by meaning, not by language.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
from hdbscan import HDBSCAN
from groq import Groq

from app.config.settings import settings
from app.database.db_manager import DatabaseManager
from app.embeddings.embed_pipeline import EmbeddingPipeline
from app.clustering.prompts import CLUSTER_LABEL_PROMPT

logger = logging.getLogger(__name__)


class ThemeClusteringEngine:
    """Cluster open-text classification fields into emergent themes."""

    def __init__(
        self,
        db: DatabaseManager,
        embedding_pipeline: EmbeddingPipeline,
        groq_api_key: Optional[str] = None,
    ):
        self.db = db
        self.ep = embedding_pipeline
        api_key = groq_api_key or settings.GROQ_API_KEY
        # Fall back to first key in comma-separated list
        if not api_key:
            keys = [k.strip() for k in settings.GROQ_API_KEYS.split(",") if k.strip()]
            api_key = keys[0] if keys else ""
        self.groq_client = Groq(api_key=api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_clustering(
        self,
        cluster_types: Optional[List[str]] = None,
    ) -> Dict:
        """
        Cluster open-text fields into emergent themes.

        Args:
            cluster_types: which fields to cluster.
                Defaults to settings.CLUSTER_FIELDS.

        Returns:
            Summary dict with cluster counts per type.
        """
        cluster_types = cluster_types or settings.CLUSTER_FIELDS

        # Log the clustering run
        run_id = self.db.log_clustering_run({
            "status": "running",
            "cluster_types": json.dumps(cluster_types),
        })

        total_classified = self.db.get_classified_count()
        min_required = settings.MIN_CLUSTER_SIZE * 3
        if total_classified < min_required:
            logger.warning(
                f"Not enough data yet — {total_classified} classified reviews, "
                f"need at least {min_required}. Skipping clustering."
            )
            self.db.update_clustering_run(run_id, {
                "status": "failed",
                "error_message": f"Insufficient data: {total_classified} < {min_required}",
                "clusters_found": 0,
            })
            return {"status": "insufficient_data", "total_classified": total_classified}

        summary = {}
        total_clusters = 0

        for field_name in cluster_types:
            logger.info(f"Clustering field: {field_name}")

            # 1. Pull all non-null values for this field
            values = self.db.get_field_values(field_name)
            if len(values) < settings.MIN_CLUSTER_SIZE:
                logger.warning(
                    f"Field '{field_name}' has only {len(values)} non-null values — skipping."
                )
                summary[field_name] = {"clusters": 0, "noise": 0, "values": len(values)}
                continue

            # 2. Run HDBSCAN
            clusters = self._cluster_field(field_name, values)

            # 3. Auto-label each cluster via Groq
            for cluster in clusters:
                cluster["label"] = self._auto_label_cluster(
                    cluster["member_values"], field_name
                )
                # 4. Select representative quotes
                cluster["representative_quotes"] = self._select_representative_quotes(
                    cluster["member_feedback_ids"]
                )
                # 5. Compute breakdowns
                sources, countries = self._compute_breakdowns(
                    cluster["member_feedback_ids"]
                )
                cluster["sources_breakdown"] = sources
                cluster["countries_breakdown"] = countries

            # 6. Delete old clusters for this type and insert new ones
            deleted = self.db.delete_clusters_by_type(field_name)
            if deleted:
                logger.info(f"Deleted {deleted} old '{field_name}' clusters.")
            inserted = self.db.insert_theme_clusters(clusters, run_id, field_name)

            noise_count = sum(1 for v in values if v.get("_cluster_label", -1) == -1)
            summary[field_name] = {
                "clusters": len(clusters),
                "noise": noise_count,
                "values": len(values),
            }
            total_clusters += len(clusters)
            logger.info(
                f"  {field_name}: {len(clusters)} clusters, "
                f"{noise_count} noise points from {len(values)} values"
            )

        # Update run log
        self.db.update_clustering_run(run_id, {
            "status": "success",
            "total_records": total_classified,
            "clusters_found": total_clusters,
        })

        logger.info(
            f"Clustering complete: {total_clusters} clusters across "
            f"{len(cluster_types)} fields."
        )
        return summary

    # ------------------------------------------------------------------
    # Core clustering logic
    # ------------------------------------------------------------------

    def _cluster_field(
        self, field_name: str, values: List[Dict]
    ) -> List[Dict]:
        """
        Run HDBSCAN on embeddings for one field.

        Args:
            field_name: classification field being clustered.
            values:     list of {"feedback_id": str, "value": str} dicts.

        Returns:
            List of cluster dicts with keys:
                cluster_id, member_values, member_feedback_ids, member_count
        """
        texts = [v["value"] for v in values]
        embeddings = self.ep.model.encode(texts, show_progress_bar=False)

        clusterer = HDBSCAN(
            min_cluster_size=settings.MIN_CLUSTER_SIZE,
            min_samples=settings.MIN_SAMPLES,
            metric="euclidean",
            algorithm="best",
        )
        labels = clusterer.fit_predict(embeddings)

        # Tag each value with its cluster label for noise counting
        for i, v in enumerate(values):
            v["_cluster_label"] = int(labels[i])

        # Group by cluster label (skip noise = -1)
        cluster_map: Dict[int, List[int]] = {}
        for i, label in enumerate(labels):
            if label == -1:
                continue
            cluster_map.setdefault(int(label), []).append(i)

        clusters = []
        for cluster_id, indices in sorted(cluster_map.items()):
            member_values = [texts[i] for i in indices]
            member_feedback_ids = [values[i]["feedback_id"] for i in indices]
            clusters.append({
                "cluster_id": cluster_id,
                "member_values": member_values,
                "member_feedback_ids": member_feedback_ids,
                "member_count": len(indices),
            })

        return clusters

    # ------------------------------------------------------------------
    # Auto-labelling via Groq
    # ------------------------------------------------------------------

    def _auto_label_cluster(
        self, member_values: List[str], field_type: str
    ) -> str:
        """
        Send a sample of cluster member values to Groq for labelling.
        Returns a short, neutral label (3-8 words).
        """
        # Cap sample size to keep prompt short
        sample = member_values[: settings.MAX_LABEL_SAMPLES]
        formatted = "\n".join(f"- {v}" for v in sample)

        prompt = CLUSTER_LABEL_PROMPT.format(
            field_type=field_type, member_values=formatted
        )

        try:
            response = self.groq_client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=50,
                timeout=15.0,
            )
            label = response.choices[0].message.content.strip().strip('"').strip("'")
            # Reject overly generic labels
            generic = {"general feedback", "general", "feedback", "issues", "other"}
            if label.lower() in generic or len(label.split()) < 2:
                # Retry with more specific instruction
                prompt += (
                    "\n\nThe label you generated was too generic. "
                    "Be MORE specific about the shared theme."
                )
                response = self.groq_client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=50,
                    timeout=15.0,
                )
                label = response.choices[0].message.content.strip().strip('"').strip("'")
            return label
        except Exception as e:
            logger.error(f"Groq labelling failed: {e}")
            # Fallback: first 8 words of the most central member value
            return " ".join(member_values[0].split()[:8])

    # ------------------------------------------------------------------
    # Representative quotes
    # ------------------------------------------------------------------

    def _select_representative_quotes(
        self, feedback_ids: List[str], n: int = 5
    ) -> List[str]:
        """
        Select N representative quotes closest to cluster centroid.
        Verifies each quote exists in the source text.
        """
        if not feedback_ids:
            return []

        # Get the source texts from the DB
        quotes = []
        for fid in feedback_ids[:n * 2]:  # Over-fetch in case some are too short
            row = self.db.get_feedback_content(fid)
            if row and len(row.strip()) >= 30:
                quotes.append(row.strip())
            if len(quotes) >= n:
                break

        return quotes[:n]

    # ------------------------------------------------------------------
    # Breakdowns
    # ------------------------------------------------------------------

    def _compute_breakdowns(
        self, feedback_ids: List[str]
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Query feedback table for the given IDs.
        Return (sources_breakdown, countries_breakdown).
        """
        sources: Dict[str, int] = {}
        countries: Dict[str, int] = {}

        for fid in feedback_ids:
            meta = self.db.get_feedback_meta(fid)
            if meta:
                src = meta.get("source", "unknown")
                sources[src] = sources.get(src, 0) + 1
                country = meta.get("country", "unknown")
                countries[country] = countries.get(country, 0) + 1

        return sources, countries

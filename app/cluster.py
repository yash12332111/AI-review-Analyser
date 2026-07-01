"""
CLI entry point for the Theme Clustering Engine (Phase 4.5).

Usage:
    python -m app.cluster                         # Cluster all 4 fields
    python -m app.cluster --field topic            # Cluster just one field
    python -m app.cluster --field core_complaint   # Cluster just complaints
"""
from __future__ import annotations

import argparse
import logging
import json
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from app.config.settings import settings
from app.database.db_manager import DatabaseManager
from app.embeddings.embed_pipeline import EmbeddingPipeline
from app.clustering.engine import ThemeClusteringEngine


def main():
    parser = argparse.ArgumentParser(description="Run theme clustering on classified reviews.")
    parser.add_argument(
        "--field",
        type=str,
        default=None,
        help="Cluster a single field (topic, core_complaint, behaviour_pattern, unmet_need).",
    )
    args = parser.parse_args()

    db = DatabaseManager(settings.SQLITE_DB_PATH)
    db.initialize()
    ep = EmbeddingPipeline()

    engine = ThemeClusteringEngine(db=db, embedding_pipeline=ep)

    cluster_types = [args.field] if args.field else None
    summary = engine.run_clustering(cluster_types=cluster_types)

    if summary.get("status") == "insufficient_data":
        print(f"\n⚠️  Not enough data for clustering ({summary['total_classified']} classified reviews).")
        sys.exit(0)

    print("\n" + "=" * 60)
    print("📊 Clustering Results")
    print("=" * 60)

    for field, info in summary.items():
        if field == "status":
            continue
        print(f"\n  {field}: {info['clusters']} clusters "
              f"({info['noise']} noise points from {info['values']} values)")

    # Show the actual clusters
    all_clusters = db.get_theme_clusters()
    current_type = None
    for c in all_clusters:
        if c["cluster_type"] != current_type:
            current_type = c["cluster_type"]
            print(f"\n{'─' * 50}")
            print(f"  Field: {current_type}")
            print(f"{'─' * 50}")
        quotes = json.loads(c["representative_quotes"]) if c["representative_quotes"] else []
        sources = json.loads(c["sources_breakdown"]) if c["sources_breakdown"] else {}
        print(f"\n  ▸ {c['label']}  ({c['member_count']} reviews)")
        print(f"    Sources: {sources}")
        for q in quotes[:2]:
            short = q[:100] + "..." if len(q) > 100 else q
            print(f"    ‣ \"{short}\"")

    db.close()


if __name__ == "__main__":
    main()

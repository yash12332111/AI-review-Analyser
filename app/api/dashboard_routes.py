from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.database.db_manager import DatabaseManager
from app.models.feedback import DashboardFilters
from app.config.settings import settings
from app.config.filters import DISCOVERY_KEYWORDS

router = APIRouter()

def get_db():
    db = DatabaseManager(settings.SQLITE_DB_PATH)
    try:
        yield db
    finally:
        db.close()

def _normalize_topic(topic: str) -> str:
    if not topic: return ""
    t = str(topic).strip()
    if t.lower() in ("null", "none", "n/a", "undefined") or t == "": return ""
    return t

def _get_canonical_key(topic: str) -> str:
    import string
    t = topic.lower().translate(str.maketrans('', '', string.punctuation))
    words = [w for w in t.split() if w not in ('the', 'a', 'an', 'and', 'or', 'of', 'in', 'to', 'for', 'with')]
    return " ".join(sorted(words))


def build_filters(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    source: Optional[str] = None,
    country: Optional[str] = None,
    sentiment: Optional[str] = None,
    topic: Optional[str] = None,
    discovery_filter: Optional[bool] = False
) -> DashboardFilters:
    return DashboardFilters(
        date_from=date_from,
        date_to=date_to,
        source=source,
        country=country,
        sentiment=sentiment,
        topic=topic,
        discovery_filter=discovery_filter
    )

@router.get("/config")
def get_config():
    """Shared config like discovery keywords"""
    return {"discovery_keywords": DISCOVERY_KEYWORDS}

@router.get("/summary")
def get_summary(
    filters: DashboardFilters = Depends(build_filters),
    db: DatabaseManager = Depends(get_db)
):
    """Total feedback, count by source, count by sentiment."""
    return db.get_summary_stats(filters)

@router.get("/topics")
def get_topics(
    filters: DashboardFilters = Depends(build_filters),
    db: DatabaseManager = Depends(get_db)
):
    """Most common topics."""
    distribution = db.get_topic_distribution(filters)
    
    canonical_map = {}
    for raw_topic, count in distribution.items():
        topic = _normalize_topic(raw_topic)
        if not topic: continue
        
        key = _get_canonical_key(topic)
        if not key: continue
        
        if key not in canonical_map:
            canonical_map[key] = {"variants": {}, "count": 0}
        canonical_map[key]["variants"][topic] = canonical_map[key]["variants"].get(topic, 0) + count
        canonical_map[key]["count"] += count

    for data in canonical_map.values():
        best_display = max(data["variants"].items(), key=lambda x: x[1])[0]
        data["display"] = best_display[:1].upper() + best_display[1:] if best_display else best_display

    total = sum(d["count"] for d in canonical_map.values())
    sorted_topics = sorted(canonical_map.values(), key=lambda x: x["count"], reverse=True)
    
    results = []
    for item in sorted_topics:
        results.append({
            "value": item["display"],
            "count": item["count"],
            "percentage": (item["count"] / total * 100) if total > 0 else 0
        })
    return results

@router.get("/complaints")
def get_complaints(
    filters: DashboardFilters = Depends(build_filters),
    db: DatabaseManager = Depends(get_db)
):
    """Top core complaints."""
    # We could calculate delta here if we did a historical query,
    # but for now just return the current ranking.
    ranking = db.get_complaint_ranking(filters)
    for c in ranking:
        c["value"] = c.pop("core_complaint")
        c["delta_pct"] = 0 # Placeholder for delta
    return ranking

@router.get("/behaviours")
def get_behaviours(
    filters: DashboardFilters = Depends(build_filters),
    db: DatabaseManager = Depends(get_db)
):
    """Common behaviour patterns extracted. This is equivalent to getting clustering for behaviours."""
    # We can use the theme clusters for behaviour_pattern
    clusters = db.get_theme_clusters("behaviour_pattern", filters=filters)
    return [{"value": c["label"], "count": c["member_count"]} for c in clusters]

@router.get("/workarounds")
def get_workarounds(
    filters: DashboardFilters = Depends(build_filters),
    db: DatabaseManager = Depends(get_db)
):
    """Workaround records."""
    records = db.get_workarounds(filters, limit=50)
    return [
        {
            "content": r.workaround_description,
            "source": r.source,
            "sentiment": r.sentiment,
            "date": r.posted_at.isoformat() if r.posted_at else None
        }
        for r in records
    ]

@router.get("/trends")
def get_trends(
    db: DatabaseManager = Depends(get_db)
):
    """Time series: topic trends for 30 days."""
    raw_trends = db.get_topic_trends(30)
    
    global_variants = {}
    daily_counts = {}
    
    for row in raw_trends:
        topic = _normalize_topic(row["topic"])
        if not topic: continue
        key = _get_canonical_key(topic)
        if not key: continue
        
        if key not in global_variants:
            global_variants[key] = {}
        global_variants[key][topic] = global_variants[key].get(topic, 0) + row["count"]
        
        day = row["day"]
        pair = (day, key)
        daily_counts[pair] = daily_counts.get(pair, 0) + row["count"]

    best_display = {}
    for key, variants in global_variants.items():
        best = max(variants.items(), key=lambda x: x[1])[0]
        best_display[key] = best[:1].upper() + best[1:] if best else best

    results = []
    for (day, key), count in daily_counts.items():
        results.append({
            "day": day,
            "topic": best_display[key],
            "count": count
        })
    return results

@router.get("/quotes")
def get_quotes(
    filters: DashboardFilters = Depends(build_filters),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DatabaseManager = Depends(get_db)
):
    """Paginated verbatim quotes with metadata."""
    records = db.query_feedback(filters, limit=limit, offset=offset)
    return {
        "data": [r.model_dump(mode='json') for r in records],
        "has_more": len(records) == limit
    }

@router.get("/themes")
def get_themes(
    filters: DashboardFilters = Depends(build_filters),
    db: DatabaseManager = Depends(get_db)
):
    """All emergent theme clusters."""
    return db.get_theme_clusters(filters=filters)

@router.get("/themes/{cluster_type}")
def get_themes_by_type(
    cluster_type: str,
    filters: DashboardFilters = Depends(build_filters),
    db: DatabaseManager = Depends(get_db)
):
    """Clusters for a specific type."""
    return db.get_theme_clusters(cluster_type, filters=filters)

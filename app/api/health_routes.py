from fastapi import APIRouter, Depends
from typing import Dict, Any
import time

from app.database.db_manager import DatabaseManager
from app.config.settings import settings
from app.scheduler.scheduler import scheduler

router = APIRouter()

def get_db():
    db = DatabaseManager(settings.SQLITE_DB_PATH)
    try:
        yield db
    finally:
        db.close()

@router.api_route("", methods=["GET", "HEAD"])
async def system_health(db: DatabaseManager = Depends(get_db)) -> Dict[str, Any]:
    # Check DB
    try:
        db.conn.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        
    total_feedback = db.conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    total_classified = db.get_classified_count()
    
    # Scheduler info
    next_run = None
    if scheduler.running:
        job = scheduler.get_job("nightly_pipeline")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
            
    last_run = db.conn.execute(
        "SELECT started_at, completed_at, status FROM collection_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "version": "1.0.0",
        "database": {
            "status": db_status,
            "total_records": total_feedback,
            "total_classified": total_classified
        },
        "scheduler": {
            "running": scheduler.running,
            "next_scheduled_run": next_run
        },
        "pipeline": {
            "last_run_started": last_run["started_at"] if last_run else None,
            "last_run_completed": last_run["completed_at"] if last_run else None,
            "last_run_status": last_run["status"] if last_run else None
        }
    }

@router.get("/sources")
async def source_health(db: DatabaseManager = Depends(get_db)) -> Dict[str, Any]:
    sources = db.conn.execute("SELECT source, COUNT(*) as cnt FROM feedback GROUP BY source").fetchall()
    source_stats = {}
    for s in sources:
        source_name = s["source"]
        last_success = db.get_last_collection_time(source_name)
        source_stats[source_name] = {
            "total_records": s["cnt"],
            "last_success": last_success.isoformat() if last_success else None
        }
    return source_stats

@router.get("/pipeline")
async def pipeline_health(db: DatabaseManager = Depends(get_db)) -> Dict[str, Any]:
    last_runs = db.conn.execute(
        "SELECT source, started_at, completed_at, records_fetched, records_new, status, error_message FROM collection_runs ORDER BY id DESC LIMIT 10"
    ).fetchall()
    
    runs = [dict(r) for r in last_runs]
    return {
        "recent_collection_runs": runs
    }

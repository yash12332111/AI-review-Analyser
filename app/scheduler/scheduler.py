import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.scheduler.pipeline import NightlyPipeline
from app.config.settings import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

def start_scheduler():
    pipeline = NightlyPipeline()
    scheduler.add_job(
        pipeline.run,
        trigger=CronTrigger(hour=settings.COLLECTION_HOUR, minute=settings.COLLECTION_MINUTE),
        id="nightly_pipeline",
        name="Nightly Feedback Pipeline",
        misfire_grace_time=3600,
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started. Nightly Pipeline set to run at {settings.COLLECTION_HOUR:02d}:{settings.COLLECTION_MINUTE:02d} UTC.")

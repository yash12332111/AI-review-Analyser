import asyncio
from app.scheduler.pipeline import NightlyPipeline
from app.config.logging_config import setup_logging

async def main():
    setup_logging()
    pipeline = NightlyPipeline()
    await pipeline.run()

if __name__ == "__main__":
    asyncio.run(main())

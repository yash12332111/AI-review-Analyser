import asyncio
import json
from app.api.health_routes import system_health
from app.database.db_manager import DatabaseManager
from app.config.settings import settings

async def print_health():
    db = DatabaseManager(settings.SQLITE_DB_PATH)
    try:
        health_data = await system_health(db)
        print("--- System Health ---")
        print(json.dumps(health_data, indent=2))
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(print_health())

"""
Database / infrastructure initialization script.

Replaced the old PostgreSQL init (init.sql + SQLAlchemy engine) with:
  1. MongoDB index creation (via motor)
  2. Qdrant collection creation (via qdrant-client)

Run this script manually before first startup, or let the app lifespan
handler in main.py call it automatically.

Usage:
    cd backend
    python init_db.py
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


async def init_all():
    logger.info("Initializing MongoDB indexes...")
    from models.mongodb import create_indexes
    await create_indexes()
    logger.info("MongoDB indexes created.")

    logger.info("Initializing Qdrant collection...")
    from models.qdrant_client import ensure_collection
    await ensure_collection()
    logger.info("Qdrant collection ready.")


if __name__ == "__main__":
    asyncio.run(init_all())
    print("Infrastructure initialized successfully!")

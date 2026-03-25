"""Memory service factory helpers to keep DB access out of cogs."""

from __future__ import annotations

from typing import Optional
import os

from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def create_discord_memory_store(
    profile_collection: str = "users",
    session_collection: str = "chat_sessions",
    narrative_collection: str = "shared_narratives",
    db_name: Optional[str] = None,
):
    """Create a MongoMemoryStore configured for Discord context."""
    from abby_core.database.mongodb import is_mongodb_available, connect_to_mongodb
    from tdos_intelligence.memory.storage import MongoMemoryStore

    if not is_mongodb_available():
        raise ConnectionError("MongoDB is not available - memory features disabled")

    mongo_client = connect_to_mongodb()
    resolved_db_name = db_name or os.getenv("MONGODB_DB", "Abby_Database")

    return MongoMemoryStore(
        storage_client=mongo_client,
        db_name=resolved_db_name,
        profile_collection=profile_collection,
        session_collection=session_collection,
        narrative_collection=narrative_collection,
    )


def create_discord_memory_service(
    profile_collection: str = "users",
    session_collection: str = "chat_sessions",
    narrative_collection: str = "shared_narratives",
    db_name: Optional[str] = None,
    logger_override=None,
):
    """Create a MemoryService configured for Discord context."""
    from tdos_intelligence.memory.service import create_memory_service

    store = create_discord_memory_store(
        profile_collection=profile_collection,
        session_collection=session_collection,
        narrative_collection=narrative_collection,
        db_name=db_name,
    )

    return create_memory_service(
        store=store,
        source_id="discord",
        logger=logger_override or logger,
    )

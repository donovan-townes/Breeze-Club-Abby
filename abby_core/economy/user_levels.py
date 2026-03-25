"""
Persistent user level tracking (guild-scoped).

This module separates permanent levels from seasonal XP so that seasonal resets
only zero XP while levels continue to reflect lifetime progress.
"""

from datetime import datetime
from typing import Optional
from abby_core.database.mongodb import get_database
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


def get_user_levels_collection():
    """Return the user_levels collection (guild-scoped, permanent levels)."""
    db = get_database()
    return db["user_levels"]


def ensure_user_level_record(user_id: str, guild_id: Optional[str], level: int = 1) -> None:
    """Ensure a level record exists for a user/guild without lowering the level."""
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id is not None else None
    coll = get_user_levels_collection()
    query = {"user_id": user_id, "guild_id": guild_id}
    now = datetime.utcnow()

    # Only bump last_updated if record already exists; upsert for first insert.
    # NOTE: Cannot have same field in both $setOnInsert and $set - use only $set to avoid conflict
    coll.update_one(
        query,
        {
            "$setOnInsert": {
                "user_id": user_id,
                "guild_id": guild_id,
                "level": level,
                "earned_at": now,
            },
            "$set": {"last_updated": now},
        },
        upsert=True,
    )


def set_user_level(user_id: str, guild_id: Optional[str], level: int, force: bool = False) -> int:
    """Set the permanent level for a user/guild.

    By default this never downgrades. Set force=True to allow explicit resets/downgrades.
    """
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id is not None else None
    coll = get_user_levels_collection()
    query = {"user_id": user_id, "guild_id": guild_id}
    now = datetime.utcnow()

    existing = coll.find_one(query, {"level": 1})
    new_level = level

    if not force and existing and "level" in existing:
        # Default behavior: never downgrade
        new_level = max(existing.get("level", level), level)

    coll.update_one(
        query,
        {
            "$set": {"level": new_level, "last_updated": now},
            "$setOnInsert": {"earned_at": now},
        },
        upsert=True,
    )

    return new_level


def reset_levels_for_guild(guild_id: str, target_level: int = 1) -> int:
    """Force-set level for all records in a guild to the target level.

    Returns the number of documents modified.
    """
    guild_id = str(guild_id)
    coll = get_user_levels_collection()
    now = datetime.utcnow()
    result = coll.update_many(
        {"guild_id": guild_id},
        {"$set": {"level": target_level, "last_updated": now}},
    )
    return result.modified_count if result else 0


def get_user_level_record(user_id: str, guild_id: Optional[str]) -> Optional[dict]:
    """Retrieve the full level record for a user/guild."""
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id is not None else None
    coll = get_user_levels_collection()
    query = {"user_id": user_id, "guild_id": guild_id}
    return coll.find_one(query)

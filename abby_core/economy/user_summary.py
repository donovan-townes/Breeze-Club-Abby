"""
User Summary: Materialized view of current user state.

This is NOT a source of truth. It's a derived, operator-safe aggregation that answers:
"What is this user's current authoritative state under the current system state?"

Properties:
- Cheap to rebuild (just queries source collections)
- Safe to rollback (derive from immutable sources)
- Safe for operators to inspect and debug
- Version-tracked for consistency

Think of it as a cached view, not a ledger.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from bson import ObjectId
from abby_core.database.mongodb import get_database
from abby_core.system.system_state import get_active_season
from abby_core.economy.xp import get_xp as get_user_xp_doc
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


# ==================== COLLECTION ACCESS ====================

def get_user_summary_collection():
    """Get the user_summary collection (materialized view)."""
    db = get_database()
    return db["user_summary"]


# ==================== SUMMARY GENERATION ====================

def compute_user_summary(
    user_id: int,
    guild_id: int,
    force_rebuild: bool = False,
) -> Optional[Dict[str, Any]]:
    """Compute or retrieve user summary.
    
    This aggregates current state from:
    - user_xp (seasonal XP points)
    - user_level (permanent level) - derived from XP but cached
    - system_state (current season)
    - system_events (last applied event)
    
    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
        force_rebuild: If True, ignore cache and recompute
    
    Returns:
        dict: User summary, or None if user has no data
    """
    user_id_str = str(user_id)
    guild_id_str = str(guild_id)
    
    summary_collection = get_user_summary_collection()
    
    # Try cache first (unless forced rebuild)
    if not force_rebuild:
        cached = summary_collection.find_one({
            "user_id": user_id_str,
            "guild_id": guild_id_str,
        })
        
        if cached:
            # Cache is valid if < 5 minutes old
            cache_age = (datetime.utcnow() - cached.get("computed_at", datetime.utcnow())).total_seconds()
            if cache_age < 300:  # 5 minutes
                return cached
    
    # Rebuild from source
    user_xp_doc = get_user_xp_doc(user_id, guild_id)
    
    if not user_xp_doc:
        # User has no XP data; summary doesn't exist
        return None
    
    # Get current season
    active_season = get_active_season()
    current_season_id = active_season.get("state_id") if active_season else None
    
    # Build summary
    summary = {
        "user_id": user_id_str,
        "guild_id": guild_id_str,
        
        # Current state
        "level": user_xp_doc.get("level", 1),
        "xp": user_xp_doc.get("points", 0),
        
        # Context
        "current_season_id": current_season_id,
        "last_xp_update": user_xp_doc.get("updated_at", user_xp_doc.get("created_at")),
        
        # Computed timestamps
        "computed_at": datetime.utcnow(),
        "version": 1,  # For schema migrations
    }
    
    # Update cache
    try:
        summary_collection.update_one(
            {
                "user_id": user_id_str,
                "guild_id": guild_id_str,
            },
            {"$set": summary},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[⚠️] Failed to cache user summary: {e}")
        # Still return the computed summary even if cache write failed
    
    return summary


def get_user_summary(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Get cached or computed user summary."""
    return compute_user_summary(user_id, guild_id, force_rebuild=False)


def rebuild_user_summary(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Force rebuild of user summary from source."""
    return compute_user_summary(user_id, guild_id, force_rebuild=True)


# ==================== BULK SUMMARY OPERATIONS ====================

def compute_guild_summaries(guild_id: int) -> int:
    """Rebuild all user summaries for a guild.
    
    This is expensive and should only be done:
    - After season rollover
    - After major XP operation
    - During diagnostics
    
    Returns:
        int: Number of summaries computed
    """
    db = get_database()
    guild_id_str = str(guild_id)
    
    # Find all XP documents for this guild
    from abby_core.database.collections.xp import get_collection as get_xp_col
    xp_collection = get_xp_col()
    user_xp_docs = list(xp_collection.find({"guild_id": guild_id_str}))
    
    count = 0
    for user_xp_doc in user_xp_docs:
        user_id = user_xp_doc.get("user_id")
        
        try:
            summary = compute_user_summary(int(user_id), guild_id, force_rebuild=True)
            if summary:
                count += 1
        except Exception as e:
            logger.warning(f"[⚠️] Failed to compute summary for user {user_id}: {e}")
            continue
    
    logger.info(f"[📊] Rebuilt {count} user summaries for guild {guild_id}")
    return count


def compute_system_summaries() -> int:
    """Rebuild all user summaries across all guilds.
    
    WARNING: This is very expensive. Use for diagnostics only.
    
    Returns:
        int: Number of summaries computed
    """
    db = get_database()
    xp_collection = db["user_xp"]
    
    user_xp_docs = list(xp_collection.find({}))
    count = 0
    
    for user_xp_doc in user_xp_docs:
        user_id = int(user_xp_doc.get("user_id"))
        guild_id = int(user_xp_doc.get("guild_id")) if user_xp_doc.get("guild_id") else None
        
        if not guild_id:
            continue
        
        try:
            summary = compute_user_summary(user_id, guild_id, force_rebuild=True)
            if summary:
                count += 1
        except Exception as e:
            logger.warning(f"[⚠️] Failed to compute summary: {e}")
            continue
    
    logger.info(f"[📊] Rebuilt {count} user summaries system-wide")
    return count


# ==================== SUMMARY QUERIES ====================

def get_top_users_by_xp(guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get top users in a guild by XP."""
    summary_collection = get_user_summary_collection()
    guild_id_str = str(guild_id)
    
    summaries = list(
        summary_collection.find({"guild_id": guild_id_str})
        .sort("xp", -1)
        .limit(limit)
    )
    
    return summaries


def get_top_users_by_level(guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get top users in a guild by level."""
    summary_collection = get_user_summary_collection()
    guild_id_str = str(guild_id)
    
    summaries = list(
        summary_collection.find({"guild_id": guild_id_str})
        .sort([("level", -1), ("xp", -1)])
        .limit(limit)
    )
    
    return summaries


def get_users_by_level_range(
    guild_id: int,
    min_level: int,
    max_level: int,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Get users in a level range."""
    summary_collection = get_user_summary_collection()
    guild_id_str = str(guild_id)
    
    summaries = list(
        summary_collection.find({
            "guild_id": guild_id_str,
            "level": {"$gte": min_level, "$lte": max_level},
        })
        .limit(limit)
    )
    
    return summaries


# ==================== SUMMARY VALIDATION ====================

def validate_summary(user_id: int, guild_id: int) -> Dict[str, Any]:
    """Validate that summary matches source of truth.
    
    Returns:
        dict: {is_valid, cached, source, mismatches: [...]}
    """
    user_id_str = str(user_id)
    guild_id_str = str(guild_id)
    
    summary_collection = get_user_summary_collection()
    cached_summary = summary_collection.find_one({
        "user_id": user_id_str,
        "guild_id": guild_id_str,
    })
    
    source_summary = compute_user_summary(user_id, guild_id, force_rebuild=True)
    
    if not source_summary:
        return {
            "is_valid": True,  # No source means no user; cache should also be empty
            "cached": cached_summary is not None,
            "source": None,
            "mismatches": [],
        }
    
    mismatches = []
    
    if not cached_summary:
        mismatches.append("Cache missing")
    else:
        # Check key fields
        for field in ["level", "xp", "current_season_id"]:
            if cached_summary.get(field) != source_summary.get(field):
                mismatches.append(f"{field}: cached={cached_summary.get(field)}, source={source_summary.get(field)}")
    
    return {
        "is_valid": len(mismatches) == 0,
        "cached": cached_summary is not None,
        "source": source_summary,
        "mismatches": mismatches,
    }


# ==================== CACHE INVALIDATION ====================

def invalidate_user_summary(user_id: int, guild_id: int) -> bool:
    """Invalidate (delete) cached summary for a user.
    
    Use this after mutations to ensure next read rebuilds from source.
    """
    user_id_str = str(user_id)
    guild_id_str = str(guild_id)
    
    summary_collection = get_user_summary_collection()
    
    try:
        result = summary_collection.delete_one({
            "user_id": user_id_str,
            "guild_id": guild_id_str,
        })
        
        if result.deleted_count > 0:
            logger.debug(f"[🗑️] Invalidated summary for user {user_id} in guild {guild_id}")
            return True
        
        return False
    
    except Exception as e:
        logger.error(f"[❌] Failed to invalidate summary: {e}")
        return False


def invalidate_guild_summaries(guild_id: int) -> int:
    """Invalidate all summaries in a guild."""
    guild_id_str = str(guild_id)
    
    summary_collection = get_user_summary_collection()
    
    try:
        result = summary_collection.delete_many({"guild_id": guild_id_str})
        logger.info(f"[🗑️] Invalidated {result.deleted_count} summaries for guild {guild_id}")
        return result.deleted_count
    
    except Exception as e:
        logger.error(f"[❌] Failed to invalidate guild summaries: {e}")
        return 0

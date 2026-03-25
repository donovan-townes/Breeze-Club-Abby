"""
System Changelog Collection Module

Purpose: Track all system changes and updates
Schema: See schemas.py (SystemChangelogSchema)
Indexes: change_id, created_at, change_type, guild_id

Manages:
- System version history
- Update changelog
- Feature releases
- Bug fixes tracking
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Change types."""
    FEATURE = "feature"
    BUGFIX = "bugfix"
    IMPROVEMENT = "improvement"
    SECURITY = "security"
    DEPRECATED = "deprecated"


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get system_changelog collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["system_changelog"]


def ensure_indexes():
    """Create indexes for system_changelog collection."""
    try:
        collection = get_collection()

        def _ensure_unique_partial_index(name: str, key: list[tuple[str, int]], filter_expr: Dict[str, Any]) -> None:
            existing = next((idx for idx in collection.list_indexes() if idx.get("name") == name), None)
            if existing:
                existing_key = dict(existing.get("key", {}))
                if existing_key == dict(key):
                    if existing.get("partialFilterExpression") != filter_expr:
                        collection.drop_index(name)
            collection.create_index(
                key,
                unique=True,
                partialFilterExpression=filter_expr,
                name=name,
            )

        _ensure_unique_partial_index(
            "change_id_1",
            [("change_id", 1)],
            {"change_id": {"$type": "string"}},
        )
        collection.create_index([("created_at", -1)])
        collection.create_index([("change_type", 1)])
        collection.create_index([("guild_id", 1)])
        collection.create_index([("version", 1)])

        logger.debug("[system_changelog] Indexes created")

    except Exception as e:
        logger.warning(f"[system_changelog] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default changelog entries."""
    try:
        collection = get_collection()
        
        # Check if already seeded
        existing = collection.count_documents({})
        if existing > 0:
            logger.debug("[system_changelog] Changelog already initialized")
            return True
        
        # Create initial entry
        initial = {
            "change_id": "system_init_v1",
            "version": "1.0.0",
            "change_type": ChangeType.FEATURE,
            "title": "System Initialized",
            "description": "Initial system setup and database initialization",
            "guild_id": None,
            "author": "system",
            "metadata": {},
            "created_at": datetime.utcnow(),
        }
        
        collection.insert_one(initial)
        logger.debug("[system_changelog] Initial entry created")
        return True
        
    except Exception as e:
        logger.error(f"[system_changelog] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize system_changelog collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[system_changelog] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[system_changelog] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def create_change(
    change_id: str,
    version: str,
    change_type: str,
    title: str,
    description: str,
    author: str = "system",
    guild_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Create a new changelog entry."""
    try:
        collection = get_collection()
        
        change = {
            "change_id": change_id,
            "version": version,
            "change_type": change_type,
            "title": title,
            "description": description,
            "author": author,
            "guild_id": guild_id,
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
        }
        
        collection.insert_one(change)
        logger.debug(f"[system_changelog] Created changelog entry {change_id}")
        return True
        
    except Exception as e:
        logger.error(f"[system_changelog] Error creating entry: {e}")
        return False


def get_change(change_id: str) -> Optional[Dict[str, Any]]:
    """Get changelog entry by ID."""
    try:
        collection = get_collection()
        return collection.find_one({"change_id": change_id})
    except Exception as e:
        logger.error(f"[system_changelog] Error getting change: {e}")
        return None


def get_recent_changes(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent changelog entries."""
    try:
        collection = get_collection()
        return list(collection.find()
                   .sort("created_at", -1)
                   .limit(limit))
    except Exception as e:
        logger.error(f"[system_changelog] Error getting recent changes: {e}")
        return []


def get_changes_by_type(change_type: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get changelog entries by type."""
    try:
        collection = get_collection()
        return list(collection.find({"change_type": change_type})
                   .sort("created_at", -1)
                   .limit(limit))
    except Exception as e:
        logger.error(f"[system_changelog] Error getting changes by type: {e}")
        return []


def get_version_changes(version: str) -> List[Dict[str, Any]]:
    """Get all changes for a specific version."""
    try:
        collection = get_collection()
        return list(collection.find({"version": version})
                   .sort("created_at", 1))
    except Exception as e:
        logger.error(f"[system_changelog] Error getting version changes: {e}")
        return []


def get_guild_changes(guild_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Get changes affecting a specific guild."""
    try:
        collection = get_collection()
        return list(collection.find({
            "$or": [
                {"guild_id": guild_id},
                {"guild_id": None}  # Global changes
            ]
        }).sort("created_at", -1).limit(limit))
    except Exception as e:
        logger.error(f"[system_changelog] Error getting guild changes: {e}")
        return []


def search_changes(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search changelog by title or description."""
    try:
        collection = get_collection()
        return list(collection.find({
            "$or": [
                {"title": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}}
            ]
        }).sort("created_at", -1).limit(limit))
    except Exception as e:
        logger.error(f"[system_changelog] Error searching changes: {e}")
        return []


def delete_old_entries(days_old: int = 90) -> int:
    """Delete changelog entries older than specified days."""
    try:
        collection = get_collection()
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        result = collection.delete_many({
            "created_at": {"$lt": cutoff_date}
        })
        
        logger.debug(f"[system_changelog] Deleted {result.deleted_count} old entries")
        return result.deleted_count
        
    except Exception as e:
        logger.error(f"[system_changelog] Error deleting old entries: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class SystemChangelog(CollectionModule):
    """Collection module for system_changelog - follows foolproof pattern."""
    
    collection_name = "system_changelog"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get system_changelog collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not SystemChangelog.collection_name:
            raise RuntimeError("collection_name not set for SystemChangelog")
        db = get_database()
        return db[SystemChangelog.collection_name]
    
    @staticmethod
    def ensure_indexes():
        """Create all indexes for efficient querying."""
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        """Seed default data if needed."""
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        """Orchestrate initialization."""
        return initialize_collection()

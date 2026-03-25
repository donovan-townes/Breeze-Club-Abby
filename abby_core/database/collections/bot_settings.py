"""
Bot Settings Collection Module

Purpose: Per-guild bot configuration and feature toggles
Schema: See schemas.py (BotSettingsSchema)
Indexes: guild_id, setting_name, is_enabled

Manages:
- Bot command settings
- Feature toggles
- Rate limits
- Permission overrides
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get bot_settings collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["bot_settings"]


def ensure_indexes():
    """Create indexes for bot_settings collection."""
    try:
        collection = get_collection()

        # Sparse unique index: allows multiple documents with null values
        index_name = "guild_id_1_setting_name_1"
        existing_indexes = collection.index_information()
        existing = existing_indexes.get(index_name)
        if existing:
            is_unique = existing.get("unique") is True
            is_sparse = existing.get("sparse") is True
            if is_unique and not is_sparse:
                collection.drop_index(index_name)
                logger.info("[bot_settings] Dropped legacy non-sparse unique index")

        collection.create_index(
            [("guild_id", 1), ("setting_name", 1)],
            unique=True,
            sparse=True,
            name=index_name,
        )
        collection.create_index([("guild_id", 1)])
        collection.create_index([("setting_name", 1)])
        collection.create_index([("is_enabled", 1)])
        collection.create_index([("updated_at", -1)])

        logger.debug("[bot_settings] Indexes created")

    except Exception as e:
        logger.warning(f"[bot_settings] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default settings if needed."""
    try:
        logger.debug("[bot_settings] No defaults to seed (per-guild)")
        return True
    except Exception as e:
        logger.error(f"[bot_settings] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize bot_settings collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[bot_settings] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[bot_settings] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def set_setting(
    guild_id: int,
    setting_name: str,
    value: Any,
    is_enabled: bool = True,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Set or update a bot setting."""
    try:
        collection = get_collection()
        
        setting = {
            "guild_id": guild_id,
            "setting_name": setting_name,
            "value": value,
            "is_enabled": is_enabled,
            "metadata": metadata or {},
            "updated_at": datetime.utcnow(),
        }
        
        collection.update_one(
            {"guild_id": guild_id, "setting_name": setting_name},
            {"$set": setting},
            upsert=True
        )
        
        logger.debug(f"[bot_settings] Set {setting_name}={value} for guild {guild_id}")
        return True
        
    except Exception as e:
        logger.error(f"[bot_settings] Error setting setting: {e}")
        return False


def get_setting(
    guild_id: int,
    setting_name: str
) -> Optional[Dict[str, Any]]:
    """Get a specific setting."""
    try:
        collection = get_collection()
        return collection.find_one({
            "guild_id": guild_id,
            "setting_name": setting_name
        })
    except Exception as e:
        logger.error(f"[bot_settings] Error getting setting: {e}")
        return None


def get_setting_value(
    guild_id: int,
    setting_name: str,
    default: Any = None
) -> Any:
    """Get setting value directly."""
    try:
        setting = get_setting(guild_id, setting_name)
        return setting.get("value", default) if setting else default
    except Exception as e:
        logger.error(f"[bot_settings] Error getting setting value: {e}")
        return default


def get_guild_settings(guild_id: int) -> List[Dict[str, Any]]:
    """Get all settings for a guild."""
    try:
        collection = get_collection()
        return list(collection.find({"guild_id": guild_id}))
    except Exception as e:
        logger.error(f"[bot_settings] Error getting guild settings: {e}")
        return []


def get_enabled_settings(guild_id: int) -> List[Dict[str, Any]]:
    """Get all enabled settings for a guild."""
    try:
        collection = get_collection()
        return list(collection.find({
            "guild_id": guild_id,
            "is_enabled": True
        }))
    except Exception as e:
        logger.error(f"[bot_settings] Error getting enabled settings: {e}")
        return []


def toggle_setting(guild_id: int, setting_name: str) -> bool:
    """Toggle a setting's enabled status."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"guild_id": guild_id, "setting_name": setting_name},
            {"$bit": {"is_enabled": {"xor": 1}}}  # Toggle boolean
        )
        
        if result.matched_count == 0:
            logger.warning(f"[bot_settings] Setting {setting_name} not found for guild {guild_id}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[bot_settings] Error toggling setting: {e}")
        return False


def delete_setting(guild_id: int, setting_name: str) -> bool:
    """Delete a setting."""
    try:
        collection = get_collection()
        
        result = collection.delete_one({
            "guild_id": guild_id,
            "setting_name": setting_name
        })
        
        if result.deleted_count == 0:
            logger.warning(f"[bot_settings] Setting {setting_name} not found for guild {guild_id}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[bot_settings] Error deleting setting: {e}")
        return False


def delete_guild_settings(guild_id: int) -> bool:
    """Delete all settings for a guild."""
    try:
        collection = get_collection()
        
        result = collection.delete_many({"guild_id": guild_id})
        
        logger.debug(f"[bot_settings] Deleted {result.deleted_count} settings for guild {guild_id}")
        return True
        
    except Exception as e:
        logger.error(f"[bot_settings] Error deleting guild settings: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class BotSettings(CollectionModule):
    """Collection module for bot_settings - follows foolproof pattern."""
    
    collection_name = "bot_settings"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get bot_settings collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not BotSettings.collection_name:
            raise RuntimeError("collection_name not set for BotSettings")
        db = get_database()
        return db[BotSettings.collection_name]
    
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

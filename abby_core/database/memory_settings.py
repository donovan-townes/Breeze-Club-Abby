"""
Memory Settings Management for Guild Configuration

Provides database operations for guild-specific memory, conversation, and assistant settings.
Settings are stored in a dedicated `memory_settings` collection with per-guild documents.

Usage:
    from abby_core.database.memory_settings import get_memory_settings, set_memory_settings
    
    settings = get_memory_settings(guild_id=123456789)
    settings["enabled"]  # True/False
    
    set_memory_settings(guild_id=123456789, updates={"enabled": False})
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pymongo import ASCENDING

try:
    from abby_core.database.mongodb import connect_to_mongodb
except ImportError:
    connect_to_mongodb = None


# Default settings from config
DEFAULT_SETTINGS = {
    "enabled": True,
    "decay_enabled": True,
    "extraction_enabled": True,
    "conversation_storage_enabled": True,
    "retention_days": 90,
    "confidence_threshold": 0.3,
    "max_conversation_exchanges": 10,
    "summon_mode": "both",  # "mention_only", "slash_only", "both"
    "default_chat_mode": "multi_turn",  # "one_shot", "multi_turn"
    "mod_channel_id": None,
    "announcement_channel_id": None,
}


def _get_memory_settings_collection(db):
    """Get memory_settings collection, creating indexes if needed."""
    collection = db["memory_settings"]
    
    # Ensure indexes exist
    try:
        collection.create_index([("guild_id", ASCENDING)], name="guild_id_index")
    except Exception:
        pass  # Index may already exist
    
    return collection


def get_memory_settings(guild_id: int) -> Dict[str, Any]:
    """
    Get memory settings for a guild.
    
    Args:
        guild_id: Discord guild ID
    
    Returns:
        Dict with all settings, using defaults if document not found
    """
    try:
        from abby_core.database.mongodb import connect_to_mongodb
        client = connect_to_mongodb()
        db = client["Abby_Database"]
    except Exception:
        return DEFAULT_SETTINGS.copy()
    
    try:
        collection = _get_memory_settings_collection(db)
        doc = collection.find_one({"guild_id": str(guild_id)})
        
        if doc:
            # Merge with defaults (new settings may not exist in old docs)
            settings = DEFAULT_SETTINGS.copy()
            settings.update(doc)
            return settings
        else:
            return DEFAULT_SETTINGS.copy()
    except Exception as e:
        print(f"[memory_settings] Failed to get settings for guild {guild_id}: {e}")
        return DEFAULT_SETTINGS.copy()


def set_memory_settings(guild_id: int, updates: Dict[str, Any]) -> bool:
    """
    Update memory settings for a guild.
    
    Args:
        guild_id: Discord guild ID
        updates: Dict of fields to update
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from abby_core.database.mongodb import connect_to_mongodb
        client = connect_to_mongodb()
        db = client["Abby_Database"]
    except Exception:
        return False
    
    try:
        collection = _get_memory_settings_collection(db)
        
        # Add timestamp
        updates["updated_at"] = datetime.utcnow()
        
        # Upsert - create if doesn't exist, update if does
        result = collection.update_one(
            {"guild_id": str(guild_id)},
            {
                "$set": updates,
                "$setOnInsert": {
                    "guild_id": str(guild_id),
                    "created_at": datetime.utcnow(),
                    **DEFAULT_SETTINGS
                }
            },
            upsert=True
        )
        
        return result.modified_count > 0 or result.upserted_id is not None
    except Exception as e:
        print(f"[memory_settings] Failed to set settings for guild {guild_id}: {e}")
        return False


def ensure_guild_settings(guild_id: int) -> Dict[str, Any]:
    """
    Ensure a guild has settings document (create if missing).
    
    Args:
        guild_id: Discord guild ID
    
    Returns:
        Guild settings
    """
    settings = get_memory_settings(guild_id)
    
    # If no custom settings exist, create default document
    if get_memory_settings(guild_id) == DEFAULT_SETTINGS:
        set_memory_settings(guild_id, DEFAULT_SETTINGS.copy())
    
    return settings


def get_guild_setting(guild_id: int, setting_key: str, default=None):
    """
    Get a single setting value for a guild.
    
    Args:
        guild_id: Discord guild ID
        setting_key: Setting key to retrieve
        default: Default value if not found
    
    Returns:
        Setting value or default
    """
    settings = get_memory_settings(guild_id)
    return settings.get(setting_key, default)


def set_guild_setting(guild_id: int, setting_key: str, value: Any) -> bool:
    """
    Set a single setting value for a guild.
    
    Args:
        guild_id: Discord guild ID
        setting_key: Setting key to update
        value: New value
    
    Returns:
        True if successful, False otherwise
    """
    return set_memory_settings(guild_id, {setting_key: value})

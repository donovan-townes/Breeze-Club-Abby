"""
Configuration Utilities - Three-Tier Resolution

Provides runtime helpers to resolve effective configuration
across Operator → Guild → User scopes.
"""

from typing import Dict, Any, Optional
from abby_core.database.collections.guild_configuration import get_guild_config


def get_effective_config(guild_id: int, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Resolve effective configuration with three-tier precedence:
    Operator defaults → Guild config → User overrides
    
    Args:
        guild_id: Discord guild ID
        user_id: Optional user ID for user-level overrides
    
    Returns:
        Merged configuration dict
    """
    # Layer 1: Guild settings (with defaults)
    config = get_memory_settings(guild_id)
    
    # Layer 2: Operator overrides (if exist)
    try:
        from abby_core.database.mongodb import get_database
        db = get_database()
        operator_collection = db["operator_features"]
        operator_doc = operator_collection.find_one({"guild_id": str(guild_id)})
        
        if operator_doc:
            # Operator can force-disable features
            if operator_doc.get("force_memory_off"):
                config["enabled"] = False
            if operator_doc.get("rag_enabled"):
                config["rag_enabled"] = True
            if operator_doc.get("experimental_memory"):
                config["experimental_memory"] = True
    except Exception:
        pass
    
    # Layer 3: User privacy overrides (if user_id provided)
    if user_id:
        try:
            from abby_core.database.mongodb import get_database
            db = get_database()
            privacy_collection = db["user_privacy_settings"]
            user_doc = privacy_collection.find_one({
                "user_id": user_id,
                "guild_id": str(guild_id)
            })
            
            if user_doc:
                # User can opt-out of memory/personalization
                if user_doc.get("memory_opt_out"):
                    config["user_memory_enabled"] = False
                else:
                    config["user_memory_enabled"] = config.get("enabled", True)
                
                if user_doc.get("personalization_opt_out"):
                    config["user_personalization_enabled"] = False
                else:
                    config["user_personalization_enabled"] = True
        except Exception:
            pass
    
    return config


def should_use_memory(guild_id: int, user_id: str) -> bool:
    """
    Check if memory should be used for this user in this guild.
    
    Respects:
    - Guild-level memory toggle
    - Operator force-disable
    - User opt-out
    
    Args:
        guild_id: Discord guild ID
        user_id: Discord user ID
    
    Returns:
        True if memory should be used, False otherwise
    """
    config = get_effective_config(guild_id, user_id)
    
    # Guild disabled (v2.0 path: features.memory.enabled is the master switch)
    if not config.get("features", {}).get("memory", {}).get("enabled", True):
        return False
    
    # User opted out
    if not config.get("user_memory_enabled", True):
        return False
    
    return True


def is_rag_enabled(guild_id: int) -> bool:
    """
    Check if RAG is enabled for this guild (operator-level feature).
    
    Args:
        guild_id: Discord guild ID
    
    Returns:
        True if RAG enabled, False otherwise
    """
    try:
        from abby_core.database.mongodb import get_database
        db = get_database()
        operator_collection = db["operator_features"]
        operator_doc = operator_collection.find_one({"guild_id": str(guild_id)})
        
        return operator_doc.get("rag_enabled", False) if operator_doc else False
    except Exception:
        return False


def get_channel_config(guild_id: int, channel_key: str) -> Optional[int]:
    """
    Get configured channel ID for a specific purpose.
    
    Args:
        guild_id: Discord guild ID
        channel_key: Channel key (e.g., "mod_channel_id", "random_messages_channel_id")
    
    Returns:
        Channel ID if configured, None otherwise
    """
    settings = get_memory_settings(guild_id)
    
    # Support v1.0 field names for backward compatibility, but read from v2.0 paths
    # Map v1.0 channel names to v2.0 paths
    channel_map = {
        "mod_channel_id": ["channels", "moderation", "id"],
        "announcement_channel_id": ["channels", "announcements", "id"],
        "random_messages_channel_id": ["channels", "random_messages", "id"],
        "motd_channel_id": ["channels", "motd", "id"],
        "welcome_channel_id": ["channels", "welcome", "id"],
        "mod_role_id": ["roles", "moderators", "id"],
    }
    
    if channel_key in channel_map:
        path = channel_map[channel_key]
        value = settings.get(path[0], {})
        for key in path[1:]:
            value = value.get(key) if isinstance(value, dict) else None
        return value
    
    # Fallback for unknown keys
    return settings.get(channel_key)

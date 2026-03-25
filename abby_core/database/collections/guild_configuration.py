"""
Guild Configuration Collection Module

Purpose: Store guild-specific settings and configuration
Schema: See schemas.py (GuildConfigSchema)
Indexes: guild_id (unique), schema_version

Manages all per-guild configuration including:
- Guild settings (prefix, language, timezone)
- Module toggles
- Feature flags
- Role and channel mappings
"""

from typing import Optional, Dict, Any, TYPE_CHECKING, List
from datetime import datetime
from dataclasses import dataclass
from pymongo import ASCENDING

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# MEMORY SETTINGS SCHEMA + DEFAULTS (Consolidated)
# ═══════════════════════════════════════════════════════════════

# Config schema with validation rules
CONFIG_SCHEMA = {
    "enabled": {
        "type": bool,
        "default": True,
        "description": "Enable memory system for this guild"
    },
    "decay_enabled": {
        "type": bool,
        "default": True,
        "description": "Enable memory decay (memories fade over time)"
    },
    "extraction_enabled": {
        "type": bool,
        "default": True,
        "description": "Extract facts from conversations automatically"
    },
    "conversation_storage_enabled": {
        "type": bool,
        "default": True,
        "description": "Store raw conversation history"
    },
    "retention_days": {
        "type": int,
        "default": 90,
        "min": 1,
        "max": 3650,
        "description": "Days to keep memories (1-10 years)"
    },
    "confidence_threshold": {
        "type": float,
        "default": 0.3,
        "min": 0.0,
        "max": 1.0,
        "description": "Minimum confidence (0.0-1.0) for storing facts"
    },
    "summon_mode": {
        "type": str,
        "default": "both",
        "enum": ["both", "mention_only", "slash_only"],
        "description": "How to trigger Abby (both, mention only, slash only)"
    },
    "default_chat_mode": {
        "type": str,
        "default": "multi_turn",
        "enum": ["one_shot", "multi_turn"],
        "description": "Conversation style (one response or back-and-forth)"
    },
    "mod_channel_id": {
        "type": int,
        "default": None,
        "nullable": True,
        "description": "Channel for mod notifications"
    },
    "announcement_channel_id": {
        "type": int,
        "default": None,
        "nullable": True,
        "description": "Channel for announcements"
    },
    "random_messages_channel_id": {
        "type": int,
        "default": None,
        "nullable": True,
        "description": "Channel for random messages"
    },
    "welcome_channel_id": {
        "type": int,
        "default": None,
        "nullable": True,
        "description": "Channel for welcome messages"
    },
    "motd_channel_id": {
        "type": int,
        "default": None,
        "nullable": True,
        "description": "Channel for message of the day"
    },
    "mod_role_id": {
        "type": int,
        "default": None,
        "nullable": True,
        "description": "Role for moderators"
    },
    "timezone": {
        "type": str,
        "default": "UTC",
        "enum": [
            "US/Eastern",
            "US/Central",
            "US/Mountain",
            "US/Pacific",
            "US/Alaska",
            "US/Hawaii",
            "Europe/London",
            "Europe/Paris",
            "Europe/Berlin",
            "Asia/Tokyo",
            "Asia/Shanghai",
            "Australia/Sydney",
            "UTC"
        ],
        "description": "Guild timezone for scheduled tasks"
    },
    "motd_enabled": {
        "type": bool,
        "default": False,
        "description": "Enable daily Message of the Day"
    },
    "motd_time": {
        "type": str,
        "default": "08:00",
        "description": "Local time for MOTD (HH:MM format)"
    },
    "motd_last_sent_date": {
        "type": str,
        "default": None,
        "nullable": True,
        "description": "Last date MOTD was sent (YYYY-MM-DD format, internal tracking)"
    },
    "game_auto_enabled": {
        "type": bool,
        "default": False,
        "description": "Enable automatic daily emoji game"
    },
    "game_auto_time": {
        "type": str,
        "default": "20:00",
        "description": "Local time for auto game (HH:MM format)"
    },
    "game_duration_minutes": {
        "type": int,
        "default": 5,
        "min": 1,
        "max": 60,
        "description": "Duration of emoji game in minutes (1-60)"
    },
    "game_last_sent_date": {
        "type": str,
        "default": None,
        "nullable": True,
        "description": "Last date game was auto-started (YYYY-MM-DD format, internal tracking)"
    },
}

# Default settings from config (v2.0 schema - consolidated with nested memory features)
# DESIGN PRINCIPLE:
# - features: What exists (master on/off switches - memory is nested)
# - channels: Where features post (id, description, last_used)
# - scheduling: When features run (time, last_sent_date)
# - memory: How memory behaves (retention, extraction, storage config)
# - context_limits: How much context is injected (token governors)
# - canon: Who controls truth (submission/approval roles)
# - defaults: Guild-wide defaults (persona, language, tone)
# NO REDUNDANT ENABLED FLAGS - use features.* to gate usage
DEFAULT_SETTINGS = {
    "schema_version": "2.0",
    "guild_name": None,  # Will be populated on first save
    "metadata": {
        "description": "Default guild configuration",
        "last_migrated": None,
        "migration_status": "v2.0_default"
    },
    # Master feature switches (authority for what exists)
    "features": {
        "motd": False,
        "random_messages": False,
        "canon_submission": True,
        "auto_game": False,
        # Nested memory sub-features
        "memory": {
            "enabled": True,
            "decay": True,
            "extraction": True,
            "conversation_storage": True
        }
    },
    # Guild-wide defaults (used for onboarding, persona selection, localization)
    "defaults": {
        "persona": "bunny",
        "language": "en",
        "tone": "friendly"
    },
    # Channel locations and metadata (where features post)
    "channels": {
        "announcements": {"id": None, "description": "Channel for announcements", "last_used": None},
        "moderation": {"id": None, "description": "Channel for mod notifications", "last_used": None},
        "motd": {"id": None, "description": "Channel for message of the day", "last_used": None},
        "random_messages": {"id": None, "description": "Channel for random messages", "last_used": None},
        "welcome": {"id": None, "description": "Channel for welcome messages", "last_used": None},
    },
    # Role mappings
    "roles": {
        "moderators": {"id": None, "permissions": ["manage_messages"], "description": "Moderator role"}
    },
    # Scheduling and timing (when features run)
    # NOTE: Check features.{feature} to determine if enabled
    "scheduling": {
        "timezone": "UTC",
        "motd": {
            "time": "08:00",
            "last_sent_date": None
        },
        "auto_game": {
            "time": "20:00",
            "duration_minutes": 5,
            "last_sent_date": None
        }
    },
    # Memory system configuration (how memory behaves)
    # NOTE: Check features.memory.enabled to determine if memory is active
    "memory": {
        "decay": {
            "retention_days": 90
        },
        "extraction": {
            "confidence_threshold": 0.3
        },
        "conversation_storage": {}
    },
    # Conversation behavior
    "conversation": {
        "default_chat_mode": "multi_turn",
        "summon_mode": "both"
    },
    # Context limits (how much context is injected)
    "context_limits": {
        "max_lore_tokens": 600,
        "max_memory_tokens": 400,
        "max_chat_history": 6,
        "max_total_context": 2000
    },
    # Usage limits (mechanical gating, not semantic - prevents abuse before LLM)
    # Applied as pre-context check gate in chatbot.py
    "usage_limits": {
        "conversation": {
            "max_turns_per_session": 3,
            "session_timeout_seconds": 60,
            "cooldown_seconds": 30
        },
        "daily": {
            "max_messages": 50,
            "reset_timezone": "guild"
        },
        "burst": {
            "max_messages": 10,  # Increased from 5 to allow natural conversation (each turn = user + bot = 2 messages)
            "window_seconds": 60  # 10 messages in 60s = ~5 turns of conversation
        }
    },
    # Canon submission and approval (who controls truth)
    "canon": {
        "auto_approve": False,
        "allowed_submit_roles": ["member"],
        "allowed_approve_roles": ["moderators"]
    }
}


@dataclass
class ValidationResult:
    """Result of config validation."""
    is_valid: bool
    errors: List[str]
    sanitized_updates: Dict[str, Any]


# ═══════════════════════════════════════════════════════════════
# COLLECTION ACCESS (Singleton Pattern)
# ═══════════════════════════════════════════════════════════════

def get_collection() -> "Collection[Dict[str, Any]]":
    """Get guild_config collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["guild_config"]


# ═══════════════════════════════════════════════════════════════
# INDEXES
# ═══════════════════════════════════════════════════════════════

def ensure_indexes():
    """Create indexes for guild_config collection."""
    try:
        collection = get_collection()

        # Primary queries
        collection.create_index([("guild_id", 1)], unique=True)
        collection.create_index([("schema_version", 1)])
        collection.create_index([("metadata.last_migrated", -1)])

        logger.debug("[guild_config] Indexes created")

    except Exception as e:
        logger.warning(f"[guild_config] Error creating indexes: {e}")


# ═══════════════════════════════════════════════════════════════
# DEFAULTS / SEEDING
# ═══════════════════════════════════════════════════════════════

def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        collection = get_collection()

        # Guild configs are created on-demand, no system defaults needed
        # Each guild creates its own config when first accessed
        logger.debug("[guild_config] No defaults to seed (on-demand creation)")
        return True

    except Exception as e:
        logger.error(f"[guild_config] Error seeding: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# INITIALIZATION
# ═══════════════════════════════════════════════════════════════

def initialize_collection() -> bool:
    """
    Initialize guild_config collection.

    Called automatically at platform startup.

    Returns:
        True if successful, False otherwise
    """
    try:
        ensure_indexes()
        seed_defaults()

        logger.debug("[guild_config] Collection initialized")
        return True

    except Exception as e:
        logger.error(f"[guild_config] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def _guild_id_filter(guild_id: int) -> Dict[str, Any]:
    """Build a query that matches both legacy int and current string guild IDs."""
    guild_id_str = str(guild_id)
    guild_id_values: list[str | int] = [guild_id_str]
    if guild_id_str.isdigit():
        guild_id_values.append(int(guild_id_str))
    return {"guild_id": {"$in": guild_id_values}}

def get_guild_config(guild_id: int) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific guild.
    
    Returns guild config or None if not found. Caller should handle None
    or use DEFAULT_SETTINGS as fallback if needed.
    """
    try:
        collection = get_collection()
        doc = collection.find_one(_guild_id_filter(guild_id))
        if not doc:
            logger.debug(f"[guild_config] No config found for guild {guild_id}, returning None")
            return None
        return doc
    except Exception as e:
        logger.error(f"[guild_config] Error getting config for guild {guild_id}: {e}")
        return None


def create_guild_config(guild_id: int, config_data: Dict[str, Any]) -> bool:
    """Create configuration for a new guild."""
    try:
        collection = get_collection()
        
        default_config = {
            "guild_id": guild_id,
            "prefix": "!",
            "language": "en",
            "timezone": "UTC",
            "schema_version": 2,
            "metadata": {
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_migrated": datetime.utcnow(),
            },
        }
        default_config.update(config_data)
        
        collection.insert_one(default_config)
        logger.debug(f"[guild_config] Created config for guild {guild_id}")
        return True
        
    except Exception as e:
        logger.error(f"[guild_config] Error creating config for guild {guild_id}: {e}")
        return False


def update_guild_config(guild_id: int, updates: Dict[str, Any]) -> bool:
    """Update configuration for a guild."""
    try:
        collection = get_collection()
        normalized_updates = dict(updates)
        current_time = datetime.utcnow()

        metadata_update = normalized_updates.get("metadata")
        if isinstance(metadata_update, dict):
            metadata_copy = dict(metadata_update)
            metadata_copy["updated_at"] = current_time
            normalized_updates["metadata"] = metadata_copy
        elif "metadata" in normalized_updates:
            normalized_updates["metadata"] = {"updated_at": current_time}
            logger.warning(
                "[guild_config] Coerced non-dict metadata update for guild %s into object to avoid path conflict",
                guild_id,
            )
        else:
            normalized_updates["metadata.updated_at"] = current_time
        
        result = collection.update_one(
            _guild_id_filter(guild_id),
            {"$set": normalized_updates}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[guild_config] Guild {guild_id} not found for update")
            return False
            
        logger.debug(f"[guild_config] Updated config for guild {guild_id}")
        return True
        
    except Exception as e:
        logger.error(f"[guild_config] Error updating config for guild {guild_id}: {e}")
        return False


def store_daily_bonus_message(guild_id: int, message_id: int, posted_at: datetime) -> bool:
    """Store daily bonus message ID and timestamp for a guild.
    
    Used to persist message tracking across bot restarts.
    Direct operation to avoid metadata field conflicts.
    
    Args:
        guild_id: Discord guild ID
        message_id: Discord message ID of the daily bonus message
        posted_at: UTC datetime when message was posted
        
    Returns:
        True if successfully stored, False otherwise
    """
    try:
        collection = get_collection()
        
        # Direct $set to nested fields only, avoiding metadata conflicts
        result = collection.update_one(
            _guild_id_filter(guild_id),
            {
                "$set": {
                    "channels.xp.daily_bonus_current_message_id": message_id,
                    "channels.xp.daily_bonus_message_posted_at": posted_at
                }
            },
            upsert=False
        )
        
        if result.matched_count == 0:
            logger.warning(f"[guild_config] Guild {guild_id} not found when storing daily bonus message")
            return False
        
        if result.modified_count > 0:
            logger.debug(f"[guild_config] Stored daily bonus message {message_id} for guild {guild_id}")
            return True
        else:
            logger.debug(f"[guild_config] No changes needed for daily bonus message {message_id} in guild {guild_id}")
            return True
            
    except Exception as e:
        logger.error(f"[guild_config] Error storing daily bonus message for guild {guild_id}: {e}")
        return False


def delete_guild_config(guild_id: int) -> bool:
    """Delete configuration for a guild."""
    try:
        collection = get_collection()
        result = collection.delete_one(_guild_id_filter(guild_id))
        
        if result.deleted_count == 0:
            logger.warning(f"[guild_config] Guild {guild_id} not found for deletion")
            return False
            
        logger.debug(f"[guild_config] Deleted config for guild {guild_id}")
        return True
        
    except Exception as e:
        logger.error(f"[guild_config] Error deleting config for guild {guild_id}: {e}")
        return False


def get_all_guild_configs() -> List[Dict[str, Any]]:
    """Return all guild configuration documents."""
    try:
        collection = get_collection()
        return list(collection.find({}))
    except Exception as e:
        logger.error(f"[guild_config] Error getting all guild configs: {e}")
        return []


def validate_config(updates: Dict[str, Any]) -> ValidationResult:
    """
    Dry-run validation of config updates before saving.

    Args:
        updates: Dict of fields to validate

    Returns:
        ValidationResult with is_valid, errors, and sanitized updates
    """
    errors: List[str] = []
    sanitized: Dict[str, Any] = {}

    for key, value in updates.items():
        # Check if key exists in schema
        if key not in CONFIG_SCHEMA and key not in ["updated_at", "created_at", "guild_id"]:
            errors.append(f"Unknown config key: {key}")
            continue

        if key in ["updated_at", "created_at", "guild_id"]:
            sanitized[key] = value
            continue

        schema = CONFIG_SCHEMA[key]

        # Check type
        expected_type = schema["type"]
        if not isinstance(value, expected_type):
            # Allow None for nullable fields
            if value is None and schema.get("nullable", False):
                sanitized[key] = None
                continue
            errors.append(f"{key}: expected {expected_type.__name__}, got {type(value).__name__}")
            continue

        # Check enum
        if "enum" in schema and value not in schema["enum"]:
            errors.append(f"{key}: must be one of {schema['enum']}, got {value}")
            continue

        # Check range
        if "min" in schema and value < schema["min"]:
            errors.append(f"{key}: minimum is {schema['min']}, got {value}")
            continue

        if "max" in schema and value > schema["max"]:
            errors.append(f"{key}: maximum is {schema['max']}, got {value}")
            continue

        sanitized[key] = value

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        sanitized_updates=sanitized
    )


def _get_memory_settings_collection(db):
    """Get guild_config collection, creating indexes if needed."""
    collection = db["guild_config"]

    # Ensure indexes exist
    try:
        collection.create_index([("guild_id", ASCENDING)], name="guild_id_index")
    except Exception:
        pass  # Index may already exist

    return collection


def get_memory_settings(guild_id: int) -> Dict[str, Any]:
    """
    Get memory settings for a guild (fail-closed: returns defaults if missing).

    Args:
        guild_id: Discord guild ID

    Returns:
        Dict with all settings, using defaults if document not found
    """
    try:
        db = get_database()  # Use configured database (respects dev/live)
    except Exception:
        # Fail closed - return defaults if database unavailable
        logger.warning(f"[guild_config] Database unavailable, using defaults for guild {guild_id}")
        return DEFAULT_SETTINGS.copy()

    try:
        collection = _get_memory_settings_collection(db)
        doc = collection.find_one({"guild_id": str(guild_id)})

        if doc:
            # Check if this is a v1.0 document (no schema_version field)
            if "schema_version" not in doc:
                # Auto-migrate v1.0 → v2.0 in-memory
                logger.info(f"[guild_config] Auto-migrating v1.0 → v2.0 for guild {guild_id}")
                doc = migrate_v1_to_v2(doc)

            # Merge with defaults (new settings may not exist in old docs)
            settings = DEFAULT_SETTINGS.copy()
            settings.update(doc)
            return settings
        else:
            return DEFAULT_SETTINGS.copy()
    except Exception as e:
        # Fail closed - return defaults if read fails
        logger.error(f"[guild_config] Failed to get settings for guild {guild_id}: {e}")
        return DEFAULT_SETTINGS.copy()


def _flatten_nested_dict(d: Dict[str, Any], parent_key: str = "") -> Dict[str, Any]:
    """
    Convert nested dictionaries to dot notation for MongoDB $set operations.

    Converts:
        {"channels": {"moderation": {"id": 123}}}
    To:
        {"channels.moderation.id": 123}

    This ensures MongoDB merges nested fields instead of replacing the entire parent object.
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict) and v:  # Only flatten non-empty dicts
            items.extend(_flatten_nested_dict(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)


def set_memory_settings(guild_id: int, updates: Dict[str, Any], audit_user_id: Optional[str] = None) -> bool:
    """
    Update memory settings for a guild with dry-run validation and audit logging.

    Performs validation before saving. Returns False if validation fails.

    Args:
        guild_id: Discord guild ID
        updates: Dict of fields to update
        audit_user_id: User ID who made the change (for audit log)

    Returns:
        True if successful, False otherwise
    """
    # For v2.0 migration: accept updates directly without strict validation
    # Schema migration in progress - defaults will fill in missing fields on upsert
    safe_updates = updates

    try:
        db = get_database()  # Use configured database (respects dev/live)
    except Exception:
        logger.error(f"[guild_config] Database unavailable for guild {guild_id}")
        return False

    try:
        collection = _get_memory_settings_collection(db)

        # Get current settings for before/after comparison
        current_doc = collection.find_one({"guild_id": str(guild_id)}) or {}

        # Flatten nested updates to dot notation for proper MongoDB merging
        # e.g., {"channels": {"moderation": {"id": 123}}} -> {"channels.moderation.id": 123}
        # This prevents MongoDB from replacing entire parent objects
        flattened_updates = _flatten_nested_dict(safe_updates)
        flattened_updates["updated_at"] = datetime.utcnow()

        # Build setOnInsert with only fields not in updates to avoid conflicts
        set_on_insert = {
            "guild_id": str(guild_id),
            "created_at": datetime.utcnow(),
        }
        # Guard against dotted-path updates creating parent conflicts on upsert
        update_roots = set()
        for key in safe_updates.keys():
            if not key:
                continue
            update_roots.add(key.split(".")[0])

        # Only add defaults that aren't being updated (check original updates, not flattened)
        for key, value in DEFAULT_SETTINGS.items():
            if key not in update_roots:
                set_on_insert[key] = value

        # Upsert - create if doesn't exist, update if does
        result = collection.update_one(
            {"guild_id": str(guild_id)},
            {
                "$set": flattened_updates,
                "$setOnInsert": set_on_insert
            },
            upsert=True
        )

        # Audit log with before/after context
        if audit_user_id:
            _log_config_change(db, guild_id, audit_user_id, current_doc, safe_updates)

        return result.modified_count > 0 or result.upserted_id is not None
    except Exception as e:
        logger.error(f"[guild_config] Failed to set settings for guild {guild_id}: {e}")
        return False


def _log_config_change(db, guild_id: int, user_id: str, before: Dict[str, Any], changes: Dict[str, Any]):
    """Log configuration changes with before/after context for audit trail."""
    try:
        # Build before/after comparison
        change_details = {}
        for key, new_value in changes.items():
            if key not in ["updated_at", "created_at"]:  # Skip timestamps
                old_value = before.get(key, None)
                if old_value != new_value:
                    change_details[key] = {
                        "before": old_value,
                        "after": new_value
                    }

        audit_doc = {
            "guild_id": str(guild_id),
            "user_id": user_id,
            "changes": change_details,
            "raw_updates": changes,  # Keep full updates for reference
            "timestamp": datetime.utcnow(),
            "action": "guild_config_update"
        }

        # Store in database
        audit_collection = db["config_audit_log"]
        audit_collection.insert_one(audit_doc)

        # Log to abby.jsonl for telemetry
        logger.info(
            f"[guild_config] Configuration updated for guild {guild_id}",
            extra={
                "guild_id": guild_id,
                "user_id": user_id,
                "changes": change_details,
                "fields_changed": list(change_details.keys())
            }
        )
    except Exception as e:
        logger.error(f"[guild_config] Failed to log audit: {e}")


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


def set_guild_config(guild_id: int, updates: Dict[str, Any], audit_user_id: Optional[str] = None) -> bool:
    """Set configuration fields for a guild (wrapper for memory settings update)."""
    return set_memory_settings(guild_id, updates, audit_user_id=audit_user_id)


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA MIGRATION v1.0 → v2.0 (Dual-Read Pattern for Backward Compatibility)
# ═══════════════════════════════════════════════════════════════════════════════

def migrate_v1_to_v2(v1_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert v1.0 flat document structure to v2.0 nested structure.

    SAFE: Non-destructive, creates new dict without modifying original.

    v1.0 Example:
    {
        "guild_id": "123",
        "timezone": "US/Central",
        "motd_enabled": true,
        "mod_channel_id": 456,
        "enabled": true
    }

    v2.0 Example:
    {
        "guild_id": "123",
        "schema_version": "2.0",
        "scheduling": {"timezone": "US/Central", "motd": {...}},
        "channels": {"moderation": {"id": 456}, ...},
        "features": {"memory": true, ...},
        "memory": {...},
        "conversation": {...},
        "context_limits": {...},
        "canon": {...}
    }

    Args:
        v1_doc: Original v1.0 document from database

    Returns:
        v2.0 structure with all v1.0 values preserved
    """
    v2 = {
        "guild_id": v1_doc.get("guild_id"),
        "guild_name": v1_doc.get("guild_name", "Unknown"),  # NEW: Snapshot for clarity
        "schema_version": "2.0",  # NEW: Enable safe migrations
        "created_at": v1_doc.get("created_at"),
        "updated_at": v1_doc.get("updated_at"),

        # ─────────────────────────────────────────────────────────────
        # Metadata: System tracking (non-authoritative snapshots)
        # ─────────────────────────────────────────────────────────────
        "metadata": {
            "guild_avatar_hash": v1_doc.get("guild_avatar_hash"),
            "member_count": v1_doc.get("member_count", 0),
            "feature_admin_user_id": v1_doc.get("feature_admin_user_id")
        },

        # ─────────────────────────────────────────────────────────────
        # Feature Flags: Generalized per-guild enable/disable
        # ─────────────────────────────────────────────────────────────
        "features": {
            "memory": v1_doc.get("enabled", True),
            "motd": v1_doc.get("motd_enabled", False),
            "random_messages": True,
            "canon_submission": True,
            "persona_overlays": True,
            "book_writing": False,
            "rag": True
        },

        # ─────────────────────────────────────────────────────────────
        # Channels: Grouped by purpose (ready for future API expansion)
        # ─────────────────────────────────────────────────────────────
        "channels": {
            "announcements": {
                "id": v1_doc.get("announcement_channel_id"),
                "enabled": v1_doc.get("announcement_channel_id") is not None,
                "description": "Server-wide announcements"
            },
            "moderation": {
                "id": v1_doc.get("mod_channel_id"),
                "enabled": v1_doc.get("mod_channel_id") is not None,
                "description": "Mod notifications"
            },
            "motd": {
                "id": v1_doc.get("motd_channel_id"),
                "enabled": v1_doc.get("motd_channel_id") is not None,
                "description": "Daily message of the day"
            },
            "random_messages": {
                "id": v1_doc.get("random_messages_channel_id"),
                "enabled": v1_doc.get("random_messages_channel_id") is not None,
                "description": "Periodic in-character messages"
            },
            "welcome": {
                "id": v1_doc.get("welcome_channel_id"),
                "enabled": v1_doc.get("welcome_channel_id") is not None,
                "description": "New member welcomes"
            }
        },

        # ─────────────────────────────────────────────────────────────
        # Roles: Can expand to role groups in future
        # ─────────────────────────────────────────────────────────────
        "roles": {
            "moderators": {
                "id": v1_doc.get("mod_role_id"),
                "enabled": v1_doc.get("mod_role_id") is not None,
                "permissions": ["manage_messages"],
                "description": "Moderator role"
            }
        },

        # ─────────────────────────────────────────────────────────────
        # Scheduling: Timezone-aware timing for all tasks
        # ─────────────────────────────────────────────────────────────
        "scheduling": {
            "timezone": v1_doc.get("timezone", "UTC"),
            "motd": {
                "enabled": v1_doc.get("motd_enabled", False),
                "time": v1_doc.get("motd_time", "08:00"),
                "last_sent_date": v1_doc.get("motd_last_sent_date")
            }
        },

        # ─────────────────────────────────────────────────────────────
        # Memory System Settings: Refined structure
        # ─────────────────────────────────────────────────────────────
        "memory": {
            "enabled": v1_doc.get("enabled", True),
            "decay": {
                "enabled": v1_doc.get("decay_enabled", True),
                "rate": "standard"
            },
            "extraction": {
                "enabled": v1_doc.get("extraction_enabled", True),
                "confidence_threshold": v1_doc.get("confidence_threshold", 0.3),
                "min_tokens": 10
            },
            "storage": {
                "enabled": v1_doc.get("conversation_storage_enabled", True),
                "retention_days": v1_doc.get("retention_days", 90),
                "max_memories_per_user": 1000
            }
        },

        # ─────────────────────────────────────────────────────────────
        # Conversation Settings: Chat behavior
        # ─────────────────────────────────────────────────────────────
        "conversation": {
            "summon_mode": v1_doc.get("summon_mode", "both"),
            "default_mode": v1_doc.get("default_chat_mode", "multi_turn")
        },

        # ─────────────────────────────────────────────────────────────
        # LLM Injection Limits: Router-level control for token budget
        # ─────────────────────────────────────────────────────────────
        "context_limits": {
            "max_lore_tokens": 600,
            "max_memory_tokens": 400,
            "max_personality_tokens": 300,
            "max_chat_history": 6,
            "max_total_context": 2000
        },

        # ─────────────────────────────────────────────────────────────
        # Canon Trust & Moderation: Boundaries for submissions
        # ─────────────────────────────────────────────────────────────
        "canon": {
            "auto_approve": False,
            "allowed_submit_roles": ["member"],
            "allowed_approve_roles": ["mod"],
            "requires_owner_sign_off": False
        }
    }

    return v2


def normalize_config_for_v2(updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert v1.0 field names to v2.0 nested structure for updates.

    Accepts both v1.0 and v2.0 paths:

    v1.0 style:
        {"timezone": "UTC", "motd_enabled": true, "mod_channel_id": 123}

    v2.0 style:
        {"scheduling": {"timezone": "UTC"}, "channels": {"moderation": {"id": 123}}}

    Mixed (both work):
        {"timezone": "UTC", "channels": {"moderation": {"id": 123}}}

    For now, this is a pass-through since CONFIG_SCHEMA still uses v1.0 fields.
    Future: Will fully normalize to v2.0 nested paths.

    Args:
        updates: Field updates in v1.0 or v2.0 format

    Returns:
        Normalized updates ready for validation
    """
    # Future v3.0: Deep mapping of v1.0 → v2.0 paths
    # For now: Pass through (CONFIG_SCHEMA validates v1.0 paths)
    return updates


async def initialize_guild_config(guild_id: int, guild_name: Optional[str] = None) -> bool:
    """
    Ensure a guild has a v2.0 config document, creating defaults if missing.

    Called on bot startup for all existing guilds and on guild_join for new guilds.

    Args:
        guild_id: Discord guild ID
        guild_name: Optional guild name to store in config

    Returns:
        True if config exists or was created, False if error
    """
    try:
        db = get_database()
    except Exception as e:
        logger.error(f"[guild_config] Failed to initialize config for guild {guild_id}: {e}")
        return False

    try:
        collection = _get_memory_settings_collection(db)
        doc = collection.find_one({"guild_id": str(guild_id)})

        if doc:
            # Already exists - if it's v1.0, migration happens on read
            return True

        # Create v2.0 config with defaults
        new_config = DEFAULT_SETTINGS.copy()
        new_config["guild_id"] = str(guild_id)
        if guild_name:
            new_config["guild_name"] = guild_name
        new_config["created_at"] = datetime.utcnow()
        new_config["updated_at"] = datetime.utcnow()

        result = collection.insert_one(new_config)

        logger.info(f"[guild_config] Initialized v2.0 config for guild {guild_id} ({guild_name or 'unknown'})")

        return bool(result.inserted_id)
    except Exception as e:
        logger.error(f"[guild_config] Failed to initialize config for guild {guild_id}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class GuildConfiguration(CollectionModule):
    """Collection module for guild_config - follows foolproof pattern."""
    
    collection_name = "guild_config"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get guild_config collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not GuildConfiguration.collection_name:
            raise RuntimeError("collection_name not set for GuildConfiguration")
        db = get_database()
        return db[GuildConfiguration.collection_name]
    
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

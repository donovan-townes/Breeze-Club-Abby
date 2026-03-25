"""
System Configuration Management

Operator-level configuration for system-wide jobs and maintenance tasks.
This is separate from guild_config and manages cross-guild operations.

Follows the CollectionModule pattern for foolproof database architecture.
"""

from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


DEFAULT_SYSTEM_CONFIG = {
    "_id": "primary",
    "timezone": "UTC",
    "system_jobs": {
        "announcements": {
            "daily_world_announcements": {
                "enabled": True,
                "schedule": {"type": "daily", "time": "09:00"}
            }
        },
        "maintenance": {
            "memory_decay": {
                "enabled": True,
                "schedule": {"type": "daily", "time": "20:00"},
                "last_executed_at_by_guild": {}
            }
        },
        # Announcements handled via content_delivery system (not via job scheduler)
        # Removed: daily_world_announcements (legacy - no handler)
        "xp_rewards": {
            "daily_bonus": {
                "enabled": True,
                "schedule": {"type": "daily", "time": "08:00"},
                "last_executed_at_by_guild": {}
            },
            "streaming_check": {
                "enabled": True,
                "schedule": {"type": "interval", "every_minutes": 5},
                "last_executed_at": None
            }
        }
    },
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow()
}


class SystemConfiguration(CollectionModule):
    """Collection module for system_config - follows foolproof pattern."""

    collection_name = "system_config"
    _default_doc_id = "primary"

    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get system_config collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not SystemConfiguration.collection_name:
            raise RuntimeError("collection_name not set for SystemConfiguration")
        db = get_database()
        return db[SystemConfiguration.collection_name]

    @staticmethod
    def ensure_indexes():
        """Create indexes for system_config collection."""
        try:
            collection = SystemConfiguration.get_collection()
            # Primary key index already exists by default on _id
            if logger:
                logger.debug("[SystemConfiguration] Indexes verified")
        except Exception as e:
            if logger:
                logger.warning(f"[SystemConfiguration] Error with indexes: {e}")

    @staticmethod
    def seed_defaults() -> bool:
        """Seed default system configuration if not present."""
        try:
            collection = SystemConfiguration.get_collection()

            # Check if already seeded
            existing = collection.find_one({"_id": SystemConfiguration._default_doc_id})
            if existing:
                if logger:
                    logger.debug("[SystemConfiguration] Configuration already exists")
                return True

            # Insert default config
            collection.insert_one(DEFAULT_SYSTEM_CONFIG.copy())

            if logger:
                logger.info("[SystemConfiguration] ✓ Seeded default system configuration")

            return True

        except Exception as e:
            if logger:
                logger.error(f"[SystemConfiguration] Error seeding defaults: {e}")
            return False

    @staticmethod
    def initialize_collection() -> bool:
        """Initialize system_config collection for use."""
        try:
            SystemConfiguration.ensure_indexes()
            SystemConfiguration.seed_defaults()

            if logger:
                logger.debug("[SystemConfiguration] Collection initialized")

            return True

        except Exception as e:
            if logger:
                logger.error(f"[SystemConfiguration] Error initializing collection: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_system_config() -> Dict[str, Any]:
    """Get system configuration. Returns default if not found."""
    if not get_database:
        return DEFAULT_SYSTEM_CONFIG.copy()

    try:
        collection = SystemConfiguration.get_collection()

        config = collection.find_one({"_id": SystemConfiguration._default_doc_id})

        if not config:
            collection.insert_one(DEFAULT_SYSTEM_CONFIG.copy())
            return DEFAULT_SYSTEM_CONFIG.copy()

        return config

    except Exception as e:
        if logger:
            logger.error(f"[SystemConfiguration] Failed to get system config: {e}", exc_info=True)
        return DEFAULT_SYSTEM_CONFIG.copy()


def set_system_config(updates: Dict[str, Any]):
    """Update system configuration."""
    if not get_database:
        if logger:
            logger.warning("[SystemConfiguration] MongoDB not available")
        return

    try:
        collection = SystemConfiguration.get_collection()

        flat_updates = _flatten_dict(updates)
        flat_updates["updated_at"] = datetime.utcnow()

        collection.update_one(
            {"_id": SystemConfiguration._default_doc_id},
            {"$set": flat_updates},
            upsert=True
        )

        if logger:
            logger.info(f"[SystemConfiguration] Updated: {list(flat_updates.keys())}")

    except Exception as e:
        if logger:
            logger.error(f"[SystemConfiguration] Failed to update: {e}", exc_info=True)


def get_system_job_config(job_path: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific system job."""
    config = get_system_config()
    system_jobs = config.get("system_jobs", {})

    parts = job_path.split(".")
    current = system_jobs
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None

    return current if isinstance(current, dict) else None


def update_job_execution(job_path: str, guild_id: Optional[int] = None, timestamp: Optional[str] = None):
    """Update last execution timestamp for a system job."""
    if timestamp is None:
        timestamp = datetime.now().isoformat()

    if guild_id is not None:
        update_path = f"system_jobs.{job_path}.last_executed_at_by_guild.{guild_id}"
    else:
        update_path = f"system_jobs.{job_path}.last_executed_at"

    set_system_config({update_path: timestamp})


def _flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """Flatten nested dict for MongoDB $set operations."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict) and not any(isinstance(vv, dict) for vv in v.values()):
            items.append((new_key, v))
        elif isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


# Auto-register with database initialization registry
try:
    from abby_core.database import register_collection_initializer
    register_collection_initializer(SystemConfiguration.initialize_collection)
except ImportError:
    pass

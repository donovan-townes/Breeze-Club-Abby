"""
Config Audit Log Collection Module

Purpose: Audit trail for guild configuration changes
Schema: Configuration change records with user tracking
Indexes: guild_id, timestamp, user_id

Manages:
- Configuration change history
- User action tracking
- Audit compliance
"""

from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def get_collection() -> "Collection[Dict[str, Any]]":
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    return get_database()["config_audit_log"]


def ensure_indexes():
    try:
        collection = get_collection()
        collection.create_index([("guild_id", 1)])
        collection.create_index([("timestamp", -1)])
        collection.create_index([("user_id", 1)])
        logger.debug("[config_audit_log] Indexes created")
    except Exception as e:
        logger.warning(f"[config_audit_log] Error creating indexes: {e}")


def seed_defaults() -> bool:
    try:
        logger.debug("[config_audit_log] No defaults to seed")
        return True
    except Exception as e:
        logger.error(f"[config_audit_log] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[config_audit_log] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[config_audit_log] Error initializing: {e}")
        return False


class ConfigAuditLog(CollectionModule):
    collection_name = "config_audit_log"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not ConfigAuditLog.collection_name:
            raise RuntimeError("collection_name not set for ConfigAuditLog")
        return get_database()[ConfigAuditLog.collection_name]
    
    @staticmethod
    def ensure_indexes():
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        return initialize_collection()

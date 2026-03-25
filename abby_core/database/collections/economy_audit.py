"""
Economy Audit Collection Module

Purpose: Audit trail for economy transactions and balance changes
Schema: Transaction records with full traceability
Indexes: user_id+guild_id, timestamp, transaction_type

Manages:
- Economy transaction history
- Balance change audit trail
- Compliance and debugging records
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
    db = get_database()
    return db["economy_audit"]


def ensure_indexes():
    try:
        collection = get_collection()
        collection.create_index([("user_id", 1), ("guild_id", 1)])
        collection.create_index([("timestamp", -1)])
        collection.create_index([("transaction_type", 1)])
        logger.debug("[economy_audit] Indexes created")
    except Exception as e:
        logger.warning(f"[economy_audit] Error creating indexes: {e}")


def seed_defaults() -> bool:
    try:
        logger.debug("[economy_audit] No defaults to seed")
        return True
    except Exception as e:
        logger.error(f"[economy_audit] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[economy_audit] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[economy_audit] Error initializing: {e}")
        return False


class EconomyAudit(CollectionModule):
    collection_name = "economy_audit"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not EconomyAudit.collection_name:
            raise RuntimeError("collection_name not set for EconomyAudit")
        db = get_database()
        return db[EconomyAudit.collection_name]
    
    @staticmethod
    def ensure_indexes():
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        return initialize_collection()

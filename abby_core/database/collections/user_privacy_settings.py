"""
User Privacy Settings Collection Module

Purpose: Store user privacy preferences and consent
Schema: Privacy flags, data sharing preferences
Indexes: user_id (unique), setting_type

Manages:
- User privacy preferences
- Consent tracking
- Data sharing opt-outs
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
    return get_database()["user_privacy_settings"]


def ensure_indexes():
    try:
        collection = get_collection()
        collection.create_index([("user_id", 1)], unique=True)
        collection.create_index([("setting_type", 1)])
        logger.debug("[user_privacy_settings] Indexes created")
    except Exception as e:
        logger.warning(f"[user_privacy_settings] Error creating indexes: {e}")


def seed_defaults() -> bool:
    try:
        logger.debug("[user_privacy_settings] No defaults to seed")
        return True
    except Exception as e:
        logger.error(f"[user_privacy_settings] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[user_privacy_settings] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[user_privacy_settings] Error initializing: {e}")
        return False


class UserPrivacySettings(CollectionModule):
    collection_name = "user_privacy_settings"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not UserPrivacySettings.collection_name:
            raise RuntimeError("collection_name not set for UserPrivacySettings")
        return get_database()[UserPrivacySettings.collection_name]
    
    @staticmethod
    def ensure_indexes():
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        return initialize_collection()

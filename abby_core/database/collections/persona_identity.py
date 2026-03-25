"""
Persona Identity Collection Module

Purpose: Canonical persona definitions and identity data
Schema: Persona profiles, traits, versions
Indexes: persona_id (unique), version, created_at

Manages:
- Canonical persona storage
- Persona versioning
- Identity configuration
- Trait management
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
    return get_database()["persona_identity"]


def ensure_indexes():
    try:
        collection = get_collection()
        collection.create_index(
            [("persona_id", 1)],
            unique=True,
            sparse=True,
        )
        collection.create_index([("version", -1)])
        collection.create_index([("created_at", -1)])
        logger.debug("[persona_identity] Indexes created")
    except Exception as e:
        logger.warning(f"[persona_identity] Error creating indexes: {e}")


def seed_defaults() -> bool:
    try:
        logger.debug("[persona_identity] No defaults to seed")
        return True
    except Exception as e:
        logger.error(f"[persona_identity] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[persona_identity] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[persona_identity] Error initializing: {e}")
        return False


class PersonaIdentity(CollectionModule):
    collection_name = "persona_identity"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not PersonaIdentity.collection_name:
            raise RuntimeError("collection_name not set for PersonaIdentity")
        return get_database()[PersonaIdentity.collection_name]
    
    @staticmethod
    def ensure_indexes():
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        return initialize_collection()

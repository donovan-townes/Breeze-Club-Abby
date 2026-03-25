"""
Music Genres Collection Module

Purpose: Music genre data for music generation
Schema: See schemas.py (MusicGenreSchema)
Indexes: genre_id, genre_name, category, is_active

Manages:
- Music genre definitions
- Genre metadata
- Audio characteristics
- Generation parameters
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
    """Get music_genres collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["music_genres"]


def ensure_indexes():
    """Create indexes for music_genres collection."""
    try:
        collection = get_collection()

        collection.create_index([("genre_id", 1)], unique=True)
        collection.create_index([("genre_name", 1)])
        collection.create_index([("category", 1)])
        collection.create_index([("is_active", 1)])
        collection.create_index([("created_at", -1)])

        logger.debug("[music_genres] Indexes created")

    except Exception as e:
        logger.warning(f"[music_genres] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default music genres."""
    try:
        collection = get_collection()
        
        # Check if already seeded
        existing = collection.count_documents({})
        if existing > 0:
            logger.debug("[music_genres] Genres already seeded")
            return True

        genres = [
            {
                "genre_id": "ambient",
                "genre_name": "Ambient",
                "category": "atmospheric",
                "tempo_range": {"min": 60, "max": 100},
                "intensity": "low",
                "is_active": True,
                "metadata": {"description": "Calm, atmospheric soundscapes"},
                "created_at": datetime.utcnow(),
            },
            {
                "genre_id": "lo-fi",
                "genre_name": "Lo-Fi",
                "category": "chillhop",
                "tempo_range": {"min": 80, "max": 110},
                "intensity": "low",
                "is_active": True,
                "metadata": {"description": "Relaxing hip-hop beats"},
                "created_at": datetime.utcnow(),
            },
            {
                "genre_id": "synthwave",
                "genre_name": "Synthwave",
                "category": "electronic",
                "tempo_range": {"min": 100, "max": 130},
                "intensity": "medium",
                "is_active": True,
                "metadata": {"description": "80s-inspired synth music"},
                "created_at": datetime.utcnow(),
            },
        ]
        
        collection.insert_many(genres)
        logger.debug("[music_genres] Default genres seeded")
        return True
        
    except Exception as e:
        logger.error(f"[music_genres] Error seeding defaults: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize music_genres collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[music_genres] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[music_genres] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def create_genre(
    genre_id: str,
    genre_name: str,
    category: str,
    tempo_range: Dict[str, int],
    intensity: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Create new music genre."""
    try:
        collection = get_collection()
        
        genre = {
            "genre_id": genre_id,
            "genre_name": genre_name,
            "category": category,
            "tempo_range": tempo_range,
            "intensity": intensity,
            "is_active": True,
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
        }
        
        collection.insert_one(genre)
        logger.debug(f"[music_genres] Created genre {genre_id}")
        return True
        
    except Exception as e:
        logger.error(f"[music_genres] Error creating genre: {e}")
        return False


def get_genre(genre_id: str) -> Optional[Dict[str, Any]]:
    """Get genre by ID."""
    try:
        collection = get_collection()
        return collection.find_one({"genre_id": genre_id, "is_active": True})
    except Exception as e:
        logger.error(f"[music_genres] Error getting genre: {e}")
        return None


def get_genres_by_category(category: str) -> List[Dict[str, Any]]:
    """Get all genres in category."""
    try:
        collection = get_collection()
        return list(collection.find(
            {"category": category, "is_active": True}
        ))
    except Exception as e:
        logger.error(f"[music_genres] Error getting genres by category: {e}")
        return []


def get_all_active_genres() -> List[Dict[str, Any]]:
    """Get all active genres."""
    try:
        collection = get_collection()
        return list(collection.find({"is_active": True}))
    except Exception as e:
        logger.error(f"[music_genres] Error getting active genres: {e}")
        return []


def get_genre_by_name(genre_name: str) -> Optional[Dict[str, Any]]:
    """Get genre by name."""
    try:
        collection = get_collection()
        return collection.find_one({
            "genre_name": genre_name,
            "is_active": True
        })
    except Exception as e:
        logger.error(f"[music_genres] Error getting genre by name: {e}")
        return None


def update_genre(
    genre_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    tempo_range: Optional[Dict[str, int]] = None,
    intensity: Optional[str] = None
) -> bool:
    """Update genre metadata."""
    try:
        collection = get_collection()
        
        update_dict: Dict[str, Any] = {}
        if metadata is not None:
            update_dict["metadata"] = metadata
        if tempo_range is not None:
            update_dict["tempo_range"] = tempo_range
        if intensity is not None:
            update_dict["intensity"] = intensity
        
        result = collection.update_one(
            {"genre_id": genre_id},
            {"$set": update_dict}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[music_genres] Genre {genre_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[music_genres] Error updating genre: {e}")
        return False


def deactivate_genre(genre_id: str) -> bool:
    """Deactivate genre."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"genre_id": genre_id},
            {"$set": {"is_active": False}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[music_genres] Genre {genre_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[music_genres] Error deactivating genre: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class MusicGenres(CollectionModule):
    """Collection module for music_genres - follows foolproof pattern."""
    
    collection_name = "music_genres"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get music_genres collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not MusicGenres.collection_name:
            raise RuntimeError("collection_name not set for MusicGenres")
        db = get_database()
        return db[MusicGenres.collection_name]
    
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

"""
Collection Module Base Class

Industry-standard abstract base class that enforces the required pattern
for all database collections. Every collection MUST inherit from this and
implement the required methods.

This prevents accidental creation of collections that don't follow our
architecture - it's enforced at import time via __init_subclass__.

Example Usage:
    from abby_core.database.base import CollectionModule
    
    class MyCollectionModule(CollectionModule):
        collection_name = "my_collection"
        
        @staticmethod
        def ensure_indexes():
            collection = MyCollectionModule.get_collection()
            collection.create_index([("user_id", 1)])
        
        @staticmethod
        def seed_defaults() -> bool:
            # Your seeding logic
            return True

Similar Patterns:
    - Django: Model subclasses enforce schema
    - SQLAlchemy: Declarative base enforces ORM pattern
    - FastAPI: APIRouter enforces endpoint pattern
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from pymongo.collection import Collection

logger = logging.getLogger(__name__)


class CollectionModule(ABC):
    """
    Abstract base class for all MongoDB collection modules.
    
    Every collection in Abby MUST inherit from this class and implement
    all required abstract methods. This enforces consistent patterns and
    makes it impossible to accidentally create a collection module that
    doesn't follow the architecture.
    
    Required Implementation:
        1. Set `collection_name` class variable
        2. Implement `get_collection()` - returns MongoDB collection
        3. Implement `ensure_indexes()` - creates all needed indexes
        4. Implement `seed_defaults()` - optional seeding (return True if no-op)
        5. Implement `initialize_collection()` - orchestrates init
    
    Auto-Registration:
        Subclasses automatically register with the database registry
        when imported, via __init_subclass__ hook.
    
    Type Safety:
        Mypy will catch missing methods at type-check time.
        Runtime will catch at import time via __init_subclass__.
    
    Example:
        from abby_core.database.base import CollectionModule
        
        class UserCollection(CollectionModule):
            collection_name = "users"
            
            @staticmethod
            def get_collection():
                from abby_core.database.mongodb import get_database
                db = get_database()
                return db[UserCollection.collection_name]
            
            @staticmethod
            def ensure_indexes():
                collection = UserCollection.get_collection()
                collection.create_index([("user_id", 1)], unique=True)
            
            @staticmethod
            def seed_defaults() -> bool:
                # This collection doesn't seed defaults
                return True
            
            @staticmethod
            def initialize_collection() -> bool:
                UserCollection.ensure_indexes()
                UserCollection.seed_defaults()
                return True
    """
    
    # Required class variable - must be set by subclass
    collection_name: str | None = None
    
    def __init_subclass__(cls, **kwargs):
        """
        Called automatically when a subclass is created.
        
        Validates that the subclass properly implements the pattern.
        Registers the collection with the database registry.
        
        Raises:
            TypeError: If subclass doesn't set collection_name or is missing methods
        """
        super().__init_subclass__(**kwargs)
        
        # Validate collection_name
        if not hasattr(cls, 'collection_name') or cls.collection_name is None:
            raise TypeError(
                f"Collection module {cls.__name__} must define 'collection_name' class variable. "
                f"Example: collection_name = \"my_collection\""
            )
        
        # Validate method implementations
        required_methods = [
            'get_collection',
            'ensure_indexes',
            'seed_defaults',
            'initialize_collection'
        ]
        
        missing_methods = []
        for method_name in required_methods:
            if not hasattr(cls, method_name):
                missing_methods.append(method_name)
            else:
                method = getattr(cls, method_name)
                # Check if it's actually implemented (not inherited from ABC)
                if method == getattr(CollectionModule, method_name, None):
                    missing_methods.append(method_name)
        
        if missing_methods:
            raise TypeError(
                f"Collection module {cls.__name__} is missing required methods: "
                f"{', '.join(missing_methods)}. "
                f"See CollectionModule docstring for example implementation."
            )
        
        # Auto-register with database registry
        try:
            from abby_core.database import register_collection_initializer
            register_collection_initializer(cls.initialize_collection)
            logger.debug(
                f"[CollectionModule] ✓ Registered collection: {cls.collection_name} "
                f"({cls.__module__}.{cls.__name__})"
            )
        except ImportError:
            # Registry not available yet (circular import guard)
            logger.debug(f"[CollectionModule] Registry not available yet, deferring registration")
    
    @staticmethod
    @abstractmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """
        Return MongoDB collection object.
        
        This is the only way to access the collection within the module.
        Enforces singleton pattern - always returns the same collection instance.
        
        Returns:
            pymongo.collection.Collection
        
        Raises:
            RuntimeError: If MongoDB not connected
        """
        pass
    
    @staticmethod
    @abstractmethod
    def ensure_indexes():
        """
        Create all necessary indexes for this collection.
        
        This is idempotent - safe to call multiple times.
        If index already exists, MongoDB silently skips it.
        
        Index Strategy:
            - Primary key / unique constraints first
            - Most common queries second
            - Less common filters last
            - TTL indexes for auto-cleanup
        
        Example:
            collection = MyCollection.get_collection()
            
            # Unique constraint
            collection.create_index([("user_id", 1)], unique=True)
            
            # Compound query index
            collection.create_index([("guild_id", 1), ("status", 1)])
            
            # Sort/range queries
            collection.create_index([("created_at", -1)])
            
            # TTL index for auto-cleanup
            collection.create_index(
                [("created_at", 1)],
                expireAfterSeconds=604800  # 7 days
            )
        """
        pass
    
    @staticmethod
    @abstractmethod
    def seed_defaults() -> bool:
        """
        Seed default/system data if needed.
        
        This is idempotent - check if data exists before seeding.
        
        Returns:
            True if seeding successful or not needed
            False if seeding failed
        
        Example:
            collection = MyCollection.get_collection()
            
            # Check if already seeded
            if collection.count_documents({}) > 0:
                return True
            
            # Insert defaults
            defaults = [
                {"_id": "default_1", "name": "System Default"},
                {"_id": "default_2", "name": "Another Default"}
            ]
            collection.insert_many(defaults)
            return True
        """
        pass
    
    @staticmethod
    @abstractmethod
    def initialize_collection() -> bool:
        """
        Initialize the collection for use.
        
        Called automatically at platform startup.
        Orchestrates index creation and data seeding.
        
        Returns:
            True if initialization successful
            False if initialization failed
        
        Implementation:
            This method is typically simple:
            
            @staticmethod
            def initialize_collection() -> bool:
                try:
                    MyCollection.ensure_indexes()
                    MyCollection.seed_defaults()
                    logger.debug("[MyCollection] Initialized")
                    return True
                except Exception as e:
                    logger.error(f"[MyCollection] Error: {e}")
                    return False
        """
        pass


class CollectionRegistry:
    """
    Registry for all collection modules.
    
    Provides discovery and validation of registered collections.
    """
    
    _collections: Dict[str, type] = {}
    
    @classmethod
    def register(cls, collection_class: type) -> None:
        """Register a collection module class."""
        collection_name = collection_class.collection_name
        
        if collection_name in cls._collections:
            logger.warning(
                f"[CollectionRegistry] Collection '{collection_name}' already registered. "
                f"Old: {cls._collections[collection_name].__name__}, "
                f"New: {collection_class.__name__}"
            )
        
        cls._collections[collection_name] = collection_class
    
    @classmethod
    def get_collection(cls, collection_name: str) -> Optional[type]:
        """Get collection module by name."""
        return cls._collections.get(collection_name)
    
    @classmethod
    def all_collections(cls) -> Dict[str, type]:
        """Get all registered collections."""
        return cls._collections.copy()
    
    @classmethod
    def list_collections(cls) -> list:
        """Get list of all collection names."""
        return list(cls._collections.keys())
    
    @classmethod
    def validate_all(cls) -> bool:
        """Validate all registered collections are healthy."""
        logger.info(f"[CollectionRegistry] Validating {len(cls._collections)} collections...")
        
        for name, collection_class in cls._collections.items():
            try:
                # Try to get collection
                collection = collection_class.get_collection()
                logger.debug(f"[CollectionRegistry] ✓ {name} - accessible")
            except Exception as e:
                logger.error(f"[CollectionRegistry] ✗ {name} - {e}")
                return False
        
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# QUICK START TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════

"""
To create a new collection, follow this template:

from abby_core.database.base import CollectionModule

class MyNewCollection(CollectionModule):
    collection_name = "my_new_collection"
    
    @staticmethod
    def get_collection():
        from abby_core.database.mongodb import get_database
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        db = get_database()
        return db[MyNewCollection.collection_name]
    
    @staticmethod
    def ensure_indexes():
        try:
            collection = MyNewCollection.get_collection()
            collection.create_index([("primary_key", 1)], unique=True)
            collection.create_index([("query_field", 1)])
        except Exception as e:
            logger.warning(f"[MyNewCollection] Index creation failed: {e}")
    
    @staticmethod
    def seed_defaults() -> bool:
        try:
            collection = MyNewCollection.get_collection()
            if collection.count_documents({}) > 0:
                return True  # Already seeded
            
            defaults = [...]
            collection.insert_many(defaults)
            return True
        except Exception as e:
            logger.error(f"[MyNewCollection] Seeding failed: {e}")
            return False
    
    @staticmethod
    def initialize_collection() -> bool:
        try:
            MyNewCollection.ensure_indexes()
            MyNewCollection.seed_defaults()
            return True
        except Exception as e:
            logger.error(f"[MyNewCollection] Initialization failed: {e}")
            return False

# The class will:
# 1. Validate it has all required methods
# 2. Auto-register with the database registry
# 3. Be discovered and initialized at startup
# All automatically!
"""

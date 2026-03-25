"""
Database Module
===============
Centralized database operations and schema management for MongoDB.

Exports:
    - mongodb: Core MongoDB connection and operations
    - schemas: TypedDict schemas for data validation
    - indexes: Database index initialization
    - Collection initialization registry for runtime setup
"""

from typing import Callable, List
from abby_core.database.mongodb import (
    connect_to_mongodb,
    get_database,
    get_profile,
    get_personality,
    update_personality,
    get_genres,
    get_promo_session,
    get_user_tasks,
    add_task,
    delete_task,
    get_economy,
    update_balance,
    get_sessions_collection,
    upsert_user,
    get_rag_documents_collection,
)

# Collection initialization registry
_collection_initializers: List[Callable[[], bool]] = []


def register_collection_initializer(func: Callable[[], bool]) -> None:
    """
    Register a collection initialization function.
    
    Each database module can register its own initialization logic
    by calling this function. All registered initializers will be
    called during platform startup.
    
    Args:
        func: Initialization function that returns True on success
        
    Example:
        # In your database module:
        from abby_core.database import register_collection_initializer
        
        def initialize_my_collection() -> bool:
            # Create indexes, seed defaults, etc.
            return True
            
        register_collection_initializer(initialize_my_collection)
    """
    if func not in _collection_initializers:
        _collection_initializers.append(func)


def initialize_all_collections() -> bool:
    """
    Initialize all registered database collections.
    
    This should be called once during platform startup after MongoDB
    connection is established. It will:
    1. Create any missing collections
    2. Ensure indexes exist
    3. Seed default data if needed
    
    Returns:
        True if all initializations succeeded, False if any failed
    """
    try:
        # Import logger here to avoid circular imports
        from tdos_intelligence.observability import logging
        logger = logging.getLogger(__name__)
        
        if not _collection_initializers:
            logger.debug("[Database] No collection initializers registered")
            return True
        
        logger.info(f"[Database] Initializing {len(_collection_initializers)} collection(s)...")
        
        success_count = 0
        failed_modules = []
        
        for initializer in _collection_initializers:
            module_name = initializer.__module__.split('.')[-1]
            try:
                if initializer():
                    success_count += 1
                else:
                    failed_modules.append(module_name)
                    logger.warning(f"[Database] Initializer for {module_name} returned False")
            except Exception as e:
                failed_modules.append(module_name)
                logger.error(f"[Database] Error initializing {module_name}: {e}")
        
        if failed_modules:
            logger.warning(
                f"[Database] ⚠️ {success_count}/{len(_collection_initializers)} collections initialized "
                f"(failed: {', '.join(failed_modules)})"
            )
            return False
        else:
            logger.info(f"[Database] ✓ All {success_count} collection(s) initialized successfully")
            return True
            
    except Exception as e:
        # Catch-all to prevent startup failure
        try:
            from tdos_intelligence.observability import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[Database] Fatal error in collection initialization: {e}")
        except:
            print(f"[Database] Fatal error in collection initialization: {e}")
        return False


# Auto-register collection initializers from database modules
# This happens at import time, so modules can self-register
def _auto_register_initializers():
    """Auto-discover and register collection initializers."""
    try:
        # Import all collections - each will self-register when imported
        from abby_core.database.collections import (
            GuildConfiguration,
            ChatSessions,
            Economy,
            Users,
            XP,
            Submissions,
            RAGDocuments,
            ContentDelivery,
            SystemState,
            Transactions,
            RandomContentItems,
            SystemConfiguration,
            MusicGenres,
            BotSettings,
            UserTasks,
            SystemChangelog,
            SystemOperations,
            OperationSnapshots,
            GenerationAudit,
        )
        
    except Exception as e:
        # Silently fail - modules might not be available yet
        import traceback
        print(f"[Database] Warning during auto-registration: {e}")
        traceback.print_exc()


# Run auto-registration at import time
_auto_register_initializers()


__all__ = [
    "connect_to_mongodb",
    "get_database",
    "get_profile",
    "get_personality",
    "update_personality",
    "get_genres",
    "get_promo_session",
    "get_user_tasks",
    "add_task",
    "delete_task",
    "get_economy",
    "update_balance",
    "get_sessions_collection",
    "upsert_user",
    "get_rag_documents_collection",
    "register_collection_initializer",
    "initialize_all_collections",
]


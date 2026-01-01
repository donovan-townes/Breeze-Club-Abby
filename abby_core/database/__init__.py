"""
Database Module
===============
Centralized database operations and schema management for MongoDB.

Exports:
    - mongodb: Core MongoDB connection and operations
    - schemas: TypedDict schemas for data validation
    - indexes: Database index initialization
"""

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
    create_session,
    append_session_message,
    close_session,
    upsert_user,
    get_rag_documents_collection,
)

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
    "create_session",
    "append_session_message",
    "close_session",
    "upsert_user",
    "get_rag_documents_collection",
]

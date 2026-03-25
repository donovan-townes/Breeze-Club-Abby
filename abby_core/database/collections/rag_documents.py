"""
RAG Documents Collection Module

Purpose: Retrieval-Augmented Generation document corpus
Schema: See schemas.py (RAGDocumentSchema)
Indexes: embedding_key, created_at, category

Manages:
- Knowledge base documents
- Embedding vectors for semantic search
- Document metadata and categorization
- Source tracking
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
    """Get rag_documents collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["rag_documents"]


def ensure_indexes():
    """Create indexes for rag_documents collection."""
    try:
        collection = get_collection()

        collection.create_index([("embedding_key", 1)])
        collection.create_index([("category", 1)])
        collection.create_index([("created_at", -1)])
        collection.create_index([("updated_at", -1)])
        collection.create_index([("source", 1)])

        logger.debug("[rag_documents] Indexes created")

    except Exception as e:
        logger.warning(f"[rag_documents] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[rag_documents] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[rag_documents] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize rag_documents collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[rag_documents] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[rag_documents] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def create_document(
    embedding_key: str,
    content: str,
    category: str = "general",
    source: str = "manual",
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Create RAG document."""
    try:
        collection = get_collection()
        
        document = {
            "embedding_key": embedding_key,
            "content": content,
            "category": category,
            "source": source,
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        collection.insert_one(document)
        logger.debug(f"[rag_documents] Created document {embedding_key}")
        return True
        
    except Exception as e:
        logger.error(f"[rag_documents] Error creating document: {e}")
        return False


def get_document(embedding_key: str) -> Optional[Dict[str, Any]]:
    """Get document by embedding key."""
    try:
        collection = get_collection()
        return collection.find_one({"embedding_key": embedding_key})
    except Exception as e:
        logger.error(f"[rag_documents] Error getting document: {e}")
        return None


def get_documents_by_category(category: str) -> List[Dict[str, Any]]:
    """Get all documents in category."""
    try:
        collection = get_collection()
        return list(collection.find({"category": category}))
    except Exception as e:
        logger.error(f"[rag_documents] Error getting documents: {e}")
        return []


def update_document(embedding_key: str, updates: Dict[str, Any]) -> bool:
    """Update document content or metadata."""
    try:
        collection = get_collection()
        
        updates["updated_at"] = datetime.utcnow()
        
        result = collection.update_one(
            {"embedding_key": embedding_key},
            {"$set": updates}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[rag_documents] Document {embedding_key} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[rag_documents] Error updating document: {e}")
        return False


def delete_document(embedding_key: str) -> bool:
    """Delete document."""
    try:
        collection = get_collection()
        
        result = collection.delete_one({"embedding_key": embedding_key})
        
        if result.deleted_count == 0:
            logger.warning(f"[rag_documents] Document {embedding_key} not found")
            return False
            
        logger.debug(f"[rag_documents] Deleted document {embedding_key}")
        return True
        
    except Exception as e:
        logger.error(f"[rag_documents] Error deleting document: {e}")
        return False


def count_documents_by_category(category: str) -> int:
    """Count documents in category."""
    try:
        collection = get_collection()
        return collection.count_documents({"category": category})
    except Exception as e:
        logger.error(f"[rag_documents] Error counting documents: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════
# RAG HANDLER HELPERS (for rag/handler.py)
# ═══════════════════════════════════════════════════════════════

def get_document_by_id(document_id: str) -> Optional[Dict[str, Any]]:
    """Get document by canonical document_id (for idempotency checks)."""
    try:
        collection = get_collection()
        return collection.find_one({"document_id": document_id})
    except Exception as e:
        logger.error(f"[rag_documents] Error getting document by ID: {e}")
        return None


def get_max_version_for_document(document_type: str, title: str) -> int:
    """Get highest version number for a document type + title combination."""
    try:
        collection = get_collection()
        base_doc_id_prefix = f"{document_type}::{title.lower().strip()}"
        
        pipeline = [
            {"$match": {"document_id": {"$regex": f"^{base_doc_id_prefix}.*::v"}}},
            {"$group": {"_id": None, "max_version": {"$max": "$version"}}}
        ]
        
        result = list(collection.aggregate(pipeline))
        return result[0]["max_version"] if result else 0
    except Exception as e:
        logger.error(f"[rag_documents] Error getting max version: {e}")
        return 0


def insert_rag_chunks(chunks: List[Dict[str, Any]]) -> bool:
    """Insert multiple RAG document chunks (for ingest function)."""
    try:
        collection = get_collection()
        if chunks:
            collection.insert_many(chunks)
        logger.debug(f"[rag_documents] Inserted {len(chunks)} chunks")
        return True
    except Exception as e:
        logger.error(f"[rag_documents] Error inserting chunks: {e}")
        return False


def list_documents_grouped(
    guild_id: Optional[str] = None,
    document_type: Optional[str] = None,
    scope: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """List documents grouped by document_id with aggregation."""
    try:
        collection = get_collection()
        
        match_query: Dict[str, Any] = {}
        if guild_id:
            match_query["guild_id"] = guild_id
        if document_type:
            match_query["document_type"] = document_type
        if scope:
            match_query["scope"] = scope
        
        pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": "$document_id",
                    "title": {"$first": "$title"},
                    "document_type": {"$first": "$document_type"},
                    "scope": {"$first": "$scope"},
                    "version": {"$first": "$version"},
                    "chunk_count": {"$sum": 1},
                    "tags": {"$first": "$tags"},
                    "created_at": {"$first": "$created_at"},
                }
            },
            {"$sort": {"created_at": -1}},
            {"$limit": limit}
        ]
        
        return list(collection.aggregate(pipeline))
    except Exception as e:
        logger.error(f"[rag_documents] Error listing documents: {e}")
        return []


def get_documents_for_query(
    guild_id: Optional[str] = None,
    document_type: Optional[str] = None,
    scope: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get all documents matching filters (for fallback query processing)."""
    try:
        collection = get_collection()
        
        query: Dict[str, Any] = {}
        if guild_id:
            query["guild_id"] = guild_id
        if document_type:
            query["document_type"] = document_type
        if scope:
            query["scope"] = scope
        
        return list(collection.find(query))
    except Exception as e:
        logger.error(f"[rag_documents] Error getting documents for query: {e}")
        return []


def delete_documents_by_id(document_id: str) -> int:
    """Delete all chunks for a given document_id."""
    try:
        collection = get_collection()
        result = collection.delete_many({"document_id": document_id})
        logger.debug(f"[rag_documents] Deleted {result.deleted_count} chunks for {document_id}")
        return result.deleted_count
    except Exception as e:
        logger.error(f"[rag_documents] Error deleting document chunks: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class RAGDocuments(CollectionModule):
    """Collection module for rag_documents - follows foolproof pattern."""
    
    collection_name = "rag_documents"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get rag_documents collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not RAGDocuments.collection_name:
            raise RuntimeError("collection_name not set for RAGDocuments")
        db = get_database()
        return db[RAGDocuments.collection_name]
    
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

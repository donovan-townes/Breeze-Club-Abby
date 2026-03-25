"""Abby RAG Adapter - Wraps TDOS RAG with guild isolation and economy integration.

This adapter bridges Discord cogs to TDOS RAG by injecting:
- Guild-level document isolation
- Economy-gated features (premium RAG)
- Storage quota management
- Discord-specific formatting
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from tdos_intelligence.rag.handler import get_rag_handler
from tdos_intelligence.rag.schemas import RAGDocument, RAGQueryResult, RAGOperationResult
from tdos_intelligence.rag.interfaces import RAGResult
from abby_core.database.mongodb import get_database

logger = logging.getLogger(__name__)


@dataclass
class RAGContext:
    """Context for RAG operations with Abby-specific data.
    
    Attributes:
        guild_id: Discord guild ID
        user_id: Discord user ID
        is_premium: Whether guild has premium features
        storage_quota: Guild storage quota (bytes)
        storage_used: Current storage usage (bytes)
    """
    guild_id: str
    user_id: str
    is_premium: bool = False
    storage_quota: Optional[int] = None
    storage_used: Optional[int] = None


class RAGAdapter:
    """Abby-specific wrapper around TDOS RAG handler.
    
    Responsibilities:
    - Enforce guild-level document isolation
    - Check storage quotas before ingestion
    - Integrate economy for premium features
    - Format RAG results for Discord
    - Track usage metrics per guild
    """

    def __init__(self):
        """Initialize the RAG adapter."""
        self.rag_handler = get_rag_handler()
        self._db = None  # Lazy initialization
        logger.info("[RAG Adapter] Initialized (database connection deferred)")

    @property
    def db(self):
        """Lazy database connection property."""
        if self._db is None:
            from abby_core.database.mongodb import is_mongodb_available
            if is_mongodb_available():
                self._db = get_database()
                logger.debug("[RAG Adapter] Database connection established")
            else:
                logger.warning("[RAG Adapter] MongoDB unavailable - operations will fail")
                raise ConnectionError("MongoDB is not available")
        return self._db

    async def ingest_document(
        self,
        content: str,
        title: str,
        context: RAGContext,
        document_type: str = "message",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Ingest a document with guild isolation and quota checks.
        
        Args:
            content: Document content
            title: Document title
            context: RAG context with guild/user info
            document_type: Document type (message, note, file, etc.)
            metadata: Additional metadata
        
        Returns:
            Dict containing:
                - success: Whether ingestion succeeded
                - document_id: Generated document ID
                - chunks_created: Number of chunks
                - error: Error message if failed
        """
        # 1. Check storage quota (Abby-specific)
        content_size = len(content.encode('utf-8'))
        if not await self._check_quota(context, content_size):
            return {
                "success": False,
                "error": "Storage quota exceeded. Upgrade to premium for more storage.",
                "quota_remaining": (context.storage_quota - (context.storage_used or 0)) if context.storage_quota else 0
            }
        
        # 2. Build RAG metadata with guild isolation
        meta = metadata or {}
        rag_metadata = {
            "guild_id": context.guild_id,
            "user_id": context.user_id,
            "document_type": document_type,
            "is_premium": context.is_premium,
            "tags": meta.get("tags"),
            "scope": meta.get("scope", "general"),
            "version": meta.get("version", 1),
            **(metadata or {})
        }
        
        # 3. Call TDOS RAG handler (pure intelligence)
        try:
            result = self.rag_handler.ingest(
                text=content,
                document_type=document_type,
                document_title=title,
                guild_id=context.guild_id,
                metadata=rag_metadata,
                user_id=context.user_id
            )
            
            # 5. Update storage quota tracking
            success = result.get("success", False)
            if success:
                await self._update_storage_usage(context, content_size)
            
            # 6. Log metrics to MongoDB
            await self._log_ingestion_metrics(context, result)
            
            return {
                "success": success,
                "document_id": result.get("document_id"),
                "chunks_created": result.get("ingested_chunks", 0),
                "error": result.get("error")
            }
        except Exception as e:
            logger.error("[RAG Adapter] Ingestion failed: %s", e)
            return {
                "success": False,
                "error": f"Ingestion failed: {str(e)}"
            }

    async def query(
        self,
        query: str,
        context: RAGContext,
        top_k: int = 3,
        document_types: Optional[List[str]] = None
    ) -> RAGResult:
        """Query RAG with guild isolation.
        
        Args:
            query: Search query
            context: RAG context with guild/user info
            top_k: Number of results (max 10 for free, unlimited for premium)
            document_types: Optional filter by document types
        
        Returns:
            RAGQueryResult with guild-filtered chunks
        """
        # 1. Enforce result limits based on premium status
        if not context.is_premium and top_k > 10:
            top_k = 10
            logger.warning("[RAG Adapter] Free tier limited to 10 results, requested %d", top_k)
        
        # 2. Build document type filter
        doc_type_filter = document_types[0] if document_types else None
        
        # 3. Call TDOS RAG handler (pure intelligence)
        try:
            result = self.rag_handler.query(
                text=query,
                guild_id=context.guild_id,
                document_type=doc_type_filter,
                top_k=top_k
            )
            
            # 4. Log metrics to MongoDB
            await self._log_query_metrics(context, query, result)
            
            return result
        except Exception as e:
            logger.error("[RAG Adapter] Query failed: %s", e)
            return RAGResult(
                results=[],
                latency_ms=0,
                success=False,
                message=f"Query failed: {str(e)}"
            )

    async def delete_document(
        self,
        document_id: str,
        context: RAGContext
    ) -> Dict[str, Any]:
        """Delete a document with guild ownership validation.
        
        Args:
            document_id: Document ID to delete
            context: RAG context with guild/user info
        
        Returns:
            Dict with success status
        """
        # 1. Verify guild ownership (security check)
        doc_metadata = await self._get_document_metadata(document_id)
        if not doc_metadata or doc_metadata.get("guild_id") != context.guild_id:
            return {
                "success": False,
                "error": "Document not found or access denied"
            }
        
        # 2. Call TDOS RAG handler
        try:
            result = self.rag_handler.delete(document_id, guild_id=context.guild_id)
            
            # 3. Update storage quota if successful
            if result:
                doc_size = doc_metadata.get("content_size", 0)
                await self._update_storage_usage(context, -doc_size)
            
            return {
                "success": result,
                "error": None if result else "Delete failed"
            }
        except Exception as e:
            logger.error("[RAG Adapter] Delete failed: %s", e)
            return {
                "success": False,
                "error": f"Delete failed: {str(e)}"
            }

    async def list_documents(
        self,
        context: RAGContext,
        document_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List documents for a guild.
        
        Args:
            context: RAG context with guild info
            document_type: Optional filter by type
            limit: Max results (default 50)
        
        Returns:
            List of document metadata dicts
        """
        try:
            documents = self.rag_handler.list(
                guild_id=context.guild_id,
                document_type=document_type
            )
            
            # Limit results
            return documents[:limit]
        except Exception as e:
            logger.error("[RAG Adapter] List failed: %s", e)
            return []

    # --- Helper methods ---

    async def _check_quota(self, context: RAGContext, size_bytes: int) -> bool:
        """Check if guild has enough storage quota.
        
        Args:
            context: RAG context
            size_bytes: Size to check
        
        Returns:
            True if quota allows, False otherwise
        """
        if context.is_premium:
            # Premium guilds have unlimited storage
            return True
        
        # Free tier quota check
        quota = context.storage_quota or (100 * 1024 * 1024)  # Default 100MB
        used = context.storage_used or 0
        return (used + size_bytes) <= quota

    async def _update_storage_usage(self, context: RAGContext, delta_bytes: int) -> None:
        """Update storage usage tracking.
        
        Args:
            context: RAG context
            delta_bytes: Change in bytes (positive or negative)
        """
        # TODO: Implement storage tracking in MongoDB
        logger.debug("[RAG Adapter] Storage delta: %d bytes for guild %s", delta_bytes, context.guild_id)

    async def _log_ingestion_metrics(
        self,
        context: RAGContext,
        result: Any
    ) -> None:
        """Log ingestion metrics to MongoDB.
        
        Args:
            context: RAG context
            result: Ingestion result
        """
        if result.get("success"):
            self.db.rag_documents.insert_one({
                "guild_id": context.guild_id,
                "user_id": context.user_id,
                "document_id": result.get("document_id"),
                "operation": "ingest",
                "success": True,
                "chunks_created": result.get("ingested_chunks", 0),
                "timestamp": None
            })

    async def _log_query_metrics(
        self,
        context: RAGContext,
        query: str,
        result: RAGResult
    ) -> None:
        """Log query metrics to MongoDB.
        
        Args:
            context: RAG context
            query: Search query
            result: Query result
        """
        self.db.rag_metrics.insert_one({
            "guild_id": context.guild_id,
            "user_id": context.user_id,
            "operation": "query",
            "query": query,
            "chunks_returned": len(result.results) if hasattr(result, 'results') else 0,
            "success": result.success if hasattr(result, 'success') else False,
            "timestamp": None  # Add timestamp utility
        })

    async def _get_document_metadata(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata from storage.
        
        Args:
            document_id: Document ID
        
        Returns:
            Metadata dict or None
        """
        # This would query ChromaDB or MongoDB for document metadata
        # For now, return placeholder
        return {"guild_id": "unknown", "content_size": 0}


# Singleton pattern
_rag_adapter_instance: Optional[RAGAdapter] = None


def get_rag_adapter() -> RAGAdapter:
    """Get singleton RAG adapter instance.
    
    Returns:
        RAGAdapter instance
    """
    global _rag_adapter_instance
    if _rag_adapter_instance is None:
        _rag_adapter_instance = RAGAdapter()
    return _rag_adapter_instance

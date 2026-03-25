#!/usr/bin/env python3
"""RAG Cleanup Utility - Reset Chroma and MongoDB RAG data for testing.

Usage:
    python cleanup_rag.py              # Show usage
    python cleanup_rag.py --clear-all  # Clear entire Chroma collection
    python cleanup_rag.py --guild 123  # Clear guild 123 from Chroma + Mongo
"""

import asyncio
import argparse
import sys
import logging
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


async def cleanup_guild_rag(guild_id: str) -> bool:
    """Delete all RAG data for a guild from Chroma and MongoDB.
    
    Args:
        guild_id: Guild ID to delete
    
    Returns:
        True if successful
    """
    try:
        # Import here to avoid circular deps
        from tdos_intelligence.rag.handler import get_rag_handler
        from abby_core.database.mongodb import get_rag_documents_collection
        
        # Delete from Chroma
        logger.info(f"[RAG Cleanup] Deleting guild {guild_id} from Chroma...")
        handler = get_rag_handler()
        if handler.delete_by_guild(guild_id):
            logger.info(f"[RAG Cleanup] ✓ Removed {guild_id} from Chroma")
        else:
            logger.error(f"[RAG Cleanup] ✗ Failed to delete {guild_id} from Chroma")
            return False
        
        # Delete from MongoDB
        logger.info(f"[RAG Cleanup] Deleting guild {guild_id} from MongoDB...")
        mongo_collection = get_rag_documents_collection()
        if mongo_collection is not None:
            result = mongo_collection.delete_many({"scope": guild_id})
            if result.deleted_count > 0:
                logger.info(f"[RAG Cleanup] ✓ Removed {result.deleted_count} documents from MongoDB")
            else:
                logger.info(f"[RAG Cleanup] No documents found for guild {guild_id} in MongoDB")
        else:
            logger.warning("[RAG Cleanup] MongoDB RAG collection not available")
        
        logger.info(f"[RAG Cleanup] ✅ Guild {guild_id} cleanup complete")
        return True
        
    except Exception as e:
        logger.error(f"[RAG Cleanup] ✗ Guild cleanup failed: {e}")
        return False


async def cleanup_all_rag() -> bool:
    """Clear all RAG data from Chroma (WARNING: destructive operation).
    
    Returns:
        True if successful
    """
    try:
        from tdos_intelligence.rag.handler import get_rag_handler
        
        logger.warning("[RAG Cleanup] ⚠️  CLEARING ALL RAG DATA - This cannot be undone!")
        
        # Require confirmation
        response = input("Type 'DELETE ALL' to confirm: ")
        if response != "DELETE ALL":
            logger.info("[RAG Cleanup] Operation cancelled")
            return False
        
        logger.info("[RAG Cleanup] Clearing all Chroma data...")
        handler = get_rag_handler()
        if handler.clear_all():
            logger.info("[RAG Cleanup] ✓ Cleared all Chroma data")
        else:
            logger.error("[RAG Cleanup] ✗ Failed to clear Chroma")
            return False
        
        logger.info("[RAG Cleanup] ⚠️  REMEMBER: MongoDB documents still exist!")
        logger.info("[RAG Cleanup] To remove MongoDB data, run manual query or cleanup-mongo script")
        
        logger.info("[RAG Cleanup] ✅ All Chroma data cleared")
        return True
        
    except Exception as e:
        logger.error(f"[RAG Cleanup] ✗ Clear all failed: {e}")
        return False


async def cleanup_mongo_guild(guild_id: str) -> bool:
    """Delete guild documents from MongoDB only.
    
    Args:
        guild_id: Guild ID to delete
    
    Returns:
        True if successful
    """
    try:
        from abby_core.database.mongodb import get_rag_documents_collection
        
        logger.info(f"[RAG Cleanup] Deleting guild {guild_id} from MongoDB...")
        mongo_collection = get_rag_documents_collection()
        if mongo_collection is not None:
            result = mongo_collection.delete_many({"scope": guild_id})
            logger.info(f"[RAG Cleanup] ✓ Removed {result.deleted_count} documents from MongoDB")
            return True
        else:
            logger.error("[RAG Cleanup] MongoDB RAG collection not available")
            return False
        
    except Exception as e:
        logger.error(f"[RAG Cleanup] ✗ MongoDB cleanup failed: {e}")
        return False


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="RAG Cleanup Utility - Reset Chroma and MongoDB RAG data for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cleanup_rag.py --guild 123456789      Delete guild 123456789
  python cleanup_rag.py --clear-all             Clear ALL Chroma data (destructive!)
  python cleanup_rag.py --mongo-guild 123456789 Delete guild from MongoDB only
        """
    )
    
    parser.add_argument(
        "--guild",
        type=str,
        help="Guild ID to delete from Chroma and MongoDB"
    )
    parser.add_argument(
        "--clear-all",
        action="store_true",
        help="Clear ALL Chroma data (WARNING: destructive, requires confirmation)"
    )
    parser.add_argument(
        "--mongo-guild",
        type=str,
        help="Delete guild from MongoDB only"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not any([args.guild, args.clear_all, args.mongo_guild]):
        parser.print_help()
        sys.exit(1)
    
    # Execute requested operation
    if args.guild:
        success = await cleanup_guild_rag(args.guild)
    elif args.clear_all:
        success = await cleanup_all_rag()
    elif args.mongo_guild:
        success = await cleanup_mongo_guild(args.mongo_guild)
    else:
        success = False
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

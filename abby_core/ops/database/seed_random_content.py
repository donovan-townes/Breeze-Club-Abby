"""
Seed Random Content Collection
Initializes the random_content_items collection with system defaults.

Usage:
    python scripts/seed_random_content.py              # Seed system defaults
    python scripts/seed_random_content.py --reset      # Clear and re-seed
    python scripts/seed_random_content.py --verify     # Check status only
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from abby_core.database.mongodb import connect_to_mongodb
from abby_core.database.random_content_items import RandomContentItems
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)


def verify_collection():
    """Verify collection status and show stats."""
    try:
        collection = RandomContentItems.get_collection()
        
        # Get counts by scope
        system_count = collection.count_documents({"scope": "system"})
        guild_count = collection.count_documents({"scope": "guild"})
        total_count = collection.count_documents({})
        
        # Get counts by status
        active_count = collection.count_documents({"status": "active"})
        disabled_count = collection.count_documents({"status": "disabled"})
        
        # Get counts by source type
        manual_count = collection.count_documents({"source_type": "manual"})
        llm_count = collection.count_documents({"source_type": "llm"})
        system_type_count = collection.count_documents({"source_type": "system"})
        
        logger.info("\n" + "="*60)
        logger.info("Random Content Collection Status")
        logger.info("="*60)
        logger.info(f"Total items:        {total_count}")
        logger.info(f"  System scope:     {system_count}")
        logger.info(f"  Guild scope:      {guild_count}")
        logger.info("")
        logger.info(f"Active items:       {active_count}")
        logger.info(f"Disabled items:     {disabled_count}")
        logger.info("")
        logger.info(f"Manual content:     {manual_count}")
        logger.info(f"LLM prompts:        {llm_count}")
        logger.info(f"System defaults:    {system_type_count}")
        logger.info("="*60)
        
        # Show sample system defaults
        if system_count > 0:
            logger.info("\nSystem defaults:")
            system_items = list(collection.find({"scope": "system"}).limit(3))
            for item in system_items:
                text = item.get("content", {}).get("text", "")
                category = item.get("category", "unknown")
                logger.info(f"  [{category}] {text[:60]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"Error verifying collection: {e}")
        return False


def reset_collection():
    """Clear and re-seed the collection."""
    try:
        collection = RandomContentItems.get_collection()
        
        # Delete only system scope items
        result = collection.delete_many({"scope": "system"})
        logger.info(f"[✓] Deleted {result.deleted_count} system items")
        
        # Re-seed
        success = RandomContentItems.seed_defaults()
        if success:
            logger.info("[✓] Collection reset and re-seeded successfully")
        else:
            logger.error("[✗] Failed to re-seed collection")
        
        return success
        
    except Exception as e:
        logger.error(f"Error resetting collection: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Seed random content collection")
    parser.add_argument("--reset", action="store_true", help="Clear and re-seed system defaults")
    parser.add_argument("--verify", action="store_true", help="Verify collection status only")
    args = parser.parse_args()
    
    try:
        # Connect to MongoDB
        logger.info("[*] Connecting to MongoDB...")
        connect_to_mongodb()
        logger.info("[✓] MongoDB connected")
        
        if args.verify:
            # Verify only
            logger.info("\n[*] Verifying collection status...")
            success = verify_collection()
            
        elif args.reset:
            # Reset and re-seed
            logger.info("\n[*] Resetting collection...")
            success = reset_collection()
            if success:
                verify_collection()
            
        else:
            # Normal seed (idempotent)
            logger.info("\n[*] Initializing collection...")
            success = RandomContentItems.initialize_collection()
            
            if success:
                logger.info("[✓] Collection initialized successfully")
                verify_collection()
            else:
                logger.error("[✗] Collection initialization failed")
        
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

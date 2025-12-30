"""
MongoDB Index Initialization Script

Run this script once after migration or on first startup to create all
required indexes for the unified Abby database.

Usage:
    python -m abby-core.utils.init_indexes
"""

import sys
from pathlib import Path

# Add abby-core to path
ABBY_CORE_PATH = Path(__file__).parent.parent
if str(ABBY_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(ABBY_CORE_PATH))

from abby_core.utils.mongo_db import create_indexes, get_database
from abby_core.utils.log_config import logging, setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def main():
    """Initialize all MongoDB indexes for unified schema."""
    try:
        logger.info("=" * 60)
        logger.info("MongoDB Index Initialization for Unified Abby Database")
        logger.info("=" * 60)
        
        # Verify database connection
        db = get_database()
        logger.info(f"Connected to database: {db.name}")
        
        # Create all indexes
        logger.info("Creating indexes for all collections...")
        create_indexes()
        
        # Verify indexes created
        logger.info("\nVerifying indexes...")
        collections = ["users", "sessions", "xp", "economy", "submissions", "rag_documents"]
        
        for coll_name in collections:
            coll = db[coll_name]
            indexes = list(coll.list_indexes())
            logger.info(f"\n{coll_name}: {len(indexes)} indexes")
            for idx in indexes:
                logger.info(f"  - {idx['name']}: {idx.get('key', {})}")
        
        logger.info("\n" + "=" * 60)
        logger.info("Index initialization complete!")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"Index initialization failed: {e}")
        raise


if __name__ == "__main__":
    main()

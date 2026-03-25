# Collection Module Template

Use this template to create a new MongoDB collection module.

## Steps

1. Create a file in abby_core/database/collections/<name>.py
2. Implement the CollectionModule subclass below
3. Import the class in abby_core/database/collections/**init**.py
4. Update docs/database/COLLECTION_INVENTORY.md

## Template

```python
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


class MyCollection(CollectionModule):
    """My collection module."""

    collection_name = "my_collection"

    @staticmethod
    def get_collection():
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        db = get_database()
        return db[MyCollection.collection_name]

    @staticmethod
    def ensure_indexes():
        try:
            collection = MyCollection.get_collection()

            # collection.create_index([("user_id", 1)], unique=True)
            # collection.create_index([("guild_id", 1), ("status", 1)])
            # collection.create_index([("created_at", 1)], expireAfterSeconds=604800)

            logger.debug("[MyCollection] Indexes created")
        except Exception as e:
            logger.warning(f"[MyCollection] Error creating indexes: {e}")

    @staticmethod
    def seed_defaults() -> bool:
        try:
            collection = MyCollection.get_collection()

            # if collection.count_documents({}) > 0:
            #     return True
            # collection.insert_many([...])

            return True
        except Exception as e:
            logger.error(f"[MyCollection] Error seeding defaults: {e}")
            return False

    @staticmethod
    def initialize_collection() -> bool:
        try:
            MyCollection.ensure_indexes()
            MyCollection.seed_defaults()
            logger.debug("[MyCollection] Initialized")
            return True
        except Exception as e:
            logger.error(f"[MyCollection] Error initializing: {e}")
            return False
```python

## Checklist

- CollectionModule subclass created
- `collection_name` set
- `get_collection()` uses get_database()
- Indexes defined for query patterns
- `seed_defaults()` idempotent
- Module imported in abby_core/database/collections/**init**.py
- Inventory updated

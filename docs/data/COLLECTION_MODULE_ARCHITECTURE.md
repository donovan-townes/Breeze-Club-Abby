# Database Collection Architecture Guide

> **Deprecated (Feb 3, 2026):** This document is consolidated into [ARCHITECTURE.md](ARCHITECTURE.md). Use that file as the canonical reference.

### Industry-Standard Pattern for Foolproof Collection Modules

## Overview

We've implemented an **Abstract Base Class (ABC) pattern** inspired by industry standards:

- **Django Models** - All models inherit from `Model` base
- **SQLAlchemy** - All ORM classes inherit from `declarative_base`
- **FastAPI** - All routers inherit from `APIRouter`

This ensures **every collection follows the exact same pattern** - making it impossible to create a collection that doesn't follow our architecture.

## The Problem We Solved

### Before this pattern:

- Collections could be created without proper indexes
- No guarantee of initialization at startup
- Hard-coding specific collections in main.py
- New collections required manual registration
- Easy to forget required methods
- Risk of data corruption from missing indexes

### After this pattern:

- ✅ Collections MUST implement all required methods
- ✅ Automatic validation at import time
- ✅ Self-registering with database
- ✅ Type-safe (Mypy catches errors)
- ✅ Foolproof - impossible to miss steps

## The Pattern

### 1. Base Class: `CollectionModule`

Located: `abby_core/database/base.py`

```python
from abby_core.database.base import CollectionModule

class MyCollection(CollectionModule):
    collection_name = "my_collection"

    @staticmethod
    def get_collection():
        # REQUIRED: Return collection object
        pass

    @staticmethod
    def ensure_indexes():
        # REQUIRED: Create all indexes
        pass

    @staticmethod
    def seed_defaults() -> bool:
        # REQUIRED: Seed optional defaults
        pass

    @staticmethod
    def initialize_collection() -> bool:
        # REQUIRED: Orchestrate initialization
        pass
```python

### 2. Automatic Validation

When a class inherits from `CollectionModule`:

```python
class MyCollection(CollectionModule):  # <-- __init_subclass__ called here
    collection_name = "my_collection"

    # If you forget any required method...
    # TypeError: Collection module MyCollection is missing required methods: ensure_indexes, seed_defaults, initialize_collection
```python

### 3. Automatic Registration

When a module is imported:

```python
from abby_core.database.my_collection import MyCollection

## Automatically:
## 1. Validates all methods exist
## 2. Registers MyCollection.initialize_collection() with database
## 3. Logs: "[CollectionModule] ✓ Registered collection: my_collection"
## 4. Collection will auto-initialize at bot startup
```python

## Implementation Steps

### Step 1: Create Module File

Create `abby_core/database/collections/my_collection.py`:

```python
from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
import logging

logger = logging.getLogger(__name__)


class MyCollection(CollectionModule):
    """My new collection module."""

    collection_name = "my_collection"

    @staticmethod
    def get_collection():
        if not get_database:
            raise RuntimeError("MongoDB not available")
        db = get_database()
        return db[MyCollection.collection_name]

    @staticmethod
    def ensure_indexes():
        try:
            collection = MyCollection.get_collection()

            # Create your indexes
            collection.create_index([("user_id", 1)], unique=True)
            collection.create_index([("guild_id", 1)])

            logger.debug("[MyCollection] Indexes created")
        except Exception as e:
            logger.warning(f"[MyCollection] Error creating indexes: {e}")

    @staticmethod
    def seed_defaults() -> bool:
        try:
            collection = MyCollection.get_collection()

            # Check if already seeded
            if collection.count_documents({}) > 0:
                return True

            # Seed defaults
            defaults = [...]
            collection.insert_many(defaults)

            logger.info(f"[MyCollection] ✓ Seeded {len(defaults)} items")
            return True

        except Exception as e:
            logger.error(f"[MyCollection] Error seeding: {e}")
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

### Step 2: Import in `collections/__init__.py`

Add to `abby_core/database/collections/__init__.py`:

```python
from abby_core.database.collections.my_collection import MyCollection
```python

No changes are required in abby_core/database/**init**.py. It auto-imports the collections package.

That's it! The collection will:

1. ✅ Validate all methods exist
2. ✅ Auto-register with database
3. ✅ Initialize at bot startup
4. ✅ Self-discover via registry

### Step 3: Use in Your Code

```python
from abby_core.database.collections.my_collection import MyCollection

## Access the collection
collection = MyCollection.get_collection()

## Run operations
result = collection.insert_one({"name": "test"})
items = collection.find({"status": "active"})
```python

## Current Implementations

### ✅ RandomContentItems

- **File**: `abby_core/database/collections/random_content_items.py`
- **Status**: Production-ready
- **Initialization**: ✓ Implemented
- **Indexes**: 5 compound indexes
- **Defaults**: 6 system prompts seeded

### ✅ SystemConfiguration

- **File**: `abby_core/database/collections/system_configuration.py`
- **Status**: Production-ready
- **Initialization**: ✓ Implemented
- **Indexes**: 1 primary key (default)
- **Defaults**: System job configuration seeded

## Benefits of This Architecture

### 1. Type Safety

Mypy catches missing methods at type-check time:

```bash
mypy abby_core/database/
## Error: MyCollection is missing methods: seed_defaults
```python

### 2. Runtime Validation

Import-time validation:

```python
from abby_core.database.bad_collection import BadCollection
## TypeError: Collection module BadCollection is missing required methods: ensure_indexes
```python

### 3. Auto-Discovery

Collections register themselves:

```python
from abby_core.database import initialize_all_collections

initialize_all_collections()  # Automatically initializes ALL collections
```python

### 4. Consistency

All collections follow the same pattern:

- Same method signatures
- Same error handling
- Same logging format
- Same index strategy

### 5. Discoverability

New developers can:

1. Copy template from `COLLECTION_MODULE_TEMPLATE.md`
2. Implement 5 methods
3. Add import to `__init__.py`
4. Done! Collection auto-registers

## Design Decisions

### Why Abstract Base Class?

- ✅ Python standard approach
- ✅ Type-safe (Mypy support)
- ✅ Runtime validation via `__init_subclass__`
- ✅ Similar to Django, SQLAlchemy, FastAPI
- ✅ Self-documenting

### Why Static Methods?

- Collections are singletons (one per database)
- No instance state needed
- Cleaner API: `MyCollection.get_collection()` vs `MyCollection().get_collection()`
- Prevents accidental multiple instances

### Why Auto-Registration?

- No manual registration list to maintain
- Collections self-discover at import
- Impossible to forget to register
- Scales to any number of collections

### Why Fail Gracefully?

- Never raise exceptions from initialization
- Log errors instead
- Bot continues even if one collection fails
- Prevent cascading failures

## Industry Precedents

### Django Models

```python
class User(models.Model):
    name = models.CharField()

    class Meta:
        db_table = "users"
## Automatically:
## - Validates schema
## - Creates tables
## - Creates indexes
## - Discovered by ORM
```python

### SQLAlchemy

```python
class User(Base):
    __tablename__ = "users"
    name = Column(String)
## Automatically:
## - Validates schema
## - Registers with session
## - Creates tables/indexes
## - Handles migrations
```python

### FastAPI

```python
class MyRouter(APIRouter):
    pass

app.include_router(MyRouter())
## Automatically:
## - Validates endpoints
## - Generates OpenAPI docs
## - Handles routing
```python

## Next Steps

### Week 1: Complete P0 Collections

1. **Guild Configuration** - Most important after random content
2. **Chat Sessions** - Needed for conversation history
3. **Economy** - Core game mechanic
4. **Users** - Profile data

### Week 2: P1 Collections

1. **XP System**
2. **Submissions**
3. **Music Genres**
4. **Integration Testing**

### Week 3-4: Remaining Collections

1. **Content Delivery Items**
2. **RAG Documents**
3. **System State**
4. **Full E2E Testing**

## Validation Checklist

When creating a new collection, verify:

- [ ] Inherits from `CollectionModule`
- [ ] Set `collection_name` class variable
- [ ] Implement `get_collection()` returning `db[collection_name]`
- [ ] Implement `ensure_indexes()` with all necessary indexes
- [ ] Implement `seed_defaults()` returning `bool`
- [ ] Implement `initialize_collection()` calling the above
- [ ] Add import to `abby_core/database/__init__.py`
- [ ] Run `pytest tests/` and verify no errors
- [ ] Run `python launch.py --dev` and verify collection initializes
- [ ] Check logs for `[CollectionModule] ✓ Registered collection: my_collection`

## Troubleshooting

### Error: "Collection module X is missing required methods"

**Cause**: Forgot to implement a required method

**Fix**:

1. Open `abby_core/database/my_collection.py`
2. Add the missing method (see template in `COLLECTION_MODULE_TEMPLATE.md`)
3. Verify it's a `@staticmethod`

### Error: "MongoDB connection not available"

**Cause**: Trying to access collection before database connection

**Fix**:

```python
## Before bot startup
try:
    collection = MyCollection.get_collection()
except RuntimeError as e:
    # Expected - database not connected yet
    pass

## After bot startup (connection ready)
collection = MyCollection.get_collection()  # OK!
```python

### Collection not initializing at startup

**Cause**: Module not imported in `abby_core/database/__init__.py`

**Fix**:

```python
## Add to abby_core/database/__init__.py
from abby_core.database.my_collection import MyCollection
```python

### Indexes not created

**Cause**: `ensure_indexes()` throwing exception (and caught silently)

**Fix**:

1. Check logs for `[MyCollection] Error creating indexes: ...`
2. Verify index syntax in `ensure_indexes()` method
3. Run `MyCollection.ensure_indexes()` directly to see error

## References

- **Base Class**: `abby_core/database/base.py`
- **Template**: `docs/data/COLLECTION_MODULE_TEMPLATE.md`
- **Example**: `abby_core/database/random_content_items.py`
- **Registry**: `abby_core/database/__init__.py`

---

**This architecture ensures that every collection follows the exact same foolproof pattern, making it impossible to create a collection without proper initialization, indexes, and lifecycle management.**

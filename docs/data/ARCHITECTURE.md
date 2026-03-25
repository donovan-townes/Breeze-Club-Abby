# Data Layer Architecture

## Purpose

This document consolidates Abby’s collection architecture into a single canonical reference. It defines how collections are structured, initialized, registered, and verified. It replaces:

- COLLECTION_MODULE_ARCHITECTURE.md
- DATABASE_COLLECTION_ARCHITECTURE.md

## Core Principles

- **Consistency:** Every collection follows the same interface and lifecycle.
- **Idempotent startup:** Initializers can run multiple times safely.
- **Index-driven design:** Indexes must reflect query patterns.
- **Isolation:** Initialization failures are logged per collection and never crash startup.
- **No adapter coupling:** Database modules must not import adapters.

## Architecture Overview

### Initialization Flow

```text
Bot startup
  ↓
MongoDB connected
  ↓
initialize_all_collections()
  ↓
CollectionModule subclasses auto‑register
  ↓
Each collection initialize_collection() runs
```

### Components

#### 1) Registry (startup orchestration)

- **Location:** abby_core/database/__init__.py
- **Responsibilities:**
  - `register_collection_initializer()` collects initializers
  - `initialize_all_collections()` runs them with logging and failure isolation

#### 2) Collection modules (one per collection)

- **Location:** abby_core/database/collections/
- Each module defines a `CollectionModule` subclass and required methods:
  - `get_collection()`
  - `ensure_indexes()`
  - `seed_defaults()`
  - `initialize_collection()`

#### 3) Collection import list

- **Location:** abby_core/database/collections/__init__.py
- All collection modules must be imported here so they auto‑register at startup.

#### 4) Inventory of record

- **Location:** COLLECTION_INVENTORY.md
- Maintain ownership, lifecycle, and status for every collection.

## The CollectionModule Standard

### Base Class

Located: abby_core/database/base.py

```python
from abby_core.database.base import CollectionModule

class MyCollection(CollectionModule):
    collection_name = "my_collection"

    @staticmethod
    def get_collection():
        pass

    @staticmethod
    def ensure_indexes():
        pass

    @staticmethod
    def seed_defaults() -> bool:
        pass

    @staticmethod
    def initialize_collection() -> bool:
        pass
```

### Automatic Validation

`CollectionModule` uses `__init_subclass__` to validate required methods at import time. Missing methods raise a `TypeError` before runtime.

### Automatic Registration

Importing the module auto‑registers the initializer with the registry. Startup runs all registered initializers in a controlled sequence.

## Adding a Collection (Required Steps)

1. Create a module in abby_core/database/collections/<name>.py
2. Implement `CollectionModule` (use COLLECTION_MODULE_TEMPLATE.md)
3. Import the class in abby_core/database/collections/__init__.py
4. Update COLLECTION_INVENTORY.md
5. Add tests if the collection is read/write critical

## Non‑Negotiables

- Idempotent initialization (safe to run multiple times)
- Indexes must match query patterns
- Initialization must not crash startup
- Use `get_database()` (no direct connection objects)
- No adapter imports in database modules

## Validation Checklist

When creating a new collection, verify:

- [ ] Inherits from `CollectionModule`
- [ ] Set `collection_name` class variable
- [ ] Implement `get_collection()` returning `db[collection_name]`
- [ ] Implement `ensure_indexes()` with all necessary indexes
- [ ] Implement `seed_defaults()` returning `bool`
- [ ] Implement `initialize_collection()` calling the above
- [ ] Add import to abby_core/database/collections/__init__.py
- [ ] Run `pytest tests/` and verify no errors
- [ ] Run `python launch.py --dev` and verify collection initializes
- [ ] Check logs for `[CollectionModule] ✓ Registered collection: my_collection`

## Verification Signals

- Startup logs show: “Initializing N collection(s)”
- Failures are logged per module without aborting startup
- Critical collections run initializer tests

## References

- COLLECTION_INVENTORY.md — Collection ownership and lifecycle
- COLLECTION_MODULE_TEMPLATE.md — Template for new collection modules
- UNIVERSAL_USER_SCHEMA.md — Canonical user schema

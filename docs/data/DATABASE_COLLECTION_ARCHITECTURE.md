# Database Collection Initialization — Architecture Guide

> **Deprecated (Feb 3, 2026):** This document is consolidated into [ARCHITECTURE.md](ARCHITECTURE.md). Use that file as the canonical reference.

## Purpose

This document defines how database collections are structured, initialized, and registered. It is the canonical reference for collection lifecycle behavior.

## Initialization flow

```python
Bot startup
  ↓
MongoDB connected
  ↓
initialize_all_collections()
  ↓
CollectionModule subclasses auto-register
  ↓
Each collection initialize_collection() runs
```python

## Components

### 1) Registry (startup orchestration)

- Location: abby_core/database/**init**.py
- Responsibilities:
  - `register_collection_initializer()` collects initializers
  - `initialize_all_collections()` runs them with logging and failure isolation

### 2) Collection modules (one per collection)

- Location: abby_core/database/collections/
- Each module defines a CollectionModule subclass and required methods:
  - `get_collection()`
  - `ensure_indexes()`
  - `seed_defaults()`
  - `initialize_collection()`

### 3) Collection import list

- Location: abby_core/database/collections/**init**.py
- All collection modules must be imported here so they auto-register at startup.

### 4) Inventory of record

- Location: docs/data/COLLECTION_INVENTORY.md
- Keep ownership, lifecycle, and status accurate.

## Adding a collection (required steps)

1. Create a module in abby_core/database/collections/<name>.py
2. Implement CollectionModule (use docs/data/COLLECTION_MODULE_TEMPLATE.md)
3. Import the new class in abby_core/database/collections/**init**.py
4. Update docs/data/COLLECTION_INVENTORY.md
5. Add tests if the collection is read/write critical

## Non‑negotiables (from audit)

- Idempotent initialization (safe to run multiple times)
- Indexes must match query patterns
- Initialization must not crash startup
- Use get_database() (no direct connection objects)
- No adapter imports in database modules

## Legacy and deprecation policy

- Legacy accessors may remain temporarily, but must call the collection module
- New code must use the collection module directly
- Mark legacy files as deprecated and schedule removal

## Verification

- Startup logs should show: “Initializing N collection(s)”
- Failures must be logged per module without aborting startup
- Run collection initializers in tests for critical collections

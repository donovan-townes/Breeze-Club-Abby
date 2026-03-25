# Data Layer — Best Practices

## Purpose

This document defines the practical standards for designing, evolving, and operating Abby’s data layer. It complements ARCHITECTURE.md, which defines the collection lifecycle and initialization model.

## Core Principles

- **Stable schemas:** Avoid breaking changes unless migration is planned and tested.
- **Index‑aligned queries:** Every critical query must be backed by an index.
- **Idempotent initialization:** Collection initialization must be safe to run multiple times.
- **Operational safety:** Never crash startup due to a single collection initializer.
- **No adapter coupling:** Database modules are platform‑agnostic.

## Naming Conventions

- Collection names are lowercase, snake_case, plural when appropriate.
- Field names are lowercase, snake_case.
- Boolean fields use `is_` or `has_` prefixes.
- Time fields use UTC and a consistent suffix: `_at` (e.g., `created_at`, `expires_at`).

## Indexing Standards

- Every query used in scheduled jobs or hot paths must be indexed.
- Prefer compound indexes for common multi‑field filters.
- Avoid unbounded text indexes unless explicitly required.
- Document query patterns in COLLECTION_INVENTORY.md when adding new indexes.

## Initialization & Seeding

- Implement `ensure_indexes()` and `seed_defaults()` in every collection module.
- Seeding must be safe to run multiple times and should short‑circuit if data exists.
- Initializers must **log and continue** rather than raise fatal errors.

## Schema Changes

- Update collection modules first, then update documentation.
- Update COLLECTION_INVENTORY.md for any new or modified collection.
- If architectural patterns change, update ARCHITECTURE.md.
- Run tests and validate startup logs after schema changes.

## Testing Expectations

- Add tests for new collections with business‑critical read/write paths.
- Validate initialization flow using `python launch.py --dev`.
- Confirm index creation via startup logs or database inspection.

## References

- ARCHITECTURE.md — Collection lifecycle and initialization model
- COLLECTION_MODULE_TEMPLATE.md — Required module template
- COLLECTION_INVENTORY.md — Collection ownership and lifecycle
- UNIVERSAL_USER_SCHEMA.md — Canonical user schema

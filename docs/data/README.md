# Database Documentation

This folder documents Abby's MongoDB data model, collection standards, and maintenance patterns.

## Start here

- [COLLECTION_INVENTORY.md](COLLECTION_INVENTORY.md) — Authoritative list of collections and ownership
- [ARCHITECTURE.md](ARCHITECTURE.md) — Canonical collection architecture (merged)
- [BEST_PRACTICES.md](BEST_PRACTICES.md) — Naming, indexing, and schema standards

> Note: DATABASE_COLLECTION_ARCHITECTURE.md and COLLECTION_MODULE_ARCHITECTURE.md are deprecated and retained for history only.

## Reference

- [COLLECTION_MODULE_TEMPLATE.md](COLLECTION_MODULE_TEMPLATE.md) — Template for new collections

## Source of truth

Collection definitions live in abby_core/database/collections. Changes to schemas must update:

1. COLLECTION_INVENTORY.md
2. ARCHITECTURE.md (if patterns change)

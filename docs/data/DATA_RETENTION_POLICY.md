# Data Retention Policy

## Purpose

Defines retention, archival, and deletion rules for ABBY’s data layer. This policy prioritizes safety, compliance, and long‑term operability.

## Retention Principles

- **Minimum viable retention:** keep only what is operationally or legally required.
- **Auditability:** retain decision‑critical logs for traceability.
- **Privacy first:** remove or anonymize data on request.
- **TTL enforcement:** prefer TTL indexes for automatic cleanup.

## Retention Tiers

### Tier 1 — Critical State (long‑term)

- Platform state history and activation audit
- Configuration state history
- Required for 20‑50 year traceability

### Tier 2 — Operational Logs (medium)

- Delivery records
- Scheduler run logs
- Metrics aggregates
- Retain for troubleshooting and capacity planning

### Tier 3 — Transient Context (short)

- Ephemeral generation artifacts
- Temporary caches
- Retain only as long as necessary

## Deletion & Anonymization

- User deletion requests must remove or anonymize all user‑identifiable records.
- All deletion operations must be logged with `request_id` and `actor_id`.

## Implementation Guidance

- Use TTL indexes for transient collections.
- Archive historical summaries rather than raw logs where possible.
- Never store raw prompts unless explicitly required and approved.

## Review Cadence

- **Quarterly:** verify TTL indexes are present and active
- **Annually:** review retention tiers and legal requirements

## Reference

- [data/COLLECTION_INVENTORY.md](COLLECTION_INVENTORY.md)
- [data/ARCHITECTURE.md](ARCHITECTURE.md)
- [operations/SECURITY_GUIDE.md](../operations/SECURITY_GUIDE.md)

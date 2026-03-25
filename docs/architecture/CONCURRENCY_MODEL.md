# Concurrency Model

## Purpose

This document defines how ABBY handles concurrency, atomicity, and ordering across services. It is the canonical reference for safe parallel execution and state mutation.

## Core Model

- **Async event loop:** Most runtime behavior is `asyncio`‑based.
- **Scheduler‑driven work:** Long‑running or periodic tasks run through SchedulerService.
- **MongoDB transactions:** Used for state activation and any multi‑document invariant updates.

## Concurrency Domains

### 1) Scheduler Jobs

- Jobs are claimed atomically from `scheduler_jobs`.
- **At‑most‑once** execution per tick.
- Handlers must be **idempotent**.

### 2) State Activation

- Platform state changes execute inside a transaction.
- Conflicting states must be deactivated before activation.
- Validation runs before mutation.

### 3) Content Delivery Lifecycle

- `content_delivery_items` transitions are sequential:
  `pending → generating → ready → delivered`
- Delivery workers must only operate on `ready` items.
- Idempotent delivery writes ensure retries are safe.

### 4) Conversation Handling

- Requests are stateless across calls.
- Generation state is ephemeral and must not be persisted.

## Atomicity Guarantees

- **State transitions:** Atomic via MongoDB transactions.
- **Job claiming:** Atomic via `find_one_and_update` or equivalent.
- **Delivery writes:** Append‑only with idempotent checks.

## Ordering Rules

- **State activation precedes dependent jobs.**
- **Generation follows lifecycle status.**
- **Delivery follows generation readiness.**

## Idempotency Rules

All handlers must:

- Use deterministic identifiers (e.g., `job_id`, `delivery_id`).
- Avoid duplicate writes on retries.
- Check for existing artifacts before creating new ones.

## Error & Retry Policy

- **Retryable errors:** re‑queued via DLQService.
- **Fatal errors:** logged with audit trail.
- **Never crash the event loop** due to a single job failure.

## Safe Parallelism Guidelines

- Use collection‑level locks only when necessary.
- Avoid long‑lived transactions.
- Prefer optimistic concurrency (e.g., compare‑and‑set).

## Reference

- [runtime/SCHEDULER_ARCHITECTURE.md](../runtime/SCHEDULER_ARCHITECTURE.md)
- [lifecycle/STATE_INVARIANTS.md](../lifecycle/STATE_INVARIANTS.md)
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)

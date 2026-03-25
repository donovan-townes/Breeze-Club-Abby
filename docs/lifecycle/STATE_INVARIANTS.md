# State Invariants

## Purpose

This document defines the invariants that **must never be violated** across ABBY’s state domains. These rules are enforced by StateValidationService and used as operational guardrails.

## Global Invariants

1. **Single active state per type** — only one season, one event, one mode can be active at a time.
2. **Platform state is authoritative** — configuration cannot override platform state.
3. **No direct mutation** — only StateActivationService can mutate platform state collections.
4. **Generation state is ephemeral** — never persist prompts or per‑request transient data.

## Platform State Invariants

- Every activation must write an audit trail.
- Conflicting states are deactivated before activation.
- State activation is atomic and validated.

## Lifecycle State Invariants

- `generation_status` must follow the ordered lifecycle:
  `pending → generating → ready → delivered`.
- `ready` items are immutable except for delivery metadata.
- Delivery must never occur for non‑ready items.

## Configuration State Invariants

- Configuration only scopes behavior (channels, toggles, thresholds).
- Configuration must not override platform state effects.

## Gameplay State Invariants

- Gameplay toggles must be event‑bound.
- Gameplay effects cannot mutate persona directly.

## Conversation FSM Invariants

- Session state transitions must be valid per FSM.
- Aborted sessions must be closed, not left in limbo.

## Enforcement Points

- **StateValidationService** — pre‑activation checks.
- **StateActivationService** — transactional mutations.
- **SchedulerService** — ensures time‑bound state transitions.
- **Lifecycle pipeline** — enforces content delivery ordering.

## Reference

- [lifecycle/STATE_MAP.md](STATE_MAP.md)
- [SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md)
- [architecture/CONCURRENCY_MODEL.md](../architecture/CONCURRENCY_MODEL.md)

# Capacity Planning

## Purpose

Defines how to estimate, monitor, and scale ABBY’s operational capacity.

## Key Capacity Drivers

- **Scheduler throughput** (jobs per minute)
- **Generation latency** (LLM round‑trip)
- **Memory/RAG retrieval** (vector DB latency)
- **Delivery throughput** (messages per minute)

## Baseline Metrics

Track these continuously:

- Scheduler tick duration (p50/p95)
- Pending jobs count
- Generation latency (p50/p95)
- DLQ volume
- Delivery success rate
- Database query latency

## Scaling Triggers

Scale when any of the following persist for >15 minutes:

- Scheduler tick duration > 2× normal baseline
- Generation p95 latency > 2× baseline
- DLQ retry queue grows continuously
- Database p95 latency > 200ms on hot paths

## Capacity Planning Process

1. **Establish baseline** from production metrics.
2. **Model expected growth** (guild count, events, seasonal load).
3. **Estimate peak traffic** (announcements, events, release days).
4. **Define thresholds** for scale‑out or scale‑up.
5. **Re‑evaluate quarterly.**

## Practical Guidelines

- Prefer **horizontal scale** for scheduler and generation workers.
- Use **separate workers** for heavy jobs (e.g., large announcements).
- Keep **headroom** of at least 30% during peak events.

## Reference

- [operations/OBSERVABILITY_RUNBOOK.md](OBSERVABILITY_RUNBOOK.md)
- [runtime/SCHEDULER_ARCHITECTURE.md](../runtime/SCHEDULER_ARCHITECTURE.md)
- [runtime/GENERATION_PIPELINE.md](../runtime/GENERATION_PIPELINE.md)

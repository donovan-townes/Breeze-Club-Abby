# Platform Overview

Abby is a state-driven conversational platform built to host long-lived communities, events, and creative ecosystems. She combines canonical platform state (seasons, events, modes) with per-guild preferences and ephemeral LLM context to stay coherent over time while remaining adaptive in the moment.

## Why Abby exists

- Keep creative and social communities feeling alive between big events.
- Make system-wide beats (seasons, announcements) feel cohesive across guilds.
- Offer playful, opt-in engagement loops (games, drops) without grinding users down.
- Provide an operator-friendly surface with clear guardrails and auditability.

## Problems she solves

- **Consistency over time:** Platform state prevents whiplash between interactions and seasons.
- **Context-rich responses:** Generation pipeline layers persona, guild, memory, and devlog context per request.
- **Operational reliability:** SchedulerService (canonical single scheduler) + lifecycle states keep announcements and jobs predictable.
- **Scoped play:** Gameplay features stay event-bound and do not leak into persona or platform tone.
- **Platform portability:** Architecture separates core logic from adapters so adding Discord, Web, CLI, or Slack requires only adapters, not core refactoring.

## What makes Abby different

- **State-first design:** Core behaviors key off canonical state axes, not ad-hoc flags.
- **Lifecycle clarity:** Announcements and content drops move through explicit stages (pending → ready → delivered → archived).
- **Composable generation:** Persona overlays, RAG, and devlogs are injected per request instead of being baked into a single prompt.
- **Operator maturity:** Overrides, safety rails, and audit trails are first-class concerns, not afterthoughts.
- **Platform-first architecture:** Core services are adapter-agnostic; platform-specific I/O lives in adapters.

## The one-line story

Abby is a state-driven conversational platform that keeps communities coherent across seasons and events while delivering contextual, operator-safe experiences—designed for a 20-year vision of multi-platform growth.

## Architecture

This document is the product and platform intent. The technical topology lives in:

- [SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md) — subsystem boundaries and data flow

Key rule remains unchanged: core never imports adapters; adapters implement core interfaces.

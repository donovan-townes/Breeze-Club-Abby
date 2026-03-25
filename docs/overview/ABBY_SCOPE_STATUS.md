# Abby Scope and Status Map

**Purpose:** Living map of what Abby is, what is done, what is in progress, and what is planned. Update whenever you complete a feature, discover missing scope, or clean up legacy artifacts.
**Last Updated:** 2026-02-17
**Status Tags:** Done, In-Progress, Blocked, Planned, Legacy

---

## 1) Scope and Boundaries (What Abby Is / Is Not)

### What Abby Is
- A **state-driven conversational platform** with long-lived community state and explicit lifecycles.
- A **platform-agnostic core** with Discord as the current adapter.
- A **scheduler-driven system** for announcements, events, jobs, and background tasks.
- A **MongoDB-backed system of record** with explicit collection ownership and audit trails.

### What Abby Is Not
- Not a generic chatbot. It is a **platform** with state, lifecycle, and operator controls.
- Not a web app yet (web/CLI adapters are specified but not implemented).
- Not an ad-hoc prompt script. Prompt assembly is structured and state-aware.

### Canonical Architecture Boundaries
- Core logic lives in `abby_core/*` and **must not** import platform adapters.
- Adapters (Discord today) live under `abby_core/discord/*` and implement core interfaces.
- State and lifecycle changes go through services (no direct mutation).

Reference:
- [docs/overview/ABBY_CANONICAL.md](docs/overview/ABBY_CANONICAL.md)
- [docs/architecture/SYSTEM_ARCHITECTURE.md](docs/architecture/SYSTEM_ARCHITECTURE.md)
- [docs/lifecycle/STATE_MAP.md](docs/lifecycle/STATE_MAP.md)

---

## 2) Core Subsystem Coverage (Status + Evidence)

| Subsystem | Status | Evidence | Notes |
| --- | --- | --- | --- |
| Platform State + Validation | Done | [docs/architecture/SYSTEM_ARCHITECTURE.md](docs/architecture/SYSTEM_ARCHITECTURE.md), [docs/lifecycle/STATE_MAP.md](docs/lifecycle/STATE_MAP.md) | StateActivationService, StateValidationService, state invariants documented. |
| Event Lifecycle + Announcements | Done | [docs/operations/IMPLEMENTATION_COMPLETE.md](docs/operations/IMPLEMENTATION_COMPLETE.md) | Auto event lifecycle + unified content dispatcher. |
| Scheduler Service | Done | [docs/runtime/SCHEDULER_ARCHITECTURE.md](docs/runtime/SCHEDULER_ARCHITECTURE.md) | Canonical scheduler model; no platform-specific loops. |
| Content Delivery + DLQ | Done | [docs/architecture/SERVICE_CONTRACTS.md](docs/architecture/SERVICE_CONTRACTS.md), tests | DLQ retry + delivery lifecycle tracked. |
| Generation Pipeline | Done | [docs/runtime/GENERATION_PIPELINE.md](docs/runtime/GENERATION_PIPELINE.md) | Composable context, logging, state-aware prompt assembly. |
| RAG Infrastructure | In-Progress | [ISSUES.md](ISSUES.md) | Infra done; chatbot prompt injection pending + fallback behavior. |
| Economy (XP, bank, tipping) | Done | [ISSUES.md](ISSUES.md) + tests | Banking, tipping, interest, guild scoping covered. |
| Cooldowns / Daily Bonus | Done | [docs/architecture/COOLDOWN_ARCHITECTURE.md](docs/architecture/COOLDOWN_ARCHITECTURE.md) | Daily bonus persistence fixed and documented. |
| Observability + Metrics | Done | [docs/architecture/SYSTEM_ARCHITECTURE.md](docs/architecture/SYSTEM_ARCHITECTURE.md) + tests | MetricsService + generation_audit present. |
| TDOS Intelligence Layer | In-Progress | [docs/architecture/TDOS_INTELLIGENCE.md](docs/architecture/TDOS_INTELLIGENCE.md) | Core stable; packaging for external use in progress. |
| Multi-Platform Adapters | Planned | [docs/architecture/ADAPTER_CONTRACTS.md](docs/architecture/ADAPTER_CONTRACTS.md) | Contracts defined; only Discord adapter present. |

---

## 3) Discord Cogs Coverage (Status + Evidence)

### Admin
| Cog | Status | Notes |
| --- | --- | --- |
| `canon.py` | In-Progress | Existence confirmed; verify commands and operator paths. |
| `guild_assistant.py` | Done | DB config issues fixed (see DATABASE_CONFIGURATION_DIAGNOSIS). |
| `guild_config.py` | Done | Core guild config management. |
| `moderation.py` | In-Progress | Present; confirm coverage of policy + enforcement. |
| `operator_panel.py` | Done | Operator view and metrics hooks documented. |
| `rag.py` | In-Progress | RAG management UI exists; chatbot injection still pending. |
| `reload.py` | Done | Hot-reload cogs. |
| `shutdown.py` | Done | Admin-only shutdown/restart flow. |
| `slash_sync.py` | Done | Slash sync utility. |
| `status.py` | Done | Status commands documented. |
| `system_state_ops.py` | Done | State activation operations (events/seasons). |

### Creative
| Cog | Status | Notes |
| --- | --- | --- |
| `chatbot.py` | In-Progress | Core chat works; RAG prompt injection still pending. |
| `images.py` | Done | Image generation path wired; guild-scoped XP gating. |
| `analyze.py` | In-Progress | Present; verify how used in production. |

### Economy
| Cog | Status | Notes |
| --- | --- | --- |
| `bank.py` | Done | Slash command bank suite + tests. |
| `experience.py` | Done | XP query and display. |
| `stats.py` | In-Progress | Validate fields/metrics accuracy. |
| `xp_rewards.py` | Done | Daily bonus persistence fixed and stored in DB. |

### Entertainment
| Cog | Status | Notes |
| --- | --- | --- |
| `games.py` | In-Progress | Emoji game exists; extended scheduling issue open. |
| `giveaways.py` | In-Progress | Present; verify edge cases + persistence. |
| `polls.py` | In-Progress | Present; verify limits and storage. |
| `memes.py` | In-Progress | Present; verify API usage. |
| `reddit.py` | In-Progress | Present; verify API + rate limits. |
| `generators.py` | In-Progress | Present; verify output sources. |

### Community
| Cog | Status | Notes |
| --- | --- | --- |
| `announcements.py` | Done | Unified content lifecycle. |
| `motd.py` | In-Progress | Present; verify storage and scheduling. |
| `nudge_handler.py` | In-Progress | Present; verify scheduling/toggles. |
| `random_messages.py` | In-Progress | Present; verify toggles and rate caps. |
| `welcome.py` | Done | Welcome flows. |

### Events
| Cog | Status | Notes |
| --- | --- | --- |
| `valentine_hearts.py` | Done | Event system documented as production-ready. |
| `easter_eggs.py` | Planned | Event in lifecycle schedule; feature likely pending. |

### Integrations
| Cog | Status | Notes |
| --- | --- | --- |
| (folder empty) | Planned | Docs mention Twitch/Twitter; no cogs present. |

### Music
| Cog | Status | Notes |
| --- | --- | --- |
| (folder empty) | Planned | Docs state migration planned. |

### System / User / Utility
| Cog | Status | Notes |
| --- | --- | --- |
| `system/*` | Done | Scheduler job registry and handlers live here. |
| `user/*` | In-Progress | Privacy panel, profile panel, reminders, release manager need verification. |
| `utility/info.py` | Done | Utility info commands. |

---

## 4) Test Coverage Map (Evidence)

**Strategy:** 70%+ target (90% for critical paths). See [docs/operations/TEST_STRATEGY.md](docs/operations/TEST_STRATEGY.md).

| Area | Evidence (tests) | Notes |
| --- | --- | --- |
| Architecture boundaries | test_architecture_compliance, test_adapter_contracts | Ensures core/adapter separation. |
| Scheduler + idempotency | test_scheduler_idempotency, test_scheduler_heartbeat | Canonical scheduler behavior. |
| State activation + merge | test_state_* suite | Strong coverage of state system. |
| Content lifecycle + DLQ | test_content_delivery_lifecycle, test_dlq_* | Delivery and retries covered. |
| Economy + tipping | test_banking_*, test_tipping, test_economy_scoping | High coverage of banking paths. |
| Intent + memory gating | test_intent*, test_memory_injection_gating, test_prompt_injection_safety | RAG gating and safety tested. |

Known gaps:
- Some legacy tests may still have import issues (see tests/README.md).
- Feature-level tests for entertainment/integration cogs are sparse.

---

## 5) Refactor Artifacts / Legacy Cleanup Candidates

### Confirmed Legacy/Deprecated (documented)
- Legacy scripts and docs marked for deletion in [SCRIPT_CLEANUP_ANALYSIS.md](SCRIPT_CLEANUP_ANALYSIS.md).
- MongoDB auth workarounds (deprecated after moving to no-auth architecture).

### Docs or References That Are Likely Out of Date
- `abby_core/discord/cogs/README.md` references files that are not present in the current tree (e.g., integrations/music implementations).
- Integrations and music cogs folders are empty but still referenced in docs.

---

## 6) Open Work (from backlog)

**High Priority (from ISSUES.md):**
- RAG prompt injection in chatbot + fallback + relevance threshold.
- Emoji game scheduling changes (multiple windows + longer duration).

**Medium Priority (from ISSUES.md):**
- Budget/spending analytics.
- Canonical currency vocabulary and conversion.
- Store/shim for purchases.
- Ambient messages via RAG.
- Passive listening and guild insights.
- Behavioral rewards engine.
- YouTube URL handling.
- Contribution workflow docs.

---

## 7) How to Keep This Current (Process)

- Update this doc when you ship or retire a subsystem.
- Add a one-line note in devlog with the change and a link here.
- Use statuses consistently and avoid adding new tags without a reason.

---

## 8) Immediate Verification TODOs

- Confirm runtime status of entertainment cogs (games, polls, memes, reddit, generators).
- Validate moderation tooling (scope, audit, and enforcement behavior).
- Verify analyze cog output and dependencies.
- Confirm RAG chatbot injection wiring status in code.
- Confirm integrations/music are still planned (or remove from docs if dropped).

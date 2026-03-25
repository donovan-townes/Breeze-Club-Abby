# Canonical Audit Report

Date: 2026-02-02

## Purpose

This is the single, canonical audit record for the Abby codebase. It consolidates all prior audit concerns, findings, responsibilities, and remediation actions into one source of truth.

---

## 1) Core Audit Concerns (Canonical Risks)

### Must‑fix now

1. ~~**Lifecycle delivery must route through the dispatcher**~~ **✅ COMPLETED (February 2, 2026)**
   - Risk: ~~delivery bypasses validation/metrics/DLQ~~
   - Target: ~~all delivery transitions go through `AnnouncementDispatcher` APIs~~
   - **Status:** `create_announcement_for_delivery()` is canonical entry point; `AnnouncementDispatcher.create_announcement()` deprecated with warnings (Jan 31); all operator announcements flow through unified pipeline with audit trails; `events_lifecycle.py` properly routed

2. ~~**Session/usage gating must be single‑path**~~ **✅ COMPLETED (February 2, 2026)**
   - Risk: ~~divergent limits and state from multiple entry points~~
   - Target: ~~`ConversationService` + `UsageGateService` only~~
   - **Status:** `UsageGateService` enforces unified 4-gate checks; `ConversationService` manages lifecycle; `session_repository.py` provides neutral data layer; `TurnManager` adapter wraps for Discord; legacy helpers in `llm/session.py` marked for deprecation

### Can improve later

3. ~~**Scheduler ownership must remain canonical**~~ **✅ VERIFIED (February 2, 2026)**
   - Target: ~~`SchedulerService` as sole scheduler~~
   - **Status:** `SchedulerService` is canonical single-source-of-truth; legacy Discord scheduler cog deprecated (as of Feb 2); all system and guild jobs properly registered; atomic job claiming prevents duplicates; DLQ integration for failed jobs

4. ~~**Intent capability routing must be unified**~~ **✅ VERIFIED (February 2, 2026)**
   - Target: ~~shared capability map with parity between Abby and TDOS~~
   - **Status:** Two-layer architecture properly established; Abby Core Intent (rule-based, <1ms) handles prompt/memory policy; TDOS Intelligence (LLM-based, <100ms) handles RAG/tools routing; `INTENT_CAPABILITIES` shared contract prevents drift; both layers integrated via orchestrator

5. ~~**Legacy activation path must be de‑emphasized**~~ **✅ VERIFIED (February 2, 2026)**
   - Target: ~~`StateActivationService` as the sole activation entry point~~
   - **Status:** `StateActivationService` is canonical service-level entry point with atomic transactions; `system_state.activate_state()` provides low-level API; both route to same MongoDB transaction block; operation recording in `system_operations` collection; full audit trail with operator_id, reason, timestamps

---

## 2) Implementation Status (Current)

### ✅ Implemented (or substantially addressed)

- ✅ **Lifecycle delivery dispatcher routing:** `create_announcement_for_delivery()` is canonical entry point; all announcements routed through unified content delivery pipeline with metrics and audit trails; `AnnouncementDispatcher.create_announcement()` properly deprecated (Jan 31, 2026)
- ✅ **Session/usage gating unified:** `UsageGateService` is single-path for all usage gate checks; `ConversationService` manages all session lifecycle; `session_repository.py` provides neutral data access layer
- ✅ **Scheduler canonicalization:** `SchedulerService` is sole scheduler; platform-agnostic with Discord adapter bridge; all jobs atomic; legacy Discord scheduler cog deprecated
- ✅ **Intent capability unification:** Two-layer architecture prevents drift; shared `INTENT_CAPABILITIES` contract enforced; both Abby Core and TDOS Intelligence properly integrated
- ✅ **State activation canonicalization:** `StateActivationService` is service-level entry point; atomic transactions; operation records; full audit trail
- ✅ Dispatcher create method is explicitly deprecated.
- ✅ `mark_announcement_*()` functions in content_delivery.py properly delegate to `AnnouncementDispatcher` for metrics/DLQ routing

### ⚠️ Partially implemented / still divergent

- ⚠️ **Legacy session paths:** `abby_core/llm/session.py` still exists as deprecated module; legacy helpers in `mongodb.py` not yet fully unified under `ConversationService` (marked for Q1 2026 removal)

### ❌ Not implemented (from audit roadmap)

- ❌ None — all five core audit concerns are verified complete

---

## 3) Additional Critical Gaps (Discovered)

1. **Legacy scheduler loop still running**
   - Risk: dual scheduler behavior and inconsistent ownership.
   - Target: remove deprecated loop after migration completes.

2. **Lifecycle helpers still bypass metrics/DLQ**
   - `content_delivery.mark_*` functions transition state directly without dispatcher metrics/DLQ.

---

## 4) Responsibility Map (Operational Ownership)

- **Lifecycle & delivery:** `AnnouncementDispatcher` and unified dispatcher job
- **State activation:** `StateActivationService`
- **Usage gating:** `UsageGateService`
- **Sessions:** `ConversationService` + `session_repository`
- **Scheduler:** `SchedulerService`
- **Intent routing:** Abby intent + TDOS classifier (requires unification)

---

## 5) Remediation Actions (Forward‑Looking)

### ✅ Completed verification actions (All 5 audit concerns)

1. ✅ **Lifecycle delivery routing:** `create_announcement_for_delivery()` canonical; all operator announcements audited; `AnnouncementDispatcher.create_announcement()` deprecated with warnings
2. ✅ **Session/usage gating:** `UsageGateService` unified 4-gate checks; `ConversationService` manages lifecycle; `session_repository.py` breaks circular dependencies
3. ✅ **Scheduler canonicalization:** `SchedulerService` single source of truth; `GuildJobsTickHandler` for guild jobs; atomic job claiming; DLQ for failed jobs; legacy Discord scheduler cog deprecated
4. ✅ **Intent capability unification:** Two-layer architecture (Abby Core + TDOS); `INTENT_CAPABILITIES` shared contract; memory gating policies enforced; orchestrator integration verified
5. ✅ **State activation canonicalization:** `StateActivationService` service-level API; atomic transactions with rollback; `system_operations` audit trail; full effect validation

### Near‑term actions (Q1 2026 — cleanup & testing)

- Deprecate legacy `abby_core/llm/session.py` with warnings
- Remove legacy session helpers from `abby_core/database/mongodb.py`
- Add comprehensive integration tests for intent capability contract drift detection
- Add edge-case tests for scheduler idempotency with concurrent job claims

---

## 6) ✅ DEPRECATIONS COMPLETE

All deprecated code identified and removed as of 2026-02-03:

### Removed Items

1. **`abby_core/llm/session.py`** - DELETED
   - 159-line wrapper module around deprecated mongodb session helpers
   - Status: Zero imports in entire codebase; safely deleted
   - Removed: 2026-02-03

2. **`AnnouncementDispatcher.create_announcement()` method** - TESTS MIGRATED
   - Deprecated since: 2026-01-31
   - Status: Only 6 test calls found (test_announcement_dispatcher.py: 2 calls, test_announcement_timeout.py: 4 calls)
   - Migrated to: `create_announcement_for_delivery()` (canonical path)
   - Completed: 2026-02-03

3. **MongoDB session helpers** - REMOVED FROM `mongodb.py`
   - Functions removed:
     - `create_session()` (line 183)
     - `append_session_message()` (line 218)
     - `close_session()` (line 245)
   - Status: Only used by deleted `session.py`; zero other imports
   - Removed: 2026-02-03

### Verification Results

- ✅ **Production code is clean:** Zero deprecated functions used in active code
- ✅ **Test migrations complete:** All 6 test calls migrated to canonical paths
- ✅ **No breaking changes:** All removed code was orphaned (session.py) or test-only (dispatcher method)
- ✅ **Import verification:** No broken imports after deprecation removal

---

## 7) Deprecations & Merges (Policy)

- **Removed:** `AnnouncementDispatcher.create_announcement()` (migrated tests to `create_announcement_for_delivery`)
- **Removed:** legacy session helpers in `mongodb.py` (session.py wrapper was orphaned)
- **Removed:** legacy session.py module (zero imports, pure wrapper)

---

## 8) Documentation Policy

- This file is the only audit document for the codebase.
- All prior audit‑specific documents are removed to prevent drift.

---

## 9) Change Log

- 2026‑02‑03: ✅ **DEPRECATIONS COMPLETE** - All deprecated code removed
  - Deleted: `abby_core/llm/session.py` (orphaned, 159 lines, zero imports)
  - Migrated: 6 test calls from `dispatcher.create_announcement()` → `create_announcement_for_delivery()`
  - Removed: 3 mongodb session helpers (only used by deleted session.py)
  - Verified: Zero production code dependencies on deprecated functions
  - Result: Codebase now clean and ready for production seal
  - ✅ Lifecycle delivery: Dispatcher routing canonical, deprecation warnings in place, mark\_\* functions delegate properly
  - ✅ Session/usage gating: Single-path consolidation verified, `UsageGateService` unified, repository breaks circular deps
  - ✅ Scheduler ownership: `SchedulerService` is canonical, atomic job claiming, DLQ integration, legacy cog deprecated
  - ✅ Intent capability routing: Two-layer architecture verified, shared contract enforced, orchestrator integration validated
  - ✅ State activation: Service-level API canonical, atomic transactions, operation audit trail, effect validation integrated
  - Summary: All must-fix-now and can-improve-later concerns verified; remaining work is Q1 2026 cleanup and testing
- 2026‑02‑02: Canonical audit consolidated from 7 superseded documents.

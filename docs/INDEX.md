# Documentation Index

**Last Updated:** February 3, 2026  
**Status:** Canonical structure (20-50 year horizon)

This index is the permanent entry point for ABBY's documentation. Keep it accurate and current.

---

## ⭐ Start Here (Read First)

1. **[overview/ABBY_CANONICAL.md](overview/ABBY_CANONICAL.md)** — Single-page platform overview. Read this before anything else.
2. **[overview/PLATFORM_OVERVIEW.md](overview/PLATFORM_OVERVIEW.md)** — Why ABBY exists, what problems it solves
3. **[architecture/SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md)** — 10,000-foot view of subsystems
4. **[lifecycle/STATE_MAP.md](lifecycle/STATE_MAP.md)** — State ownership registry
5. **[operations/OPERATOR_GUIDE.md](operations/OPERATOR_GUIDE.md)** — Day-to-day operations

---

## 📁 By Domain (Navigation)

### Overview — Platform Identity

> **Purpose:** What ABBY is, why it exists, high-level intent  
> **Stability:** 50 years — core "why"

- **[overview/ABBY_CANONICAL.md](overview/ABBY_CANONICAL.md)** ⭐ — Executive platform overview
- **[overview/PLATFORM_OVERVIEW.md](overview/PLATFORM_OVERVIEW.md)** — Product and platform intent

### Architecture — System Design & Contracts

> **Purpose:** Subsystem boundaries, contracts, invariants  
> **Stability:** 20-50 years

- **[architecture/SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md)** — Subsystem topology & data flow
- **[architecture/INTENT_ARCHITECTURE.md](architecture/INTENT_ARCHITECTURE.md)** — Two-layer intent classification
- **[architecture/ADAPTER_CONTRACTS.md](architecture/ADAPTER_CONTRACTS.md)** — Platform-agnostic interfaces
- **[architecture/SERVICE_CONTRACTS.md](architecture/SERVICE_CONTRACTS.md)** — Service boundaries & guarantees
- **[architecture/CONCURRENCY_MODEL.md](architecture/CONCURRENCY_MODEL.md)** — Atomicity & parallelism model
- **[architecture/HEARTBEAT_ARCHITECTURE.md](architecture/HEARTBEAT_ARCHITECTURE.md)** — Health monitoring
- **[architecture/COOLDOWN_ARCHITECTURE.md](architecture/COOLDOWN_ARCHITECTURE.md)** — Rate limiting system
- **[architecture/TDOS_INTELLIGENCE.md](architecture/TDOS_INTELLIGENCE.md)** — TDOS orchestrator

### Lifecycle & State — State Models & Transitions

> **Purpose:** State machines, ownership, transitions  
> **Stability:** 20-50 years

- **[lifecycle/STATE_MAP.md](lifecycle/STATE_MAP.md)** — Index & ownership registry
- **[lifecycle/PLATFORM_STATE.md](lifecycle/PLATFORM_STATE.md)** — Seasons, events, modes (canonical global state)
- **[lifecycle/LIFECYCLE_STATE.md](lifecycle/LIFECYCLE_STATE.md)** — Announcements & content delivery
- **[lifecycle/GAMEPLAY_STATE.md](lifecycle/GAMEPLAY_STATE.md)** — Event-bound gameplay
- **[lifecycle/CONFIGURATION_STATE.md](lifecycle/CONFIGURATION_STATE.md)** — Guild/user preferences
- **[lifecycle/GENERATION_STATE.md](lifecycle/GENERATION_STATE.md)** — Ephemeral request context
- **[lifecycle/STATE_INVARIANTS.md](lifecycle/STATE_INVARIANTS.md)** — Non‑negotiable state rules
- **[lifecycle/CONVERSATION_FSM.md](lifecycle/CONVERSATION_FSM.md)** — Session state machine

### Data — Persistence & Schema

> **Purpose:** Database layer, schemas, collections  
> **Stability:** 20 years (schemas evolve)

- **[data/README.md](data/README.md)** — Data layer entry point
- **[data/ARCHITECTURE.md](data/ARCHITECTURE.md)** — Three-tier data access pattern
- **[data/BEST_PRACTICES.md](data/BEST_PRACTICES.md)** — Naming, error handling, indexing
- **[data/COLLECTION_INVENTORY.md](data/COLLECTION_INVENTORY.md)** — All collections & ownership
- **[data/COLLECTION_MODULE_TEMPLATE.md](data/COLLECTION_MODULE_TEMPLATE.md)** — Template for new collections
- **[data/UNIVERSAL_USER_SCHEMA.md](data/UNIVERSAL_USER_SCHEMA.md)** — Multi-platform user model
- **[data/UNIVERSAL_USER_PROFILE.md](data/UNIVERSAL_USER_PROFILE.md)** — User lifecycle
- **[data/DATA_RETENTION_POLICY.md](data/DATA_RETENTION_POLICY.md)** — Retention & archival policy

### Runtime — Execution Model

> **Purpose:** Scheduling, generation flow, job execution  
> **Stability:** 10-20 years (implementation changes)

- **[runtime/SCHEDULER_ARCHITECTURE.md](runtime/SCHEDULER_ARCHITECTURE.md)** — Canonical scheduler (SchedulerService)
- **[runtime/GENERATION_PIPELINE.md](runtime/GENERATION_PIPELINE.md)** — Intent → LLM → delivery flow
- **[runtime/SCHEDULER_JOBS_CATALOG.md](runtime/SCHEDULER_JOBS_CATALOG.md)** — All background jobs with ownership

### Operations — Day-to-Day Procedures

> **Purpose:** Configuration, security, incidents, observability  
> **Stability:** 5-10 years (tooling evolves)

- **[operations/OPERATOR_GUIDE.md](operations/OPERATOR_GUIDE.md)** — Power & safety checklist
- **[operations/STARTUP_OPERATIONS_GUIDE.md](operations/STARTUP_OPERATIONS_GUIDE.md)** — Startup procedures
- **[operations/CONFIGURATION_REFERENCE.md](operations/CONFIGURATION_REFERENCE.md)** — All 90+ env vars
- **[operations/SECURITY_GUIDE.md](operations/SECURITY_GUIDE.md)** — Tokens, encryption, rotation
- **[operations/OBSERVABILITY_RUNBOOK.md](operations/OBSERVABILITY_RUNBOOK.md)** — Logs, metrics, DLQ
- **[operations/INCIDENT_RESPONSE.md](operations/INCIDENT_RESPONSE.md)** — Triage & recovery
- **[operations/CAPACITY_PLANNING.md](operations/CAPACITY_PLANNING.md)** — Scale thresholds & baselines
- **[operations/DEPLOYMENT_STRATEGY.md](operations/DEPLOYMENT_STRATEGY.md)** — Release & rollback plan
- **[operations/RAG_GUIDE.md](operations/RAG_GUIDE.md)** — Vector store lifecycle
- **[operations/TEST_STRATEGY.md](operations/TEST_STRATEGY.md)** — Testing approach
- **[operations/QDRANT_MIGRATION_GUIDE.md](operations/QDRANT_MIGRATION_GUIDE.md)** — Qdrant migration
- **[operations/USER_ID_GENERATION_GUIDE.md](operations/USER_ID_GENERATION_GUIDE.md)** — User ID strategy

### Distribution — Release & Deployment

> **Purpose:** Release model, packaging, deployment  
> **Stability:** 5-10 years

- **[distribution/README.md](distribution/README.md)** — Distribution entry point
- **[distribution/DISTRIBUTION_RELEASES_ARCHITECTURE.md](distribution/DISTRIBUTION_RELEASES_ARCHITECTURE.md)** — Release model
- **[distribution/DISTRIBUTION_IMPLEMENTATION_GUIDE.md](distribution/DISTRIBUTION_IMPLEMENTATION_GUIDE.md)** — Implementation flow
- **[distribution/DISTRIBUTION_RELEASE_INDEX.md](distribution/DISTRIBUTION_RELEASE_INDEX.md)** — Historical releases

### Persona — Character Definition

> **Purpose:** Who Abby is (tone, voice, character)  
> **Stability:** 50 years

- **[persona/PERSONA_CANON_SPEC.md](persona/PERSONA_CANON_SPEC.md)** — Character definition

### Reference — Supporting Materials

> **Purpose:** Consolidation notes, historical artifacts  
> **Stability:** 2-5 years

- **[reference/CONSOLIDATION_COMPLETE.md](reference/CONSOLIDATION_COMPLETE.md)** — January 2026 consolidation
- **[reference/CONSOLIDATION_SUMMARY.md](reference/CONSOLIDATION_SUMMARY.md)** — Pre-consolidation inventory
- **[reference/STARTUP_LOGGING.md](reference/STARTUP_LOGGING.md)** — Logging format reference
- **[reference/CANONICAL_STATE_MAP.md](reference/CANONICAL_STATE_MAP.md)** — Merged into lifecycle/STATE_MAP.md
- **[reference/CHANGES_QUICK_REFERENCE.md](reference/CHANGES_QUICK_REFERENCE.md)** — Recent changes
- **[reference/COMPLETION_CHECKLIST.md](reference/COMPLETION_CHECKLIST.md)** — Project checklist
- **[reference/PHASE_1_IMPLEMENTATION.md](reference/PHASE_1_IMPLEMENTATION.md)** — Phase 1 summary
- **[reference/COOLDOWN_ARCHITECTURE_VALIDATION.md](reference/COOLDOWN_ARCHITECTURE_VALIDATION.md)** — Validation artifact
- **[reference/COOLDOWN_IMPLEMENTATION_SUMMARY.md](reference/COOLDOWN_IMPLEMENTATION_SUMMARY.md)** — Implementation summary

### Archive — Historical Documents

> **Purpose:** Superseded docs, point-in-time fixes  
> **Stability:** Permanent archive

- **[archive/README.md](archive/README.md)** — Archive purpose and policy
- **[archive/OLD_AUDIT.md](archive/OLD_AUDIT.md)** — Superseded audit
- **[archive/BUG_FIXES/](archive/BUG_FIXES/)** — Point-in-time fixes

---

## 🔍 Quick Lookup (By Task)

### "I need to understand platform architecture"

- Start: [overview/ABBY_CANONICAL.md](overview/ABBY_CANONICAL.md)
- Deep dive: [architecture/SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md)
- State model: [lifecycle/STATE_MAP.md](lifecycle/STATE_MAP.md)

### "I need to operate/configure the system"

- Day-to-day: [operations/OPERATOR_GUIDE.md](operations/OPERATOR_GUIDE.md)
- All env vars: [operations/CONFIGURATION_REFERENCE.md](operations/CONFIGURATION_REFERENCE.md)
- Security: [operations/SECURITY_GUIDE.md](operations/SECURITY_GUIDE.md)
- Incidents: [operations/INCIDENT_RESPONSE.md](operations/INCIDENT_RESPONSE.md)

### "I need to understand state management"

- Ownership: [lifecycle/STATE_MAP.md](lifecycle/STATE_MAP.md)
- Platform state: [lifecycle/PLATFORM_STATE.md](lifecycle/PLATFORM_STATE.md)
- Announcements: [lifecycle/LIFECYCLE_STATE.md](lifecycle/LIFECYCLE_STATE.md)
- Sessions: [lifecycle/CONVERSATION_FSM.md](lifecycle/CONVERSATION_FSM.md)

### "I need to work with data/database"

- Entry: [data/README.md](data/README.md)
- Architecture: [data/ARCHITECTURE.md](data/ARCHITECTURE.md)
- Best practices: [data/BEST_PRACTICES.md](data/BEST_PRACTICES.md)
- All collections: [data/COLLECTION_INVENTORY.md](data/COLLECTION_INVENTORY.md)

### "I need to understand runtime execution"

- Scheduler: [runtime/SCHEDULER_ARCHITECTURE.md](runtime/SCHEDULER_ARCHITECTURE.md)
- Generation: [runtime/GENERATION_PIPELINE.md](runtime/GENERATION_PIPELINE.md)
- All jobs: [runtime/SCHEDULER_JOBS_CATALOG.md](runtime/SCHEDULER_JOBS_CATALOG.md)

---

## 📚 Essential Reading (First Week)

For new engineers, read these in order:

1. **[overview/ABBY_CANONICAL.md](overview/ABBY_CANONICAL.md)** (10 min) — Platform overview
2. **[overview/PLATFORM_OVERVIEW.md](overview/PLATFORM_OVERVIEW.md)** (5 min) — Why ABBY exists
3. **[architecture/SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md)** (15 min) — System topology
4. **[lifecycle/STATE_MAP.md](lifecycle/STATE_MAP.md)** (10 min) — State ownership
5. **[operations/OPERATOR_GUIDE.md](operations/OPERATOR_GUIDE.md)** (15 min) — Operations

**Total:** ~1 hour for platform understanding

---

## 🔄 Documentation Consolidation History

### February 3, 2026: Major Restructuring

✅ **Canonical structure implemented** — 20-50 year horizon design  
✅ **Folders reorganized:**

- `states/` → `lifecycle/` (clarity)
- `database/` → `data/` (broader scope)
- `guides/` → `operations/` (semantic clarity)
- New: `overview/`, `runtime/`, `reference/`, `archive/`, `evolution/`

✅ **Documents moved:**

- 60+ documents reorganized
- 25% reduction in active documents
- Zero redundancy after consolidation

✅ **New canonical overview:** [overview/ABBY_CANONICAL.md](overview/ABBY_CANONICAL.md)

✅ **Audit completed:** See root-level DOCUMENTATION\_\*.md files for full details

**Guiding principle:** All documentation optimized for 50-year architectural evolution without major rewrites.

### January 31, 2026: Initial Consolidation

✅ Database docs consolidated  
✅ State domain docs streamlined  
✅ 8 missing operational docs created  
✅ Architecture overlap reduced

---

## 📝 Update Expectations

### When to Update This Index

- Adding a new document
- Removing or archiving a document
- Renaming or moving a document
- Changing folder structure

### Review Schedule

- **Weekly:** Check for new docs requiring indexing
- **Monthly:** Verify all links resolve
- **Quarterly:** Review folder organization
- **Annually:** Full documentation audit

---

## 🆘 Emergency Quick Links

- **System down:** [operations/INCIDENT_RESPONSE.md](operations/INCIDENT_RESPONSE.md)
- **State activation failed:** [lifecycle/PLATFORM_STATE.md](lifecycle/PLATFORM_STATE.md)
- **Scheduler issues:** [runtime/SCHEDULER_ARCHITECTURE.md](runtime/SCHEDULER_ARCHITECTURE.md)
- **Database slow:** [data/BEST_PRACTICES.md](data/BEST_PRACTICES.md)
- **Security incident:** [operations/SECURITY_GUIDE.md](operations/SECURITY_GUIDE.md)

---

## 📞 Ownership

| Domain                 | Owner           |
| ---------------------- | --------------- |
| Overview, Architecture | Platform Team   |
| Lifecycle & State      | Platform Team   |
| Data                   | Data Team       |
| Runtime                | Platform Team   |
| Operations             | Operations Team |
| Distribution           | DevOps Team     |
| Persona                | Creative Team   |

**Documentation Maintainer:** Principal Software Architect  
**Last Major Restructure:** February 3, 2026  
**Next Review:** March 2026

---

**This index is the canonical entry point. All documentation navigation starts here.**

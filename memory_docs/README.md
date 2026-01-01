# Memory System Documentation

**Status**: Production Ready (v1.0)  
**TDOS Portable**: Yes — designed for kernel integration  
**Last Updated**: December 31, 2025

---

## Overview

The Memory System is a typed, deterministic framework for extracting, storing, and retrieving subject-scoped relational intelligence. It separates raw interaction data from validated facts, enabling safe reuse across agents, domains, and TDOS pipelines.

**Key Design Principles**:
- ✅ Memory is append-only with decay (never deleted, only expired)
- ✅ Memory is typed (USER_FACT | USER_PATTERN | SHARED_NARRATIVE)
- ✅ Memory is subject-scoped (no cross-subject leakage)
- ✅ Memory is never authoritative (advisory, not deterministic)
- ✅ Memory is never executable (informational only)

---

## Quick Navigation

1. **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Complete system design, layers, and data flow
2. **[MEMORY_CONTRACT.md](./MEMORY_CONTRACT.md)** — Formal guarantees, invariants, and safety rules
3. **[MEMORY_ENVELOPE.md](./MEMORY_ENVELOPE.md)** — Envelope pattern, structure, and LLM formatting
4. **[EXTRACTION_RULES.md](./EXTRACTION_RULES.md)** — Fact extraction, typing, and validation
5. **[INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md)** — How to use this system in your agent/domain
6. **[DATA_MODEL.md](./DATA_MODEL.md)** — Complete schema, types, and storage structures
7. **[TDOS_MAPPING.md](./TDOS_MAPPING.md)** — Alignment with TDOS kernel concepts (subjects, tenants, ledger)

---

## System Architecture (High Level)

```
[Raw Interaction]
  ↓ chat logs, summaries
[Extraction Layer]
  ↓ LLM-powered fact/pattern extraction + validation
[Memory Types]
  ├─ USER_FACT (grounded, high-confidence, slow decay)
  ├─ USER_PATTERN (aggregated, confidence-gated, medium decay)
  └─ SHARED_NARRATIVE (warmth/context, never authoritative, fast decay)
[Memory Envelope]
  ↓ subject-scoped, contextual packaging for LLM consumption
[Storage]
  └─ MongoDB (subject_id, typed, append-only with expiry)
```

---

## Use Cases

**Abby (Discord Bot)**
- Store user preferences, hobbies, facts
- Adapt response style per-user
- Maintain continuity across sessions

**Future Clerk/Scribe Agents**
- Extract and store client meeting notes
- Track project context across interactions
- Enable handoff between agents

**TDOS Integration**
- Subject-scoped memory for kernel agents
- Audit trail via event log (immutable)
- Tenant isolation guarantees

**Self (Creator)**
- Personal subject profile
- Interaction history with agents
- Long-term context for creative work

---

## Getting Started

### Minimal Setup (No Config Required)

```python
from memory_extraction import extract_facts_from_summary
from memory_envelope import get_memory_envelope, format_envelope_for_llm

# 1. Extract facts from conversation summary
facts = extract_facts_from_summary(
    summary="User mentioned they love fettuccini and work on FL Studio music",
    user_id="USER:246030816692404234"
)

# 2. Load user's memory envelope
envelope = get_memory_envelope(
    user_id="USER:246030816692404234",
    guild_id="TENANT:BreezeCrew"
)

# 3. Format for LLM context
context = format_envelope_for_llm(envelope, max_facts=5)

# 4. Use in your prompt
system_prompt = f"You know: {context}\n\nRespond naturally."
```

---

## Key Concepts

### Memory Envelope Pattern
The primary pattern for packaging subject intelligence. Includes:
- Identity (subject, tenant)
- Facts (typed, scored)
- Patterns (aggregated behaviors)
- Recent context (last session)
- Constraints (opt-outs, privacy)

→ See [MEMORY_ENVELOPE.md](./MEMORY_ENVELOPE.md)

### Extraction Pipeline
1. **Summarization** (external) → narrative text
2. **Extraction** (LLM) → candidate facts
3. **Validation** (rule-based) → ground against summary
4. **Typing** (deterministic) → USER_FACT | USER_PATTERN | SHARED_NARRATIVE
5. **Storage** (MongoDB) → subject-scoped, append-only

→ See [EXTRACTION_RULES.md](./EXTRACTION_RULES.md)

### Confidence & Decay
- **USER_FACT** — confidence 0.8+, slow decay (30 days)
- **USER_PATTERN** — confidence 0.75+, medium decay (14 days)
- **SHARED_NARRATIVE** — confidence 0.6+, fast decay (7 days)

Decay is applied per-query; expired facts remain in storage but are not loaded into envelopes.

→ See [MEMORY_CONTRACT.md](./MEMORY_CONTRACT.md)

---

## Self-Contained Design

This system requires **zero hard-coded paths or config files**:

- MongoDB client passed as parameter (or singleton per domain)
- Subject IDs follow canonical format (SUBJECT_TYPE:VALUE)
- Tenant IDs follow canonical format (TENANT:NAME)
- No external config lookups
- All defaults are sensible and overridable

```python
# Example: self-contained usage
client = MongoClient(os.getenv("MONGODB_URI"))  # your choice
memory_system = MemorySystem(mongo_client=client)
facts = memory_system.extract_facts(summary, subject_id, tenant_id)
```

→ See [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md)

---

## TDOS Alignment

This system maps cleanly to TDOS kernel concepts:

| Memory Concept | TDOS Analog |
|---|---|
| subject_id | SUBJECT:TYPE:VALUE |
| tenant_id | TENANT:NAME |
| memory_envelope | Context envelope for job execution |
| extraction event | Audit log entry |
| decay/expiry | TTL on ledger artifacts |
| append-only | Ledger immutability principle |
| confidence | Determinism/trust scoring |

→ See [TDOS_MAPPING.md](./TDOS_MAPPING.md)

---

## Safety Guarantees

✅ **Memory Write Authority** — Only designated components may write memory
✅ **No Cross-Subject Leakage** — Subject IDs enforced at storage layer
✅ **No Silent Mutations** — High-confidence decisions logged, low-confidence gated
✅ **No Hallucination** — Facts validated against original summary
✅ **No Authoritative Use** — Memory marked "advisory" in all contexts
✅ **No Permission Leakage** — Warmth/narrative never influences access control

→ See [MEMORY_CONTRACT.md](./MEMORY_CONTRACT.md)

---

## Documentation Structure

```
memory_docs/
├── README.md (this file)
├── ARCHITECTURE.md (system design)
├── MEMORY_CONTRACT.md (guarantees & rules)
├── MEMORY_ENVELOPE.md (pattern details)
├── EXTRACTION_RULES.md (LLM extraction logic)
├── DATA_MODEL.md (schema & types)
├── INTEGRATION_GUIDE.md (how to use)
└── TDOS_MAPPING.md (kernel alignment)
```

Each document is self-contained and can be read independently.

---

## Quick Reference: Memory Lifecycle

```
1. RAW INTERACTION
   └─ Chat logs, user messages

2. SUMMARIZATION (external system)
   └─ Narrative summary of session

3. EXTRACTION
   ├─ LLM extracts candidate facts
   └─ Rule-based validation against summary

4. TYPING & CONFIDENCE
   ├─ USER_FACT (high confidence, explicit)
   ├─ USER_PATTERN (aggregated, gated)
   └─ SHARED_NARRATIVE (warmth, non-authoritative)

5. STORAGE
   └─ MongoDB (subject_id, typed, append-only)

6. LOADING (per-query)
   ├─ Fetch latest entries for subject
   ├─ Filter by confidence threshold
   ├─ Apply decay/expiry rules
   └─ Package into memory envelope

7. CONSUMPTION
   ├─ Format for LLM context
   ├─ Use in system prompt or conversation
   └─ Never treat as authoritative truth
```

---

## For TDOS Integration

This system is ready to become a TDOS module. When integrating:

1. Use subject/tenant IDs from TDOS kernel
2. Emit extraction events to TDOS event log
3. Store memory in TDOS-managed ledger/registries
4. Enforce tenant isolation via kernel access control
5. Treat memory as advisory context, not deterministic state

→ See [TDOS_MAPPING.md](./TDOS_MAPPING.md) for detailed mapping

---

## Status & Versioning

**Current Version**: 1.0  
**Stability**: Production  
**TDOS Compatibility**: v1.4+  

Breaking changes will be documented and versioned. Additive changes backward-compatible.

For questions or integration discussions, refer to the appropriate guide above.

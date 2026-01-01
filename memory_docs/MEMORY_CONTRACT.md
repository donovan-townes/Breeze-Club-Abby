# Memory Contract & Safety Guarantees

**Version**: 1.0  
**Critical**: This document defines the binding contract for memory system behavior.

---

## Core Invariants

These are non-negotiable rules that must be enforced at all times.

### INV-001: Memory is Append-Only with Decay

**Rule**: Facts are never deleted or modified; they expire via decay.

**Enforcement**:
- Insert-only operations (no UPDATE on fact content)
- Decay applied via `active: false` flag, not deletion
- Expired facts remain in MongoDB (immutable audit trail)

**Violation**: Updating fact text or confidence retroactively
**Safe**: Adding new fact with different confidence, marking old fact inactive

### INV-002: Memory is Typed

**Rule**: Every memory entry has exactly one type: USER_FACT | USER_PATTERN | SHARED_NARRATIVE

**Enforcement**:
- Type checked at insertion (MongoDB schema validation)
- Type immutable after creation
- Different decay/confidence rules per type

**Violation**: Trying to reclassify a fact from FACT to PATTERN
**Safe**: Extracting new fact with PATTERN type if evidence supports it

### INV-003: Memory is Subject-Scoped

**Rule**: A memory entry belongs to exactly one subject; no cross-subject leakage.

**Enforcement**:
- subject_id immutable at creation
- Query always includes subject_id + tenant_id filter
- MongoDB unique index: (subject_id, tenant_id, memory_id)

**Violation**: Using memory from USER:Alice when context is USER:Bob
**Safe**: One user per envelope, clear subject labeling throughout

### INV-004: Memory is Never Authoritative

**Rule**: Memory is advisory/contextual; never used for access control, permission, or deterministic logic.

**Enforcement**:
- Design review: memory never gates features
- Logging check: "advisory" label in all consumption points
- Code review: no conditional logic based on memory confidence alone

**Violation**: "User is advanced → give them power-user features" based on learned_level pattern
**Safe**: "User prefers detailed explanations → tailor response style" based on pattern

### INV-005: Memory is Never Executable

**Rule**: Memory cannot trigger actions; it can only inform decisions.

**Enforcement**:
- Memory marked read-only at consumption point
- No memory→action pipeline (only memory→context→decision)
- Agent/domain logic responsible for final decisions

**Violation**: Pattern says "user loves alerts" → system auto-enables alerts
**Safe**: Pattern says "user loves alerts" → offer alerts more prominently in UI

### INV-006: Warmth Never Leaks into Power

**Rule**: SHARED_NARRATIVE facts never influence permissions, pricing, moderation, or escalation.

**Enforcement**:
- SHARED_NARRATIVE filtered out before permission checks
- Audit log includes "rejected warmth-based logic" if attempted
- Code review: warmth-only facts in separate variable/scope

**Violation**: "User shared a cute memory about debugging late → trust them more on platform moderation"
**Safe**: "User shared a cute memory → use in greeting for continuity"

---

## Write Authority Guarantee

**Who can write memory**:

1. Discord Adapter (via extract_facts_from_summary → add_memorable_fact)
2. Manual Owner Override (SUBJECT:DONOVAN with admin role)
3. TDOS Kernel Agents (via standardized job execution + extraction)

**Who cannot**:

- Direct user input (not validated)
- External webhooks (no direct API)
- LLM output (unchecked)
- Other agents (without TDOS job context)
- Bot responses (never self-memorize)

**Enforcement**:
- add_memorable_fact() requires (user_id, guild_id, fact, source, confidence)
- source field tracks origin (llm_extraction, manual, etc.)
- All writes logged to event table with invoker_subject_id

---

## Confidence Gating

**Rule**: Confidence thresholds gate application; low-confidence updates require confirmation.

| Confidence Range | Action |
|---|---|
| 0.90–1.0 | Auto-apply, use in responses |
| 0.80–0.89 | Auto-apply, use in responses |
| 0.75–0.79 | Log as proposal only, do NOT apply automatically |
| 0.60–0.74 | Narrative/warmth only, do not apply updates |
| < 0.60 | Discard entirely |

**Example: Pattern confidence 0.75**
```python
if confidence >= 0.80:
    apply_pattern_updates(user_id, updates)  # Auto
    logger.info(f"Applied pattern updates (conf: {confidence:.2f})")
else:
    logger.warning(f"Low-confidence pattern (conf: {confidence:.2f})")
    logger.warning(f"Proposed updates: {updates}")
    logger.warning(f"(User interactions can reinforce these patterns)")
    # Do NOT apply
```

**Enforcement**:
- Code review of all pattern application
- Metrics: track how many proposals vs. auto-applies
- Alert if low-confidence auto-applies occur (bug)

---

## No Hallucination Guarantee

**Rule**: Every extracted fact is grounded in the original conversation summary.

**Validation Process**:
1. LLM extracts candidate fact
2. validate_fact_against_summary() checks if fact appears in summary
3. Fact must match summary text with ≥ 80% semantic similarity
4. If validation fails, fact is discarded (not forced)

**Example Validation**:
```python
summary = "User mentioned they love fettuccini and work on FL Studio"

candidate = "User is an expert musician"
# ❌ REJECTED: "expert" not supported by summary
# summary says "work on", not "expert at"

candidate = "User loves fettuccini"
# ✅ ACCEPTED: "loves fettuccini" appears verbatim in summary

candidate = "User enjoys Italian food"
# ✅ ACCEPTED: "loves fettuccini" → "enjoys Italian food" (semantic match)
```

**Enforcement**:
- All facts run through validate_fact_against_summary() before insertion
- Invalid facts logged with reason (for debugging)
- LLM prompt explicitly forbids extrapolation

---

## No Silent Mutation Guarantee

**Rule**: High-confidence updates applied automatically; low-confidence updates logged & gated.

**Silent Updates** (confidence ≥ 0.80):
- Applied without confirmation
- Logged as INFO level
- Safe because high confidence

**Gated Updates** (0.75 ≤ confidence < 0.80):
- Logged as WARNING
- Proposal stored but not applied
- Awaits user confirmation or pattern reinforcement

**Rejected Updates** (confidence < 0.75):
- Logged as DEBUG
- Not stored
- No side effects

**Example Log Output**:
```
[HIGH] Applied pattern updates (conf: 0.85): ['domains', 'learning_level']
[GATE] Low-confidence pattern (conf: 0.78): proposed ['communication_style']
[GATE] (User interactions can reinforce these patterns)
[SKIP] Insufficient confidence (conf: 0.62): discarded pattern
```

---

## Privacy & Opt-Out Contract

**Constraint Model**: Memory envelope includes `constraints` field (future).

**Current Constraints** (planned):
```python
constraints = {
    "memory_enabled": True,  # User can opt out entirely
    "learn_patterns": True,  # User can opt out of pattern learning
    "share_with": [/* list of agent types */],  # Selective sharing
    "anonymize_dates": False,  # Blur timestamps if privacy concern
    "delete_after_days": None,  # Auto-delete after N days (GDPR)
}
```

**Rule**: If user opts out, memory is not learned; existing memory is excluded from envelopes.

**Enforcement**:
- Constraints checked before add_memorable_fact() call
- Opt-out logged as event (audit trail)
- GDPR-compliant deletion (marked inactive then archived)

---

## Tenant Isolation Guarantee

**Rule**: No memory from TENANT:A leaks to TENANT:B.

**Enforcement**:
1. **Query Time**: All queries include `tenant_id` filter
   ```python
   db.collection.find_one({
       "subject_id": subject_id,
       "tenant_id": tenant_id,  # ← Mandatory
       "type": "USER_FACT"
   })
   ```

2. **Index Level**: Compound index (subject_id, tenant_id, memory_id)
3. **Application Level**: envelope.subject_id validation against request tenant_id

**Violation Detection**:
- Audit log includes all cross-tenant queries (should be zero)
- Alert if > 0 cross-tenant reads detected

---

## Decay & Expiry Rules

**Decay does NOT delete; it filters**. Expired facts remain in MongoDB.

### Per-Type Decay Windows

| Type | Window | Active Envelope? | Storage |
|------|--------|---|---|
| USER_FACT | 30 days | Yes if age < 30d, else No | Kept forever |
| USER_PATTERN | 14 days | Yes if age < 14d, else No | Kept forever |
| SHARED_NARRATIVE | 7 days | Yes if age < 7d, else No | Kept forever |

**Expiry Calculation**:
```python
now = datetime.utcnow()
age_days = (now - fact.added_at).days

is_expired = {
    "USER_FACT": age_days > 30,
    "USER_PATTERN": age_days > 14,
    "SHARED_NARRATIVE": age_days > 7,
}
```

**Archive Policy** (optional, no code required):
- After 90 days, expired facts can be archived to cold storage
- Archive is optional; keeping forever is acceptable
- No deletion without explicit user request (GDPR)

---

## Consistency Model

**Consistency Level**: Eventual consistency (MongoDB majority write concern)

**Guarantees**:
- Write acknowledged when majority of replicas confirm
- Read from primary always gets latest writes
- Cache TTL (900s) acceptable for advisory use

**Tradeoff**:
- New facts take up to 15 minutes to appear in cached envelope
- Acceptable: new facts are low-priority context
- Critical decision: refresh envelope manually before using

**Example**:
```python
# First call: cache miss, reads DB, returns 1 fact, caches for 900s
envelope1 = get_memory_envelope(user_id)  # has 1 fact

# Add new fact to DB
add_memorable_fact(user_id, "loves coffee", ...)

# Within 15 minutes, next call still returns cached envelope (1 fact)
envelope2 = get_memory_envelope(user_id)  # still has 1 fact (cached)

# After 900s (15 min), cache expires
envelope3 = get_memory_envelope(user_id)  # refreshes, now has 2 facts
```

**For critical scenarios**:
```python
# Force refresh: bypass cache
envelope = get_memory_envelope(user_id, skip_cache=True)  # always fresh
```

---

## Audit Trail Contract

**Every memory write produces an event**:

```python
{
    "event_id": str,
    "event_type": "MEMORY_FACT_ADDED",
    "timestamp": datetime.utcnow(),
    "subject_id": subject_id,
    "tenant_id": tenant_id,
    "invoker_subject_id": invoker_id,  # Who added this
    
    "memory_id": fact_id,
    "memory_type": "USER_FACT",
    "fact_content": fact_text,
    "confidence": confidence_score,
    
    "source": "llm_extraction",  # Where fact came from
    "validation_status": "passed",  # Did it pass validate_fact_against_summary?
    "metadata": {"reason": "...", "summary_excerpt": "..."}
}
```

**Event Storage**:
- Append-only MongoDB collection: `memory_events`
- Indexed by (tenant_id, subject_id, timestamp)
- Immutable (no deletes allowed)
- Synced to TDOS event ledger (future)

**Retention**: No automatic deletion; events kept forever for audit.

---

## Testing & Validation

**Test Categories**:

1. **Invariant Tests**: Confirm INV-001 through INV-006 hold under load
2. **Isolation Tests**: Verify no cross-tenant leakage
3. **Decay Tests**: Confirm facts expire at correct times
4. **Validation Tests**: Ensure no hallucinated facts pass
5. **Permission Tests**: Confirm memory never gates access
6. **Stress Tests**: High-frequency reads/writes maintain consistency

**Safety Checklist Before Production**:
- [ ] All invariants unit-tested
- [ ] Isolation tests pass (100+ concurrent users)
- [ ] Decay tests confirm TTL accuracy
- [ ] Validation rejects 100% of hallucinated facts
- [ ] Code review: zero permission-gating on memory
- [ ] Audit log: zero cross-tenant reads
- [ ] Load test: 1000 reads/sec, 100 writes/sec stable

---

## Contract Violations & Remediation

**If INV-001 violated** (fact modified after creation):
- Immediate alert
- Stop accepting writes for affected fact
- Audit log incident
- Manual review required

**If INV-003 violated** (cross-tenant leakage):
- Immediate alert (CRITICAL)
- Kill connection
- Purge cache
- Full audit of affected queries

**If INV-004 violated** (memory used for permission):
- Log error with stack trace
- Reject the gating decision
- Alert operator
- Code review of offending section

**If validation fails** (hallucinated fact accepted):
- Log as CRITICAL
- Mark fact invalid (without deletion)
- Retrain LLM prompt
- Incident review

---

## Version History

| Version | Changes | Status |
|---------|---------|--------|
| 1.0 | Initial contract definition | Current |

This contract is stable and production-ready. Breaking changes require RFC + version bump.


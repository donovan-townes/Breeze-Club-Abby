# TDOS Kernel Integration: Memory System Mapping

**Version**: 1.0  
**Target**: TDOS Kernel v1.5+  
**Integration Type**: Deterministic memory as first-class kernel citizen  
**Status**: Ready for adoption

---

## Overview

The memory system is designed from the ground up to integrate seamlessly with TDOS kernel architecture. This document maps memory system concepts to TDOS kernel primitives.

**Core Alignment**:
- ✅ Deterministic (same input → same extraction)
- ✅ Provenance-aware (all writes audited)
- ✅ Immutable truth (append-only with decay)
- ✅ Subject-scoped (no cross-subject leakage)
- ✅ Tenant-isolated (query-level enforcement)
- ✅ Event-logged (all ops recorded)
- ✅ Kernel-portable (no hard-coded paths)

---

## Subject ID Mapping

### Memory System Format
```
subject_id: str = "USER:246030816692404234"
tenant_id: str = "TENANT:BreezeCrew"
```

### TDOS Kernel Format

**Mapping to TDOS Subject**:
```
TDOS Subject: {
    type: "USER",
    id: "246030816692404234",
    tenant: "BreezeCrew",
    region: "DISCORD"                    // Platform identifier
}

# In memory system:
memory.subject_id = "USER:246030816692404234"
memory.tenant_id = "TENANT:BreezeCrew"
```

**Query Enforcement**:
```python
# ✅ Correct: Subject + Tenant scoped
profile = db.discord_profiles.find_one({
    "user_id": "246030816692404234",
    "guild_id": "BreezeCrew"             # Tenant
})

# ❌ Wrong: Missing tenant scope
profile = db.discord_profiles.find_one({
    "user_id": "246030816692404234"     # Could cross tenants
})
```

---

## Job Context Integration

### TDOS Job Execution Flow

```
[TDOS Kernel]
    ↓
[Invoke Job: extract_facts]
    ├─ job_id: "job_abc123"
    ├─ subject: USER:246030816692404234
    ├─ tenant: TENANT:BreezeCrew
    ├─ input: {conversation_summary}
    └─ context: {session_id, invoker, ...}
    ↓
[Memory System]
    ├─ Check permissions (via job context)
    ├─ Extract facts (deterministic LLM call)
    ├─ Validate facts (grounded in summary)
    ├─ Log event to kernel ledger
    └─ Return: {facts_stored, event_ids}
    ↓
[TDOS Result]
    ├─ Status: SUCCESS
    ├─ Artifacts: {new_facts, event_log}
    └─ Next Job: refresh_envelope_cache
```

### Job Definition Example

```python
# TDOS Job: Extract facts from conversation
MEMORY_EXTRACTION_JOB = {
    "name": "extract_memorable_facts",
    "version": "1.0",
    "description": "Extract facts from conversation summary",
    
    "inputs": {
        "summary": str,                 # Conversation summary
        "subject_id": str,              # USER:123
        "tenant_id": str,               # TENANT:guild
    },
    
    "outputs": {
        "facts_extracted": List[dict],
        "facts_stored": int,
        "rejected_count": int,
        "event_ids": List[str],
    },
    
    "requires_permissions": [
        "memory:write:{subject_id}",    # Can write to this subject's memory
        "tenant:access:{tenant_id}",    # Can access this tenant
    ],
    
    "isolation": {
        "subject_scoped": True,         # Only affects one subject
        "tenant_scoped": True,          # Only affects one tenant
        "side_effects": "append_only",  # No deletions
    },
    
    "determinism": {
        "deterministic": True,          # Same input → same output
        "seed_reproducible": True,      # LLM with fixed seed
    }
}
```

---

## Event Ledger Mapping

### Memory Event → TDOS Ledger Entry

**Memory Event**:
```json
{
    "event_type": "MEMORY_ADDED",
    "timestamp": "2025-01-15T10:30:45.123Z",
    "subject_id": "USER:246030816692404234",
    "tenant_id": "TENANT:BreezeCrew",
    "invoker_subject_id": "CHATBOT:abby_v2.1",
    "operation": {
        "action": "add_fact",
        "memory_content": {
            "fact": "Loves fettuccini",
            "confidence": 0.85,
            "type": "USER_FACT"
        }
    },
    "result": {
        "success": true,
        "affected_documents": 1
    }
}
```

**Maps to TDOS Ledger Entry**:
```
TDOS Ledger Entry: {
    entry_id: "ledger_abc123def456",
    timestamp: 2025-01-15T10:30:45.123Z,
    
    # Subject & Tenant
    subject: USER:246030816692404234,
    tenant: TENANT:BreezeCrew,
    
    # Job Context
    job_id: "job_abc123",
    job_name: "extract_memorable_facts:v1.0",
    invoker: CHATBOT:abby_v2.1,
    
    # Operation
    operation: "MEMORY_ADDED",
    data: {
        memory_type: "USER_FACT",
        content: "Loves fettuccini",
        confidence: 0.85
    },
    
    # Result
    status: "SUCCESS",
    audit_trail: {
        changed_fields: ["memorable_facts"],
        before_state: {...},
        after_state: {...},
    },
    
    # Provenance
    signed_by: "CHATBOT:abby_v2.1",
    version: 1,
}
```

---

## Permission Model

### TDOS Capability Gating

**Memory Write Permissions**:
```python
MEMORY_PERMISSIONS = {
    "memory:read:{subject_id}": {
        "allows": ["get_memory_envelope", "get_facts"],
        "required_for": ["use_in_prompt"],
        "scoped_by": ["tenant_id"]
    },
    
    "memory:write:{subject_id}": {
        "allows": ["add_memorable_fact", "extract_facts"],
        "required_for": ["store_new_memory"],
        "scoped_by": ["tenant_id"],
        "gated_by": "job:extract_memorable_facts:v1.0"
    },
    
    "memory:decay:{subject_id}": {
        "allows": ["apply_confidence_decay"],
        "required_for": ["auto_expire_old_facts"],
        "scoped_by": ["tenant_id"],
        "gated_by": "system:decay_scheduler"
    },
    
    "tenant:access:{tenant_id}": {
        "allows": ["cross_subject_access_in_tenant"],
        "required_for": ["bulk_memory_analysis"],
        "scoped_by": ["tenant_id"]
    }
}
```

**Check Permissions** (before operation):
```python
def check_memory_permission(
    invoker: str,                      # "CHATBOT:abby_v2.1"
    action: str,                       # "add_fact"
    subject_id: str,                   # "USER:123"
    tenant_id: str,                    # "TENANT:guild"
    job_context: dict                  # From TDOS kernel
) -> bool:
    """Verify invoker has permission for action."""
    
    # Build required capability
    capability = f"memory:{action}:{subject_id}"
    
    # Check TDOS capability
    if not kernel.has_capability(invoker, capability, tenant=tenant_id):
        log_denial(invoker, action, subject_id, tenant_id)
        return False
    
    # Check job authorization
    if action == "add_fact":
        required_job = "extract_memorable_facts:v1.0"
        if job_context.get("job_name") != required_job:
            log_denial(invoker, action, job=job_context.get("job_name"))
            return False
    
    return True
```

---

## Determinism Contract

### LLM Extraction Determinism

**Problem**: LLMs are non-deterministic by default.

**Solution**: Fixed seed + temperature control.

```python
def extract_facts_deterministically(
    summary: str,
    subject_id: str,
    tenant_id: str,
    seed: int = 42                     # Fixed seed
) -> List[dict]:
    """Extract facts with reproducible results."""
    
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        temperature=0.3,                # Low temperature (more deterministic)
        seed=seed,                      # Fixed seed for reproducibility
        prompt=EXTRACTION_PROMPT.format(summary=summary),
    )
    
    facts = parse_extraction(response)
    
    # Audit: Record seed used
    log_event({
        "operation": "extract_facts",
        "subject_id": subject_id,
        "seed": seed,
        "facts_extracted": len(facts),
        "extraction_hash": hash(str(facts))
    })
    
    return facts
```

**Verification**: Same input + seed → Same facts extracted.

```python
# Run 1
facts_1 = extract_facts_deterministically(
    summary="User loves fettuccini",
    subject_id="USER:123",
    tenant_id="TENANT:guild",
    seed=42
)

# Run 2 (identical)
facts_2 = extract_facts_deterministically(
    summary="User loves fettuccini",
    subject_id="USER:123",
    tenant_id="TENANT:guild",
    seed=42
)

assert facts_1 == facts_2, "Extraction should be deterministic"
```

---

## Audit Trail Contract

### Complete Operation Tracing

**Every memory write must be logged**:

```python
async def add_memorable_fact_with_audit(
    subject_id: str,
    tenant_id: str,
    fact: str,
    fact_type: str,
    confidence: float,
    job_context: dict,               # From TDOS kernel
    storage: MemoryStorage
) -> dict:
    """Add fact with complete audit trail."""
    
    # Pre-audit: Log request
    pre_state = storage.get_profile(subject_id, tenant_id)
    
    fact_id = ObjectId()
    
    # Write fact
    success = storage.add_fact(
        subject_id=subject_id,
        tenant_id=tenant_id,
        fact_id=fact_id,
        fact_text=fact,
        fact_type=fact_type,
        confidence=confidence
    )
    
    if not success:
        # Log failure
        storage.log_event({
            "event_type": "MEMORY_WRITE_FAILED",
            "subject_id": subject_id,
            "tenant_id": tenant_id,
            "job_id": job_context.get("job_id"),
            "invoker": job_context.get("invoker"),
            "reason": "write_failed"
        })
        return {"success": False}
    
    # Post-audit: Log success
    post_state = storage.get_profile(subject_id, tenant_id)
    
    event = {
        "event_type": "MEMORY_ADDED",
        "timestamp": datetime.utcnow(),
        "subject_id": subject_id,
        "tenant_id": tenant_id,
        "job_id": job_context.get("job_id"),
        "invoker": job_context.get("invoker"),
        "operation": {
            "action": "add_fact",
            "fact_id": str(fact_id),
            "fact_text": fact,
            "fact_type": fact_type,
            "confidence": confidence
        },
        "audit": {
            "before": pre_state.get("creative_profile", {}).get("memorable_facts", []),
            "after": post_state.get("creative_profile", {}).get("memorable_facts", []),
            "changed_count": 1
        },
        "write_concern": {
            "w": "majority",
            "j": True
        },
        "success": True
    }
    
    # Log to TDOS ledger
    storage.log_event(event)
    
    # Also log to kernel ledger
    kernel.ledger.append_entry(
        operation="MEMORY_ADDED",
        subject=subject_id,
        tenant=tenant_id,
        job_id=job_context.get("job_id"),
        data=event
    )
    
    return {
        "success": True,
        "fact_id": str(fact_id),
        "event_id": event.get("event_id")
    }
```

---

## Immutability Guarantee

### Append-Only with Decay

**Never delete memory**; instead, apply decay.

```python
# ❌ WRONG: Direct deletion (violates immutability)
db.discord_profiles.update_one(
    {"user_id": user_id},
    {"$pull": {"memorable_facts": {"confidence": {"$lt": 0.50}}}}
)

# ✅ CORRECT: Mark as inactive via decay
def apply_confidence_decay(subject_id, tenant_id):
    """Age-based decay, never delete."""
    
    profile = db.find_one(subject_id, tenant_id)
    
    for fact in profile["memorable_facts"]:
        age_days = (now - fact["added_at"]).days
        
        # Check decay window (don't delete)
        if fact["type"] == "USER_FACT" and age_days > 30:
            # Mark as inactive, keep in DB for audit trail
            fact["active"] = False
        # ... similar for patterns, narratives
    
    # Update profile (re-read to include new facts)
    profile_fresh = db.find_one(subject_id, tenant_id)  # ← Re-read
    for fact in profile_fresh["memorable_facts"]:
        age_days = (now - fact["added_at"]).days
        if should_decay(fact, age_days):
            fact["active"] = False
    
    # Write with audit trail
    db.update_one(
        {"user_id": subject_id, "guild_id": tenant_id},
        {"$set": {"creative_profile.memorable_facts": profile_fresh["memorable_facts"]}},
        write_concern=WriteConcern(w="majority", j=True)
    )
    
    # Log decay operation
    log_decay_event(subject_id, tenant_id, facts_decayed=count)
```

**Benefit**: Full audit trail, never lose data, able to analyze why fact was deemed inactive.

---

## Tenant Isolation Enforcement

### Query-Level Isolation

**Every query must include tenant_id**:

```python
# ✅ GOOD: Tenant-scoped query
profile = db.discord_profiles.find_one({
    "user_id": user_id,
    "guild_id": tenant_id            # ← MUST include
})

# ❌ BAD: No tenant scope (leaks across guilds)
profile = db.discord_profiles.find_one({"user_id": user_id})
```

**Enforce at Index Level**:

```javascript
// Create index enforcing tenant scope
db.discord_profiles.createIndex(
    {user_id: 1, guild_id: 1},
    {unique: true}
)

// This prevents duplicate (user, guild) pairs
// Ensures strict subject+tenant identity
```

**Query Helper** (enforce in code):

```python
class TenantSafeStorage:
    """Wrapper ensuring all queries are tenant-scoped."""
    
    def find_profile(self, user_id, guild_id):
        """Get profile (guild_id required)."""
        if not guild_id:
            raise ValueError("guild_id (tenant) required")
        
        return db.discord_profiles.find_one({
            "user_id": user_id,
            "guild_id": guild_id         # ← Enforced
        })
    
    def find_events(self, user_id, guild_id, limit=50):
        """Get events (guild_id required)."""
        if not guild_id:
            raise ValueError("guild_id (tenant) required")
        
        return list(db.memory_events.find({
            "subject_id": f"USER:{user_id}",
            "tenant_id": f"TENANT:{guild_id}"  # ← Enforced
        }).limit(limit))
    
    def add_fact(self, user_id, guild_id, fact, confidence):
        """Add fact (guild_id required)."""
        if not guild_id:
            raise ValueError("guild_id (tenant) required")
        
        return db.discord_profiles.update_one(
            {"user_id": user_id, "guild_id": guild_id},  # ← Scoped
            {"$push": {"creative_profile.memorable_facts": {...}}}
        )
```

---

## TDOS Deployment Architecture

### Architecture Diagram

```
[TDOS Kernel v1.5+]
    │
    ├─ [Job Scheduler]
    │   ├─ extract_memorable_facts:v1.0
    │   ├─ apply_confidence_decay:v1.0
    │   └─ refresh_memory_envelope:v1.0
    │
    ├─ [Capability Manager]
    │   ├─ memory:read:{subject_id}
    │   ├─ memory:write:{subject_id}
    │   └─ memory:decay:{subject_id}
    │
    ├─ [Ledger] (Immutable)
    │   └─ All memory operations logged
    │
    └─ [Adapters]
        ├─ Discord Adapter
        ├─ Slack Adapter
        └─ Custom Adapters
            │
            ├─ [Memory System]
            │   ├─ Extraction (LLM)
            │   ├─ Validation
            │   ├─ Storage (MongoDB)
            │   └─ Retrieval
            │
            └─ [Envelope]
                └─ → LLM Prompt
```

---

## Integration Checklist

### Phase 1: Foundation
- [ ] Deploy memory system to TDOS /agents/memory/
- [ ] Configure MongoDB connection (use TDOS secrets manager)
- [ ] Create indexes
- [ ] Verify determinism with seed-based tests

### Phase 2: Job Registration
- [ ] Register extract_memorable_facts job with kernel
- [ ] Register apply_confidence_decay job
- [ ] Register refresh_envelope_cache job
- [ ] Define job dependencies

### Phase 3: Permission Setup
- [ ] Define memory capabilities in TDOS RBAC
- [ ] Configure job→capability mappings
- [ ] Set up invoker authentication
- [ ] Test permission gating

### Phase 4: Ledger Integration
- [ ] Map memory events to ledger schema
- [ ] Configure ledger append (verify immutability)
- [ ] Audit event logging
- [ ] Test ledger query performance

### Phase 5: Multi-Adapter Testing
- [ ] Test with Discord adapter
- [ ] Test with Slack adapter
- [ ] Verify tenant isolation across adapters
- [ ] Test cross-adapter memory sharing (controlled)

### Phase 6: Monitoring & Observability
- [ ] Configure metrics export (Prometheus)
- [ ] Set up logs aggregation
- [ ] Create dashboards (Grafana)
- [ ] Define alerting rules

### Phase 7: Production Hardening
- [ ] Load testing (10k+ subjects)
- [ ] Decay scheduler reliability
- [ ] Cache invalidation robustness
- [ ] Failover testing

---

## Sample TDOS Job: Extract Facts

```python
# /agents/memory/extract_facts_job.py

from tdos import Job, Subject, Tenant, Ledger, Capabilities
from memory_system.extraction import extract_memorable_facts
from memory_system.storage import MemoryStorage

class ExtractMemorableFactsJob(Job):
    """Extract facts from conversation summary."""
    
    name = "extract_memorable_facts"
    version = "1.0"
    description = "Extract memorable facts from conversation"
    
    required_capabilities = [
        "memory:write:{subject_id}",
        "tenant:access:{tenant_id}"
    ]
    
    def execute(
        self,
        summary: str,
        subject: Subject,
        tenant: Tenant,
        context: dict
    ) -> dict:
        """Execute fact extraction."""
        
        # Check permissions
        if not self.check_capabilities(context["invoker"], subject, tenant):
            self.ledger.log_denied_operation(
                operation="extract_facts",
                subject=subject,
                tenant=tenant,
                reason="insufficient_capabilities"
            )
            return {"success": False, "error": "Permission denied"}
        
        # Extract facts (deterministic)
        storage = MemoryStorage()
        facts = extract_memorable_facts(
            summary=summary,
            subject_id=subject.full_id,
            tenant_id=tenant.full_id,
            storage=storage,
            seed=context.get("seed", 42)  # Deterministic
        )
        
        # Log to ledger
        self.ledger.append_entry(
            operation="MEMORY_EXTRACTION",
            subject=subject,
            tenant=tenant,
            job_id=context["job_id"],
            invoker=context["invoker"],
            data={
                "facts_extracted": len(facts),
                "summary_hash": hash(summary),
                "seed": context.get("seed", 42)
            }
        )
        
        return {
            "success": True,
            "facts": facts,
            "count": len(facts)
        }
```

---

## Migration Path

### Step 1: Enable Memory System
```python
# In TDOS config
AGENTS = {
    "memory": {
        "enabled": True,
        "version": "1.0",
        "mongo_uri": "$SECRETS.MONGO_URI",
        "db_name": "memory"
    }
}
```

### Step 2: Register Jobs
```python
# In TDOS job registry
JOBS = {
    "extract_memorable_facts": {
        "module": "agents.memory.extract_facts_job",
        "class": "ExtractMemorableFactsJob",
        "enabled": True
    },
    "apply_confidence_decay": {
        "module": "agents.memory.decay_job",
        "class": "ApplyConfidenceDecayJob",
        "enabled": True,
        "schedule": "0 6 * * *"  # 6 AM daily
    }
}
```

### Step 3: Enable in Adapters
```python
# In Discord adapter
MEMORY_CONFIG = {
    "enabled": True,
    "extract_after_conversation": True,
    "include_envelope_in_prompt": True
}
```

---

## Performance Targets

**For TDOS Adoption**:

- Envelope load: <100 ms (p99)
- Fact extraction: <5 seconds
- Cache hit rate: >95%
- Ledger append: <10 ms
- Query latency: <50 ms

**Monitoring** (via TDOS metrics):
```prometheus
memory_envelope_load_ms{subject_id="...", tenant_id="..."}
memory_extraction_duration_ms{job_id="..."}
memory_cache_hit_rate{tenant_id="..."}
memory_storage_size_bytes{tenant_id="..."}
```

---

## Success Criteria

✅ **Memory system is "TDOS-ready" when**:

1. All operations logged to kernel ledger
2. Tenant isolation enforced at query layer
3. All writes use WriteConcern(w="majority", j=True)
4. Determinism verified (seed-based reproducibility)
5. Permission model integrated with TDOS RBAC
6. Job definitions registered and tested
7. Audit trail complete and queryable
8. Immutability guaranteed (append-only)
9. Subject scoping enforced in all queries
10. Metrics exported to TDOS observability

---

## Future Enhancements

**Planned for v2.0**:

1. **Multi-tenant rollup**: Aggregate memory across tenants (with permission gates)
2. **Memory marketplace**: Subject opts-in to share patterns with kernel
3. **Causal ordering**: Track fact dependencies ("loves fettuccini" → "Italian cuisine" domain)
4. **Confidence redistribution**: Update related facts when confidence increases
5. **Temporal queries**: "What did I know about this subject on date X?"
6. **Fact versioning**: Track how confidence changed over time
7. **Consensus mechanism**: Multiple subjects vote on shared narratives


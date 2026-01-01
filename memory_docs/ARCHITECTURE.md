# Memory System Architecture

**Version**: 1.0  
**Status**: Production Ready

---

## System Layers

```
┌─────────────────────────────────────────────────────────────┐
│ [L3] Domain/Agent Layer                                     │
│      (Abby, Clerk, Scribe, etc.)                            │
│      Consumer of memory envelopes                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ [L2] Memory Envelope Layer                                  │
│      Packaging, formatting, caching                         │
│      format_envelope_for_llm()                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ [L1] Memory Management Layer                                │
│      Load, filter, decay application                        │
│      get_memory_envelope()                                  │
│      apply_confidence_decay()                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ [L0] Extraction & Validation Layer                          │
│      LLM-powered fact/pattern extraction                    │
│      Rule-based validation                                  │
│      extract_facts_from_summary()                           │
│      validate_fact_against_summary()                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Storage Layer (MongoDB)                                     │
│ discord_profiles.creative_profile.memorable_facts[]         │
│ discord_profiles.creative_profile.user_patterns[]           │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Extraction Flow

```
Session Start
  ↓
User Interaction
  ↓ (chat logs)
Session End → Generate Summary
  ↓ (narrative text of conversation)
Extract Facts from Summary
  ├─ LLM extracts candidate facts
  ├─ Validator grounds each fact in summary
  ├─ Type each fact (FACT | PATTERN | NARRATIVE)
  └─ Assign confidence score
  ↓
Filter by Type
  ├─ USER_FACT (conf ≥ 0.8)
  ├─ USER_PATTERN (conf ≥ 0.75)
  └─ SHARED_NARRATIVE (conf ≥ 0.6)
  ↓
Write to MongoDB
  ├─ Append to subject's memory array
  ├─ Record timestamp + source
  ├─ Store confidence score
  └─ Emit event (for audit/TDOS ledger)
```

### Retrieval Flow

```
Request for Memory (subject_id, tenant_id)
  ↓
Fetch from Cache (if TTL valid)
  └─ Hit? Return immediately
  ↓ Miss
Load from MongoDB
  ├─ Query: subject_id + tenant_id
  ├─ Filter: confidence_threshold
  └─ Sort: most recent first, limit to N
  ↓
Apply Decay Rules
  ├─ USER_FACT: 30-day decay
  ├─ USER_PATTERN: 14-day decay
  └─ SHARED_NARRATIVE: 7-day decay
  ↓
Exclude Expired Entries
  └─ Mark as inactive (keep in storage for audit)
  ↓
Package into Envelope
  ├─ Include identity (subject, tenant)
  ├─ Include top K facts
  ├─ Include patterns (with caveats)
  ├─ Include recent context
  └─ Include constraints (opt-outs, etc.)
  ↓
Cache with TTL (900 seconds)
  ↓
Return to Caller
```

---

## Memory Types

### USER_FACT

**Characteristics**:

- Explicitly stated or strongly implied by user
- Verbatim-grounded in conversation summary
- Examples: "loves fettuccini", "works on FL Studio", "was a Masters player"
- Confidence threshold: ≥ 0.80
- Decay: 30 days

**Validation**:

- Must appear textually in summary
- Must be specific and concrete
- Cannot be inferred beyond stated context

**LLM Usage**:

- Treated as authoritative context
- Used to personalize responses
- Used to maintain consistency

**Never**:

- Used for permission/access decisions
- Treated as declarative system facts
- Extended beyond stated domain

### USER_PATTERN

**Characteristics**:

- Aggregated behavior across multiple interactions
- Never single-incident, always trend-based
- Examples: "prefers step-by-step explanations", "tends to ask about music"
- Confidence threshold: ≥ 0.75
- Decay: 14 days

**Validation**:

- Must be observed across multiple sessions
- Must not contradict explicit user preferences
- Requires confidence gate (< 0.75 → proposal only, not auto-apply)

**LLM Usage**:

- Phrased as tendencies: "often prefers...", "typically..."
- Never phrased as absolutes
- Combined with current session signals for real-time adaptation

**Never**:

- Used for permission decisions
- Treated as fact
- Applied if user contradicts pattern

### SHARED_NARRATIVE

**Characteristics**:

- Inside jokes, shared memories, warmth
- Informational/relational only
- Examples: "I remember when you first told me about FL Studio", "We've been chatting since 2019"
- Confidence threshold: ≥ 0.60
- Decay: 7 days

**Validation**:

- Grounded in conversation history
- Never conflates user facts with bot observations

**LLM Usage**:

- Used for tone and continuity
- Creates sense of shared history
- Humanizes interaction

**Critical Rules**:

- ❌ NEVER used for inference or decision-making
- ❌ NEVER embedded in system prompts as facts
- ❌ NEVER influences permissions, pricing, moderation
- ❌ NEVER leaks into power/authority logic

---

## Confidence Scoring

Confidence ranges: 0.0 to 1.0

| Range     | Interpretation               | Action                               |
| --------- | ---------------------------- | ------------------------------------ |
| 0.90–1.0  | Explicitly stated            | Auto-apply, use in responses         |
| 0.80–0.89 | Strongly implied             | Auto-apply, use in responses         |
| 0.75–0.79 | Clear pattern, requires gate | Propose only, wait for confirmation  |
| 0.60–0.74 | Weak signal, needs context   | Narrative only, do not apply updates |
| < 0.60    | Insufficient signal          | Discard                              |

**Gating Logic**:

- High confidence (≥ 0.8) → Auto-apply pattern updates
- Medium confidence (0.75–0.79) → Log as proposal, do not apply
- Low confidence (< 0.75) → Do not extract

---

## Decay Rules

Decay is **applied per-query**, not per-write. Facts remain in storage indefinitely but are filtered from active envelopes based on age.

### USER_FACT Decay (30-day window)

```
Age (days)    Included in Envelope?
0–7           Yes (fresh)
7–14          Yes (recent)
14–30         Yes (still active, but older)
30+           No (expired)
```

### USER_PATTERN Decay (14-day window)

```
Age (days)    Included in Envelope?
0–7           Yes (current trend)
7–14          Yes (still active)
14+           No (expired)
```

### SHARED_NARRATIVE Decay (7-day window)

```
Age (days)    Included in Envelope?
0–3           Yes (fresh)
3–7           Yes (still active)
7+            No (expired)
```

**Expired Facts**:

- Remain in MongoDB (immutable audit trail)
- Marked with `active: false` flag
- Not included in memory envelopes
- Can be manually archived/pruned after 90 days

---

## Storage Schema

### Memory Entry (Single Fact/Pattern/Narrative)

```python
{
    "id": str,                           # UUID, unique per fact
    "subject_id": str,                   # "USER:246030816692404234"
    "tenant_id": str,                    # "TENANT:BreezeCrew"

    "type": str,                         # "USER_FACT" | "USER_PATTERN" | "SHARED_NARRATIVE"
    "fact": str,                         # Natural language fact text
    "source": str,                       # "llm_extraction", "manual_input", etc.
    "confidence": float,                 # 0.0–1.0

    "added_at": datetime,                # When fact was first added
    "last_confirmed": datetime,          # When fact was most recently confirmed

    "active": bool,                      # Decay flag (true if within TTL window)
    "metadata": dict,                    # Optional: {"context": "...", "validator": "..."}
}
```

### MongoDB Collection Path

```
Database: Abby_Database
Collection: discord_profiles
Document: { user_id: "246030816692404234" }

Subcollection (nested array):
  creative_profile.memorable_facts: [memory_entry, ...]
  creative_profile.user_patterns: [memory_entry, ...]
```

---

## Caching Strategy

**Cache Layer**: In-memory (per-agent process)
**Key**: `{subject_id}:{tenant_id}`
**TTL**: 900 seconds (15 minutes)
**Invalidation Triggers**:

- TTL expires
- New memory added for subject
- Manual cache flush (cache_invalidate)

**Benefits**:

- Reduces MongoDB load
- Fast envelope retrieval (milliseconds vs. hundreds of ms)
- Safe within 15-minute window for eventual consistency

**Tradeoff**:

- New facts take up to 15 minutes to appear (expected behavior)
- Acceptable for advisory/warmth use cases

---

## Write Authority

**Only these components may write memory**:

1. **Discord Adapter** (abby_adapters.discord.cogs.Chatbot)

   - Receives extraction from memory_extraction module
   - Validates confidence gates
   - Writes to MongoDB via add_memorable_fact()

2. **Owner Override** (SUBJECT:DONOVAN or equiv.)

   - Manual correction/entry
   - Admin interface (future)

3. **Agent Systems** (future Clerk/Scribe/Kernel agents)
   - Follow same extraction → validation → write flow
   - Use TDOS job context for audit

**Never written by**:

- Direct user input (always goes through extraction first)
- External systems (no webhooks to memory directly)
- Unchecked LLM output (always validated)

---

## Audit & Immutability

Every memory write emits an event:

```python
{
    "event_id": str,                     # Unique event ID
    "event_type": str,                   # "MEMORY_FACT_ADDED", "MEMORY_PATTERN_UPDATED", etc.
    "timestamp": datetime,               # ISO-8601 UTC
    "subject_id": str,                   # Who this is about
    "tenant_id": str,                    # Tenant context
    "invoker_subject_id": str,           # Who made the change (Abby, admin, etc.)

    "memory_id": str,                    # ID of the fact/pattern affected
    "memory_type": str,                  # "USER_FACT", etc.
    "memory_content": dict,              # The actual fact (for audit)
    "confidence": float,                 # Confidence at write time

    "metadata": dict,                    # {"reason": "...", "source": "..."}
}
```

**Event Log Storage**:

- Append-only MongoDB collection: `memory_events`
- Indexed by timestamp, subject_id, tenant_id
- Immutable (delete forbidden)
- Synced to TDOS event ledger (future)

---

## Edge Cases & Safety

### Case 1: User Changes Preference Mid-Pattern

**Scenario**: Pattern says "user prefers detailed explanations", but user explicitly says "keep it brief"
**Resolution**: Current session context overrides pattern. Pattern marked stale on next auto-refresh.

### Case 2: Conflicting Facts

**Scenario**: One extraction says "loves coffee", another says "doesn't drink coffee"
**Resolution**: Both stored with timestamps. Envelope includes both with confidence scores. LLM resolves in context.

### Case 3: Cross-Tenant Memory Leak

**Scenario**: User active in multiple Discord servers (different tenants)
**Resolution**: Memory query enforced at MongoDB level: `tenant_id` + `subject_id` index ensures isolation.

### Case 4: Stale Cache During High-Frequency Updates

**Scenario**: Multiple facts added within 15-minute cache window
**Resolution**: Cache TTL acceptable for advisory use. Critical decisions should refresh. Manual invalidate available.

---

## Performance Characteristics

| Operation                        | Latency   | Notes                        |
| -------------------------------- | --------- | ---------------------------- |
| get_memory_envelope (cache hit)  | 1–5ms     | In-memory                    |
| get_memory_envelope (cache miss) | 50–200ms  | MongoDB query                |
| extract_facts_from_summary       | 2–5s      | LLM call                     |
| add_memorable_fact               | 100–500ms | MongoDB write + verification |
| apply_confidence_decay           | 10–50ms   | In-memory filter             |
| format_envelope_for_llm          | 1–10ms    | String formatting            |

**Optimization Notes**:

- Extraction is LLM-bound, not storage-bound
- Reads are cache-optimized (900s TTL)
- Writes include verification (small overhead, critical for correctness)
- Decay is lazy (applied at read time, not background job)

---

## Configuration Recommendations

```python
# Self-contained defaults (no config file needed)

MEMORY_CONFIG = {
    # Decay windows (days)
    "USER_FACT_DECAY_DAYS": 30,
    "USER_PATTERN_DECAY_DAYS": 14,
    "SHARED_NARRATIVE_DECAY_DAYS": 7,

    # Confidence thresholds
    "FACT_MIN_CONFIDENCE": 0.80,
    "PATTERN_MIN_CONFIDENCE": 0.75,
    "NARRATIVE_MIN_CONFIDENCE": 0.60,

    # Envelope packing
    "MAX_FACTS_IN_ENVELOPE": 5,
    "MAX_PATTERNS_IN_ENVELOPE": 3,
    "MAX_NARRATIVES_IN_ENVELOPE": 2,

    # Caching
    "CACHE_TTL_SECONDS": 900,
    "CACHE_BACKEND": "memory",  # future: redis, memcached

    # Storage
    "MEMORY_STORE": "mongodb",
    "ARCHIVE_AFTER_DAYS": 90,  # Optional background cleanup
}
```

All values overridable at runtime; no external config required.

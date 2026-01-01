# Memory Envelope Pattern

**Version**: 1.0  
**Pattern Type**: Contextual intelligence packaging  
**TDOS Analog**: Job execution context envelope

---

## Overview

The Memory Envelope is the primary pattern for packaging subject intelligence into a consumable, LLM-friendly format. It's a structured container that includes facts, patterns, recent context, and constraints—all subject-scoped and ready for consumption.

**Core Purpose**: Transform raw memory data into contextual intelligence that can be injected into prompts or decision trees.

---

## Envelope Structure

```python
MemoryEnvelope = {
    # [Identity] Who is this about?
    "identity": {
        "subject_id": str,              # "USER:246030816692404234"
        "tenant_id": str,               # "TENANT:BreezeCrew"
        "subject_type": str,            # "USER"
        "display_name": str,            # "Z8phyR" (for logging)
    },
    
    # [Relational Intelligence] What do we know about them?
    "relational": {
        "memorable_facts": [
            {
                "fact": "Loves fettuccini",
                "confidence": 0.85,
                "added_at": "2025-12-31T01:10:36Z",
                "age_days": 0,
                "type": "USER_FACT"
            },
            # ... more facts
        ],
        "patterns": [
            {
                "pattern": "Prefers step-by-step explanations",
                "confidence": 0.80,
                "inferred_from": "multiple sessions",
                "type": "USER_PATTERN"
            },
            # ... more patterns
        ],
        "narratives": [
            {
                "narrative": "Been chatting since 2019",
                "confidence": 0.95,
                "type": "SHARED_NARRATIVE"
            },
            # ... more narratives
        ],
        "confidence_score": float,      # Aggregate confidence (0.0–1.0)
        "learning_level": str,          # "beginner", "intermediate", "advanced"
        "domains": [str],               # ["music production", "FL Studio"]
        "preferences": {
            "communication_style": str, # "casual", "formal", "technical"
            "detail_level": str,        # "high", "medium", "low"
            "explanation_style": str,   # "step-by-step", "conceptual", "examples"
        }
    },
    
    # [Recent Context] What happened in this session?
    "recent_context": {
        "session_id": str,              # "28233af0-e244-49f8-b593..."
        "last_active": str,             # ISO-8601 timestamp
        "session_summary": str,         # Concise summary of last interaction
        "topics_discussed": [str],      # ["fettuccini", "music production"]
        "tone": str,                    # "playful", "serious", "casual"
    },
    
    # [Constraints] What are the rules for this subject?
    "constraints": {
        "memory_enabled": bool,         # Can we learn about them?
        "learn_patterns": bool,         # Can we aggregate patterns?
        "share_with": [str],            # ["discord_adapter", "clerk_agent"]
        "anonymize_dates": bool,        # Blur timestamps?
        "delete_after_days": int,       # Auto-delete (GDPR)
    },
    
    # [Metadata] System info
    "metadata": {
        "created_at": str,              # Envelope creation timestamp
        "cache_ttl_seconds": int,       # How long cached (usually 900)
        "source": str,                  # "memory_system:v1.0"
    }
}
```

---

## Envelope Lifecycle

### 1. Creation (get_memory_envelope)

```python
def get_memory_envelope(
    subject_id: str,
    tenant_id: str,
    skip_cache: bool = False
) -> MemoryEnvelope:
    """Retrieve or create memory envelope for subject."""
    
    # Check cache first
    if cached := cache.get(f"{subject_id}:{tenant_id}"):
        return cached
    
    # Load from MongoDB
    profile = db.discord_profiles.find_one({
        "user_id": subject_id,
        "guild_id": tenant_id
    })
    
    # Build envelope
    envelope = MemoryEnvelope(
        identity={
            "subject_id": subject_id,
            "tenant_id": tenant_id,
            # ...
        },
        relational={
            "memorable_facts": apply_decay(profile.facts),
            "patterns": apply_decay(profile.patterns),
            # ...
        },
        recent_context={
            # ... from last session
        },
        constraints={
            # ... from user preferences
        }
    )
    
    # Cache with TTL
    cache.set(f"{subject_id}:{tenant_id}", envelope, ttl=900)
    
    return envelope
```

### 2. Filtering (Decay Application)

```python
def apply_confidence_decay(facts, decay_days=30):
    """Filter facts by age and decay window."""
    now = datetime.utcnow()
    active_facts = []
    
    for fact in facts:
        age_days = (now - fact.added_at).days
        
        # Check decay window
        if fact.type == "USER_FACT" and age_days > 30:
            fact.active = False
            continue
        if fact.type == "USER_PATTERN" and age_days > 14:
            fact.active = False
            continue
        if fact.type == "SHARED_NARRATIVE" and age_days > 7:
            fact.active = False
            continue
        
        active_facts.append(fact)
    
    return active_facts
```

### 3. Formatting (format_envelope_for_llm)

```python
def format_envelope_for_llm(
    envelope: MemoryEnvelope,
    max_facts: int = 5,
    include_patterns: bool = True,
    include_narratives: bool = True
) -> str:
    """Format envelope into concise LLM-friendly text."""
    
    lines = []
    
    # Identity (brief)
    lines.append(f"Subject: {envelope.identity['display_name']}")
    
    # Facts (highest priority)
    lines.append("\nKnown Facts:")
    for fact in envelope.relational['memorable_facts'][:max_facts]:
        lines.append(f"  - {fact['fact']}")
    
    # Patterns (marked as tendencies)
    if include_patterns:
        lines.append("\nObserved Patterns:")
        for pattern in envelope.relational['patterns'][:3]:
            lines.append(f"  - Often {pattern['pattern']}")
    
    # Preferences
    if envelope.relational['preferences']:
        lines.append("\nPreferences:")
        for key, val in envelope.relational['preferences'].items():
            lines.append(f"  - {key}: {val}")
    
    # Narratives (marked as warmth)
    if include_narratives:
        lines.append("\nShared Context:")
        for narrative in envelope.relational['narratives'][:2]:
            lines.append(f"  - {narrative['narrative']}")
    
    return "\n".join(lines)
```

### 4. Usage in Prompt

```python
# Load envelope
envelope = get_memory_envelope(user_id, tenant_id)

# Format for LLM
context = format_envelope_for_llm(envelope)

# Build system prompt
system_prompt = f"""You are Abby, a helpful assistant.

{context}

Respond naturally, adapting to their preferences where appropriate.
Never treat memories as authoritative facts; use them as context for warmth."""

# Use in chat
response = llm.chat(
    system_prompt=system_prompt,
    user_message=user_input,
    chat_history=chat_history
)
```

---

## Envelope Consumption Guidelines

### DO ✅

- Use facts to maintain continuity ("You mentioned loving fettuccini")
- Use patterns to adapt communication style (if preference for detail)
- Use narratives for warmth and connection ("Since we've been chatting since 2019...")
- Reference recent context to ground responses
- Respect constraints (memory_enabled, learn_patterns, etc.)

### DON'T ❌

- Treat patterns as absolute truth ("You always prefer step-by-step")
- Use patterns for permission/access decisions
- Inject narratives into factual claims
- Override user contradictions with learned patterns
- Share envelope across tenants
- Store envelope as-is (treat as temporary, regenerate per-session)

### Example Response

**Bad**:
```
You're advanced in music production, so here's a complex implementation...
```
(Pattern treated as fact; no user confirmation)

**Good**:
```
You mentioned enjoying FL Studio optimization. Here's an approach—I can go deeper if you'd like.
```
(Fact-grounded; offers flexibility)

---

## Envelope Caching

**Cache Key**: `{subject_id}:{tenant_id}`
**TTL**: 900 seconds (15 minutes)
**Storage**: In-memory (per-process)

**Cache Invalidation Triggers**:

```python
# Automatic (after TTL)
cache.expire(key, ttl=900)

# Manual (after new memory added)
invalidate_cache(subject_id, tenant_id)

# Manual (force refresh)
envelope = get_memory_envelope(subject_id, tenant_id, skip_cache=True)
```

**Benefits**:
- Millisecond retrieval
- Reduced MongoDB load
- Fast prompt injection

**Tradeoff**:
- New facts take up to 15 minutes to appear
- Acceptable: facts are low-priority context

---

## Envelope Constraints (Future)

**Current Implementation**: constraints field is reserved.

**Planned Rules**:

```python
constraints = {
    # Can we learn about this subject at all?
    "memory_enabled": True,
    
    # Can we aggregate patterns?
    "learn_patterns": True,
    
    # Which systems can access this envelope?
    "share_with": ["discord_adapter"],  # Don't share with unknown agents
    
    # Privacy: blur dates?
    "anonymize_dates": False,
    
    # GDPR: auto-delete after N days
    "delete_after_days": None,
}
```

**Enforcement**:
- Check constraints before add_memorable_fact()
- Check constraints before returning envelope
- Respect opt-outs in all downstream logic

---

## Envelope Serialization

**For Storage / Audit Logging**:

```python
import json

# Serialize envelope to JSON (for audit)
envelope_json = json.dumps(envelope, default=str)

# Log event
event = {
    "event_type": "ENVELOPE_LOADED",
    "subject_id": envelope.identity["subject_id"],
    "envelope_snapshot": envelope_json,
    "timestamp": datetime.utcnow(),
}

db.memory_events.insert_one(event)
```

**For Caching**:

```python
import pickle

# Serialize to bytes (for in-memory cache)
envelope_bytes = pickle.dumps(envelope)
cache.set(key, envelope_bytes)

# Deserialize from cache
envelope = pickle.loads(cache.get(key))
```

---

## Envelope Size & Performance

**Typical Envelope Size**: 2–10 KB
**Formatting Time**: 1–10 ms
**Cache Hit Time**: 1–5 ms
**Cache Miss Time**: 50–200 ms

**Optimization Tips**:

1. **Limit facts in envelope**:
   ```python
   format_envelope_for_llm(envelope, max_facts=5)
   ```

2. **Skip unnecessary sections**:
   ```python
   format_envelope_for_llm(envelope, include_narratives=False)
   ```

3. **Use cache religiously**:
   ```python
   # ✅ Good: will hit cache 99% of time
   envelope = get_memory_envelope(user_id)
   
   # ❌ Bad: always queries DB
   envelope = get_memory_envelope(user_id, skip_cache=True)
   ```

4. **Pre-format for common cases**:
   ```python
   # Cache the formatted string too
   formatted = format_envelope_for_llm(envelope)
   cache.set(f"{user_id}:formatted", formatted, ttl=900)
   ```

---

## Multi-Envelope Usage (Future)

For complex agents with multiple subject perspectives:

```python
# Clerk agent needing context for both client and creator
client_envelope = get_memory_envelope(
    subject_id="USER:client_id",
    tenant_id="TENANT:project_id"
)

creator_envelope = get_memory_envelope(
    subject_id="USER:creator_id",
    tenant_id="TENANT:project_id"
)

# Both envelopes same tenant (enforced isolation)
# Both envelopes different subjects (no leakage)

system_prompt = f"""
Client context:
{format_envelope_for_llm(client_envelope)}

Creator context:
{format_envelope_for_llm(creator_envelope)}

Bridge their needs thoughtfully.
"""
```

---

## Envelope Versioning

**Current Version**: 1.0

**Version Changes**:
- v1.0 → v1.1: Add "constraints" field (backward compatible)
- v1.0 → v2.0: Change memory typing system (breaking change)

**Version Header** (in envelope or logs):

```python
envelope["metadata"]["schema_version"] = "1.0"
```

**Compatibility Check**:

```python
def validate_envelope(envelope):
    version = envelope["metadata"]["schema_version"]
    if version != "1.0":
        raise ValueError(f"Unsupported envelope version: {version}")
    return True
```

---

## Testing the Pattern

**Unit Tests**:
- [ ] Envelope created correctly
- [ ] Decay filters facts by age
- [ ] Formatting produces valid LLM-friendly text
- [ ] Cache invalidation works
- [ ] Subject isolation enforced
- [ ] Constraints respected

**Integration Tests**:
- [ ] Envelope loads from MongoDB
- [ ] Envelope serializes/deserializes
- [ ] Cache hit/miss behavior correct
- [ ] Multiple subjects isolated

**Example Test**:

```python
def test_envelope_isolation():
    """Confirm no cross-subject leakage."""
    env1 = get_memory_envelope("USER:alice", "TENANT:breeze")
    env2 = get_memory_envelope("USER:bob", "TENANT:breeze")
    
    assert env1["identity"]["subject_id"] == "USER:alice"
    assert env2["identity"]["subject_id"] == "USER:bob"
    
    # Both in same tenant, but subject_id strictly separated
    assert env1 != env2
    assert len(env1["relational"]["memorable_facts"]) > 0
    assert len(env2["relational"]["memorable_facts"]) == 0  # Different facts
```


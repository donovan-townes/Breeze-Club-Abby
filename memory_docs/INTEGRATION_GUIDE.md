# Integration Guide: Using Memory System

**Version**: 1.0  
**Target Audience**: Developers integrating memory system into agents/adapters  
**Scope**: Self-contained setup, no external config required

---

## Quick Start (5 Minutes)

### Step 1: Copy Memory Module

```bash
# Copy memory system into your project
cp -r memory_system/ your_project/vendors/memory/

# Directory structure:
your_project/
├── vendors/
│   └── memory/
│       ├── __init__.py
│       ├── envelope.py          # Memory envelope pattern
│       ├── extraction.py        # LLM-based fact extraction
│       ├── validation.py        # Validation & guardrails
│       └── storage.py           # MongoDB interface
```

### Step 2: Initialize MongoDB Connection

```python
from vendors.memory.storage import MemoryStorage

# Self-contained: no config file needed
storage = MemoryStorage(
    mongo_uri="mongodb://localhost:27017",
    db_name="memory_db"
)

# Create indexes
storage.ensure_indexes()
```

### Step 3: Load User Memory

```python
from vendors.memory.envelope import get_memory_envelope

# Load envelope
envelope = get_memory_envelope(
    subject_id="USER:246030816692404234",
    tenant_id="TENANT:BreezeCrew",
    storage=storage
)

# Format for LLM
context = envelope.format_for_llm(max_facts=5)
```

### Step 4: Use in Prompt

```python
# Build system prompt with memory
system_prompt = f"""You are a helpful assistant.

{context}

Respond naturally, adapting to their preferences where appropriate."""

# Call LLM
response = llm.chat(system_prompt=system_prompt, user_message=user_input)
```

### Step 5: Extract & Store New Facts

```python
from vendors.memory.extraction import extract_memorable_facts

# After conversation, extract facts
facts = extract_memorable_facts(
    summary=conversation_summary,
    subject_id="USER:246030816692404234",
    tenant_id="TENANT:BreezeCrew",
    storage=storage
)

print(f"Stored {len(facts)} new facts")
```

---

## Installation

### Prerequisites

```python
# requirements.txt
pymongo>=4.0
openai>=1.0
```

### Install

```bash
pip install -r requirements.txt
```

### Verify MongoDB Connection

```python
from vendors.memory.storage import MemoryStorage

storage = MemoryStorage()
storage.test_connection()
# Output: Connected to MongoDB ✓
```

---

## Core API Reference

### get_memory_envelope()

Load a user's complete memory envelope.

```python
def get_memory_envelope(
    subject_id: str,                    # "USER:123"
    tenant_id: str,                     # "TENANT:guild_id"
    storage: MemoryStorage,
    skip_cache: bool = False            # Bypass cache?
) -> MemoryEnvelope:
    """Load memory envelope for subject."""
```

**Example**:
```python
envelope = get_memory_envelope(
    subject_id="USER:246030816692404234",
    tenant_id="TENANT:BreezeCrew",
    storage=storage
)
```

---

### format_envelope_for_llm()

Format envelope into LLM-friendly text.

```python
def format_envelope_for_llm(
    envelope: MemoryEnvelope,
    max_facts: int = 5,                 # Limit facts in output
    include_patterns: bool = True,      # Include inferred patterns?
    include_narratives: bool = True     # Include warmth/context?
) -> str:
    """Format envelope as concise text."""
```

**Example**:
```python
context = format_envelope_for_llm(
    envelope=envelope,
    max_facts=3,
    include_patterns=True,
    include_narratives=True
)

print(context)
# Output:
# Subject: Z8phyR
# 
# Known Facts:
#   - Loves fettuccini
#   - Works in radiology
# 
# Observed Patterns:
#   - Prefers detailed explanations
```

---

### extract_memorable_facts()

Extract and store facts from conversation summary.

```python
def extract_memorable_facts(
    summary: str,                       # Conversation summary
    subject_id: str,                    # "USER:123"
    tenant_id: str,                     # "TENANT:guild_id"
    storage: MemoryStorage
) -> List[dict]:
    """Extract facts from summary and store in MongoDB."""
```

**Example**:
```python
summary = """
User said they love fettuccini pasta.
They asked for step-by-step explanations.
Mentioned working in radiology for 5 years.
"""

facts = extract_memorable_facts(
    summary=summary,
    subject_id="USER:246030816692404234",
    tenant_id="TENANT:BreezeCrew",
    storage=storage
)

print(facts)
# [
#   {"fact": "Loves fettuccini", "confidence": 0.95},
#   {"pattern": "Prefers step-by-step explanations", "confidence": 0.85},
#   {"narrative": "Been working in radiology for 5 years", "confidence": 0.90}
# ]
```

---

### add_memorable_fact()

Manually add a single fact.

```python
def add_memorable_fact(
    subject_id: str,
    tenant_id: str,
    fact: str,                          # "Loves fettuccini"
    fact_type: str,                     # "USER_FACT"
    confidence: float,                  # 0.95
    storage: MemoryStorage
) -> bool:
    """Add fact to user's profile."""
```

**Example**:
```python
added = add_memorable_fact(
    subject_id="USER:246030816692404234",
    tenant_id="TENANT:BreezeCrew",
    fact="Loves fettuccini",
    fact_type="USER_FACT",
    confidence=0.95,
    storage=storage
)
print(f"Fact stored: {added}")  # True
```

---

### apply_confidence_decay()

Age-based decay for facts in a profile.

```python
def apply_confidence_decay(
    subject_id: str,
    tenant_id: str,
    storage: MemoryStorage
) -> dict:
    """Apply age-based decay to facts (automatic on retrieve)."""
```

**Note**: Decay is applied automatically when envelope is loaded. Manual call is rarely needed.

---

### invalidate_cache()

Manually clear cache for a subject.

```python
def invalidate_cache(
    subject_id: str,
    tenant_id: str
) -> bool:
    """Clear cached envelope (called automatically on new facts)."""
```

**Example**:
```python
# After manual profile update
invalidate_cache("USER:246030816692404234", "TENANT:BreezeCrew")

# Next envelope load will be fresh from MongoDB
```

---

## Common Patterns

### Pattern 1: Extract After Every Conversation

```python
async def handle_message(message, user_id, guild_id):
    """Process message and extract facts."""
    
    # Chat
    response = await chatbot.respond(message)
    
    # Build summary
    summary = f"{message.content}\n\nAssistant: {response}"
    
    # Extract facts
    facts = extract_memorable_facts(
        summary=summary,
        subject_id=f"USER:{user_id}",
        tenant_id=f"TENANT:{guild_id}",
        storage=storage
    )
    
    if facts:
        logger.info(f"Stored {len(facts)} facts for user {user_id}")
```

### Pattern 2: Check Memory Before Responding

```python
async def respond_with_memory(message, user_id, guild_id):
    """Load user memory and use for contextual response."""
    
    # Load envelope
    envelope = get_memory_envelope(
        subject_id=f"USER:{user_id}",
        tenant_id=f"TENANT:{guild_id}",
        storage=storage
    )
    
    # Format for prompt
    context = format_envelope_for_llm(envelope)
    
    # Build system prompt
    system_prompt = f"""You are Abby, a helpful assistant.

{context}

Respond naturally, adapting to their preferences where appropriate."""
    
    # Get response
    response = await llm.chat(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": message.content}]
    )
    
    return response
```

### Pattern 3: Bulk Memory Analysis

```python
def analyze_guild_memory(guild_id):
    """Analyze memory patterns across guild members."""
    
    # Find all profiles in guild
    profiles = storage.find_profiles(guild_id=guild_id)
    
    # Aggregate statistics
    stats = {
        "total_users": len(profiles),
        "avg_facts_per_user": 0,
        "most_common_patterns": [],
        "domains": []
    }
    
    all_facts = []
    all_patterns = []
    all_domains = []
    
    for profile in profiles:
        creative = profile["creative_profile"]
        all_facts.extend(creative["memorable_facts"])
        all_patterns.extend(creative["patterns"])
        all_domains.extend(creative["domains"])
    
    stats["avg_facts_per_user"] = len(all_facts) / len(profiles)
    
    # Count pattern occurrences
    from collections import Counter
    pattern_names = [p["pattern"] for p in all_patterns]
    stats["most_common_patterns"] = Counter(pattern_names).most_common(5)
    
    # Domain summary
    domain_names = [d["domain"] for d in all_domains]
    stats["domains"] = Counter(domain_names).most_common(10)
    
    return stats
```

### Pattern 4: GDPR Data Export

```python
def export_user_memory(user_id, guild_id):
    """Export user's complete memory (GDPR compliance)."""
    
    profile = storage.find_profile(user_id, guild_id)
    
    export = {
        "user_id": user_id,
        "guild_id": guild_id,
        "extracted_at": datetime.utcnow().isoformat(),
        "memory": {
            "facts": profile["creative_profile"]["memorable_facts"],
            "patterns": profile["creative_profile"]["patterns"],
            "narratives": profile["creative_profile"]["narratives"],
            "domains": profile["creative_profile"]["domains"]
        },
        "audit_trail": storage.get_events(user_id, guild_id, limit=100)
    }
    
    # Save as JSON
    filename = f"memory_export_{user_id}_{guild_id}.json"
    with open(filename, "w") as f:
        json.dump(export, f, indent=2, default=str)
    
    return filename
```

---

## Testing Integration

### Unit Test: Memory Envelope

```python
def test_memory_envelope():
    """Test envelope loading and formatting."""
    
    # Setup
    storage = MemoryStorage()
    user_id = "USER:test_123"
    guild_id = "TENANT:test_guild"
    
    # Add test fact
    add_memorable_fact(
        subject_id=user_id,
        tenant_id=guild_id,
        fact="Loves pasta",
        fact_type="USER_FACT",
        confidence=0.95,
        storage=storage
    )
    
    # Load envelope
    envelope = get_memory_envelope(user_id, guild_id, storage)
    assert envelope is not None
    assert len(envelope.relational["memorable_facts"]) >= 1
    
    # Format
    formatted = format_envelope_for_llm(envelope)
    assert "pasta" in formatted.lower()
```

### Integration Test: Full Pipeline

```python
@pytest.mark.integration
async def test_full_extraction_pipeline():
    """Test end-to-end fact extraction."""
    
    summary = """
    User mentioned loving fettuccini pasta. 
    Asked for step-by-step explanation.
    Said they've been using computers since 1999.
    """
    
    # Extract
    facts = extract_memorable_facts(
        summary=summary,
        subject_id="USER:test_123",
        tenant_id="TENANT:test_guild",
        storage=storage
    )
    
    # Verify
    assert len(facts) >= 2
    assert any("fettuccini" in f.get("fact", "") for f in facts)
    assert any("step" in f.get("pattern", "") for f in facts)
    
    # Verify stored in MongoDB
    profile = storage.find_profile("test_123", "test_guild")
    assert len(profile["creative_profile"]["memorable_facts"]) > 0
```

---

## Configuration (Optional)

The memory system is self-contained with sensible defaults. Override if needed:

```python
from vendors.memory.config import MemoryConfig

config = MemoryConfig(
    # MongoDB
    mongo_uri="mongodb://localhost:27017",
    db_name="memory_db",
    
    # LLM
    llm_model="gpt-4-turbo",
    extraction_temperature=0.3,        # Lower = more deterministic
    
    # Cache
    cache_ttl_seconds=900,             # 15 minutes
    
    # Decay
    fact_decay_days=30,
    pattern_decay_days=14,
    narrative_decay_days=7,
    
    # Confidence thresholds
    fact_threshold=0.80,
    pattern_threshold=0.75,
    narrative_threshold=0.60,
    
    # Logging
    verbose=False,
    log_rejections=True               # Log failed extractions?
)

storage = MemoryStorage(config=config)
```

---

## Troubleshooting

### Issue: "MongoDB connection refused"

**Solution**: Ensure MongoDB is running.
```bash
# Windows
mongod

# Or use local instance
python -c "from pymongo import MongoClient; MongoClient('mongodb://localhost:27017').admin.command('ping')"
```

### Issue: "No facts found for user"

**Possible Causes**:
1. User is new (no facts extracted yet)
2. Facts decayed away (older than 30 days)
3. Cache is stale

**Solutions**:
```python
# Force fresh load
envelope = get_memory_envelope(
    subject_id="USER:123",
    tenant_id="TENANT:guild",
    storage=storage,
    skip_cache=True  # ← Bypass cache
)

# Or manually extract facts
summary = "User said they love fettuccini"
facts = extract_memorable_facts(summary, "USER:123", "TENANT:guild", storage)
```

### Issue: "LLM extraction timeout"

**Solution**: Increase LLM timeout or use summary shortening.
```python
# Shorten summary before extraction
short_summary = conversation_summary[:2000]  # Max 2000 chars

facts = extract_memorable_facts(
    summary=short_summary,
    subject_id="USER:123",
    tenant_id="TENANT:guild",
    storage=storage,
    timeout_seconds=30  # ← Longer timeout
)
```

---

## Performance Tuning

### Optimize Cache Hit Rate

```python
# Use cache (default)
envelope = get_memory_envelope(user_id, guild_id)  # Cached

# Check cache before full query
from vendors.memory.cache import cache_get
if cached := cache_get(f"{user_id}:{guild_id}"):
    envelope = cached
else:
    envelope = get_memory_envelope(user_id, guild_id)
```

### Limit Envelope Size

```python
# For high-latency prompts, use minimal envelope
context = format_envelope_for_llm(
    envelope,
    max_facts=3,                      # Only top 3 facts
    include_patterns=False,           # Skip patterns
    include_narratives=False          # Skip warmth
)
```

### Batch Extractions

```python
# Extract for multiple users efficiently
summaries = {
    "USER:1": "summary 1",
    "USER:2": "summary 2",
    "USER:3": "summary 3",
}

results = {}
for user_id, summary in summaries.items():
    facts = extract_memorable_facts(
        summary=summary,
        subject_id=user_id,
        tenant_id="TENANT:guild",
        storage=storage
    )
    results[user_id] = facts
```

---

## Security Considerations

### Tenant Isolation

```python
# ✅ Good: All queries scoped to tenant
envelope = get_memory_envelope(
    subject_id="USER:123",
    tenant_id="TENANT:guild_A",      # ← Explicit tenant
    storage=storage
)

# ❌ Bad: Could leak data across tenants
envelope = get_memory_envelope(subject_id="USER:123")  # No tenant!
```

### Access Control

```python
# Before allowing memory access, verify permissions
def can_access_memory(requester_id, subject_id, guild_id):
    """Check if requester can access subject's memory."""
    
    # Only allow self-access or moderators
    if requester_id == subject_id:
        return True
    
    if is_moderator(requester_id, guild_id):
        return True
    
    return False

# Use in envelope loading
if can_access_memory(requester_id, subject_id, guild_id):
    envelope = get_memory_envelope(subject_id, guild_id, storage)
else:
    raise PermissionError("Cannot access this user's memory")
```

---

## Migration from Other Systems

### From Simple User Tracking

If you have existing user data (e.g., a dictionary of preferences):

```python
def migrate_to_memory(user_id, guild_id, existing_data, storage):
    """Migrate existing user data to memory system."""
    
    # Facts
    if existing_data.get("favorite_food"):
        add_memorable_fact(
            subject_id=f"USER:{user_id}",
            tenant_id=f"TENANT:{guild_id}",
            fact=f"Loves {existing_data['favorite_food']}",
            fact_type="USER_FACT",
            confidence=0.85,  # Migrated data is trusted
            storage=storage
        )
    
    # Patterns
    if existing_data.get("communication_style"):
        add_memorable_fact(
            subject_id=f"USER:{user_id}",
            tenant_id=f"TENANT:{guild_id}",
            fact=f"Prefers {existing_data['communication_style']} communication",
            fact_type="USER_PATTERN",
            confidence=0.80,
            storage=storage
        )
    
    print(f"Migrated data for user {user_id}")
```

---

## Next Steps

1. **Integrate into your adapter**: Use patterns above
2. **Test extraction**: Run unit tests with your domain
3. **Monitor logs**: Check rejection patterns to refine LLM prompt
4. **Tune configuration**: Adjust decay windows and thresholds
5. **TDOS integration**: See [TDOS_MAPPING.md](TDOS_MAPPING.md) for kernel alignment


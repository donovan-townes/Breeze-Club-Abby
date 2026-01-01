# Data Model & Schema

**Version**: 1.0  
**Purpose**: Define all data structures, MongoDB schemas, validation rules, and indexes  
**TDOS Analog**: Immutable data ledger schema

---

## Overview

The memory system stores data in MongoDB with a well-defined schema. This document specifies:

- MongoDB collection structure
- Python/TypeScript type definitions
- Validation rules and constraints
- Index definitions and performance tuning
- Event schema for audit logging
- Query patterns

---

## MongoDB Collections

### 1. discord_profiles (Main Profile Storage)

**Purpose**: Store user memory profiles with facts, patterns, preferences.

**Schema**:

```javascript
db.discord_profiles.insertOne({
  // [Identity]
  user_id: "246030816692404234", // Discord user ID
  guild_id: "1234567890123456789", // Discord guild (tenant) ID

  // [Profile Metadata]
  created_at: ISODate("2025-01-15T10:00:00Z"),
  updated_at: ISODate("2025-01-15T10:30:00Z"),
  last_active: ISODate("2025-01-15T10:30:00Z"),
  message_count: 42, // Total interactions
  session_count: 5, // Number of conversations

  // [Creative Profile]
  creative_profile: {
    // Facts: explicitly stated preferences/attributes
    memorable_facts: [
      {
        _id: ObjectId(),
        fact: "Loves fettuccini",
        type: "USER_FACT",
        confidence: 0.85,
        added_at: ISODate("2025-01-14T09:30:00Z"),
        last_confirmed_at: ISODate("2025-01-15T10:00:00Z"),
        confirmation_count: 2, // Times re-confirmed
        source: "conversation_summary",
        source_hash: "sha256_of_summary",
      },
      // ... more facts
    ],

    // Patterns: inferred behaviors
    patterns: [
      {
        _id: ObjectId(),
        pattern: "Prefers step-by-step explanations",
        type: "USER_PATTERN",
        confidence: 0.8,
        added_at: ISODate("2025-01-13T14:22:00Z"),
        last_observed: ISODate("2025-01-15T10:00:00Z"),
        observation_count: 3, // Times observed
        source: "behavior_inference",
      },
      // ... more patterns
    ],

    // Narratives: shared context
    narratives: [
      {
        _id: ObjectId(),
        narrative: "Been chatting since 2019",
        type: "SHARED_NARRATIVE",
        confidence: 0.95,
        added_at: ISODate("2025-01-15T09:00:00Z"),
        is_confirmed: true,
      },
      // ... more narratives
    ],

    // Preferences (inferred from patterns/facts)
    preferences: {
      communication_style: "casual", // casual|formal|technical
      detail_level: "medium", // high|medium|low
      explanation_style: "step-by-step", // step-by-step|conceptual|examples
    },

    // Domains: topics of expertise/interest
    domains: [
      {
        domain: "music production",
        confidence: 0.85,
        tools: ["FL Studio", "Ableton"],
        last_mentioned: ISODate("2025-01-15T09:30:00Z"),
      },
      {
        domain: "gardening",
        confidence: 0.7,
        last_mentioned: ISODate("2025-01-15T10:15:00Z"),
      },
    ],

    // Aggregated metadata
    total_facts_lifetime: 12,
    total_patterns_lifetime: 8,
    total_narratives_lifetime: 3,
    avg_confidence: 0.82,
    learning_level: "intermediate",
  },

  // [Privacy & Constraints]
  constraints: {
    memory_enabled: true,
    learn_patterns: true,
    share_with: ["discord_adapter"],
    anonymize_dates: false,
    delete_after_days: null, // GDPR: never auto-delete
  },

  // [Metadata]
  version: "1.0",
  last_extraction_at: ISODate("2025-01-15T10:30:00Z"),
  last_decay_at: ISODate("2025-01-15T06:00:00Z"),
});
```

**Validation Rules**:

```javascript
db.discord_profiles.createIndex({ user_id: 1, guild_id: 1 }, { unique: true });

db.createCollection("discord_profiles", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["user_id", "guild_id", "created_at"],
      properties: {
        user_id: {
          bsonType: "string",
          pattern: "^[0-9]+$", // Numeric string
        },
        guild_id: {
          bsonType: "string",
          pattern: "^[0-9]+$",
        },
        creative_profile: {
          bsonType: "object",
          properties: {
            memorable_facts: {
              bsonType: "array",
              items: {
                bsonType: "object",
                required: ["fact", "type", "confidence", "added_at"],
                properties: {
                  confidence: {
                    bsonType: "double",
                    minimum: 0.6,
                    maximum: 1.0,
                  },
                },
              },
            },
          },
        },
      },
    },
  },
});
```

**Indexes**:

```javascript
// Primary lookup
db.discord_profiles.createIndex({ user_id: 1, guild_id: 1 }, { unique: true });

// Search by user in tenant
db.discord_profiles.createIndex({ guild_id: 1, user_id: 1 });

// Activity tracking
db.discord_profiles.createIndex({ guild_id: 1, last_active: -1 });

// Bulk decay operations
db.discord_profiles.createIndex(
  { "creative_profile.memorable_facts.added_at": 1 },
  { name: "fact_age_index" }
);

// Domain tracking
db.discord_profiles.createIndex(
  { "creative_profile.domains.domain": 1 },
  { name: "domain_index" }
);
```

---

### 2. memory_events (Audit Log)

**Purpose**: Immutable log of all memory operations (write, update, decay, cache invalidation).

**Schema**:

```javascript
db.memory_events.insertOne({
  // [Event Identity]
  _id: ObjectId(),
  event_id: "evt_abc123def456", // Unique event ID
  event_type: "MEMORY_ADDED|MEMORY_UPDATED|DECAY_APPLIED|CACHE_INVALIDATED",

  // [Timestamp]
  timestamp: ISODate("2025-01-15T10:30:45.123Z"),
  event_sequence: 1234567890, // Monotonic counter

  // [Subject & Tenant]
  subject_id: "USER:246030816692404234",
  tenant_id: "TENANT:BreezeCrew",
  invoker_subject_id: "CHATBOT:abby_v2.1", // Who triggered this?

  // [Operation Details]
  operation: {
    action: "add_fact", // Specific action
    memory_type: "USER_FACT",
    memory_content: {
      fact: "Loves fettuccini",
      confidence: 0.85,
      type: "USER_FACT",
    },
  },

  // [Write Concern]
  write_concern: {
    w: "majority",
    j: true, // Journaled
  },

  // [Result]
  result: {
    success: true,
    duration_ms: 42, // How long did operation take?
    affected_documents: 1,
    error: null,
  },

  // [Context]
  context: {
    session_id: "session_abc123",
    conversation_summary_hash: "sha256_xyz",
    source: "chatbot:discord_adapter",
    ip_address: "192.168.1.1", // For audit trail
  },
});
```

**Validation**:

```javascript
db.createCollection("memory_events", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "_id",
        "event_type",
        "timestamp",
        "subject_id",
        "tenant_id",
        "operation",
        "result",
      ],
    },
  },
});
```

**Indexes**:

```javascript
// Lookup by subject + tenant
db.memory_events.createIndex({ subject_id: 1, tenant_id: 1 });

// Time-series queries
db.memory_events.createIndex({ timestamp: -1 });

// Event type tracking
db.memory_events.createIndex({ event_type: 1, timestamp: -1 });

// Compound: subject + event type + time
db.memory_events.createIndex(
  {
    subject_id: 1,
    event_type: 1,
    timestamp: -1,
  },
  { name: "subject_event_time_index" }
);

// Retention: auto-delete old events (2 years)
db.memory_events.createIndex(
  { timestamp: 1 },
  { expireAfterSeconds: 63072000 } // 2 years
);
```

---

## Python Type Definitions

### MemoryFact

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class MemoryFact:
    """A single memorable fact about a user."""

    fact: str                          # "Loves fettuccini"
    type: str                          # "USER_FACT"
    confidence: float                  # 0.60–1.0
    added_at: datetime                 # When added

    # Optional metadata
    last_confirmed_at: Optional[datetime] = None
    confirmation_count: int = 1
    source: str = "conversation_summary"
    source_hash: Optional[str] = None

    def __post_init__(self):
        """Validate fields."""
        if not 0.60 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.60–1.0, got {self.confidence}")
        if self.type not in ["USER_FACT", "USER_PATTERN", "SHARED_NARRATIVE"]:
            raise ValueError(f"Invalid type: {self.type}")
        if self.confirmation_count < 1:
            raise ValueError("confirmation_count must be >= 1")

    def is_active(self, decay_days: int = 30) -> bool:
        """Check if fact is still within decay window."""
        from datetime import datetime, timedelta
        age = (datetime.utcnow() - self.added_at).days
        return age <= decay_days

    def to_dict(self) -> dict:
        """Serialize to MongoDB document."""
        return {
            "fact": self.fact,
            "type": self.type,
            "confidence": self.confidence,
            "added_at": self.added_at,
            "last_confirmed_at": self.last_confirmed_at,
            "confirmation_count": self.confirmation_count,
            "source": self.source,
            "source_hash": self.source_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryFact":
        """Deserialize from MongoDB document."""
        return cls(**data)
```

### MemoryPattern

```python
@dataclass
class MemoryPattern:
    """An inferred behavioral pattern."""

    pattern: str                       # "Prefers step-by-step"
    type: str = "USER_PATTERN"
    confidence: float = 0.75
    added_at: Optional[datetime] = None

    last_observed: Optional[datetime] = None
    observation_count: int = 1
    source: str = "behavior_inference"

    def __post_init__(self):
        """Validate fields."""
        if self.type != "USER_PATTERN":
            raise ValueError("Pattern type must be USER_PATTERN")
        if not 0.60 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.60–1.0, got {self.confidence}")
        if self.added_at is None:
            self.added_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Serialize to MongoDB."""
        return {
            "pattern": self.pattern,
            "type": self.type,
            "confidence": self.confidence,
            "added_at": self.added_at,
            "last_observed": self.last_observed,
            "observation_count": self.observation_count,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryPattern":
        """Deserialize from MongoDB."""
        return cls(**data)
```

### CreativeProfile

```python
@dataclass
class CreativeProfile:
    """Complete subject memory profile."""

    memorable_facts: List[MemoryFact]
    patterns: List[MemoryPattern]
    narratives: List[MemoryNarrative]

    preferences: Dict[str, str]        # communication_style, detail_level, etc.
    domains: List[Dict[str, Any]]

    total_facts_lifetime: int = 0
    total_patterns_lifetime: int = 0
    total_narratives_lifetime: int = 0
    avg_confidence: float = 0.80
    learning_level: str = "intermediate"

    def active_facts(self, decay_days: int = 30) -> List[MemoryFact]:
        """Get facts within decay window."""
        return [f for f in self.memorable_facts if f.is_active(decay_days)]

    def high_confidence_facts(self, threshold: float = 0.80) -> List[MemoryFact]:
        """Get facts above confidence threshold."""
        return [f for f in self.memorable_facts if f.confidence >= threshold]

    def to_dict(self) -> dict:
        """Serialize to MongoDB."""
        return {
            "memorable_facts": [f.to_dict() for f in self.memorable_facts],
            "patterns": [p.to_dict() for p in self.patterns],
            "narratives": [n.to_dict() for n in self.narratives],
            "preferences": self.preferences,
            "domains": self.domains,
            "total_facts_lifetime": self.total_facts_lifetime,
            "total_patterns_lifetime": self.total_patterns_lifetime,
            "total_narratives_lifetime": self.total_narratives_lifetime,
            "avg_confidence": self.avg_confidence,
            "learning_level": self.learning_level,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CreativeProfile":
        """Deserialize from MongoDB."""
        return cls(
            memorable_facts=[MemoryFact.from_dict(f) for f in data.get("memorable_facts", [])],
            patterns=[MemoryPattern.from_dict(p) for p in data.get("patterns", [])],
            narratives=[MemoryNarrative.from_dict(n) for n in data.get("narratives", [])],
            preferences=data.get("preferences", {}),
            domains=data.get("domains", []),
            total_facts_lifetime=data.get("total_facts_lifetime", 0),
            total_patterns_lifetime=data.get("total_patterns_lifetime", 0),
            total_narratives_lifetime=data.get("total_narratives_lifetime", 0),
            avg_confidence=data.get("avg_confidence", 0.80),
            learning_level=data.get("learning_level", "intermediate"),
        )
```

---

## Query Patterns

### Get User Profile

```python
def get_user_profile(
    user_id: str,
    guild_id: str,
    db
) -> Optional[dict]:
    """Retrieve user profile from MongoDB."""
    return db.discord_profiles.find_one({
        "user_id": user_id,
        "guild_id": guild_id
    })
```

### Find High-Confidence Facts

```python
def get_high_confidence_facts(
    user_id: str,
    guild_id: str,
    threshold: float = 0.80,
    db = None
) -> List[dict]:
    """Get facts above confidence threshold."""
    profile = get_user_profile(user_id, guild_id, db)
    if not profile:
        return []

    return [
        fact for fact in profile["creative_profile"]["memorable_facts"]
        if fact["confidence"] >= threshold
    ]
```

### List Recent Events

```python
def get_memory_events(
    subject_id: str,
    tenant_id: str,
    limit: int = 50,
    db = None
) -> List[dict]:
    """Get recent memory events for audit trail."""
    return list(db.memory_events.find({
        "subject_id": subject_id,
        "tenant_id": tenant_id
    }).sort("timestamp", -1).limit(limit))
```

### Bulk Decay Query

```python
def find_profiles_needing_decay(
    guild_id: str,
    decay_threshold_hours: int = 12,
    db = None
) -> List[dict]:
    """Find profiles where decay is overdue."""
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(hours=decay_threshold_hours)

    return list(db.discord_profiles.find({
        "guild_id": guild_id,
        "last_decay_at": {"$lt": cutoff}
    }))
```

---

## Validation Constraints

### Confidence Ranges

```python
# USER_FACT
assert 0.80 <= fact.confidence <= 1.0

# USER_PATTERN
assert 0.75 <= pattern.confidence <= 1.0

# SHARED_NARRATIVE
assert 0.60 <= narrative.confidence <= 1.0
```

### Decay Windows

```python
DECAY_WINDOWS = {
    "USER_FACT": 30,          # days
    "USER_PATTERN": 14,       # days
    "SHARED_NARRATIVE": 7,    # days
}
```

### Type Enforcement

```python
VALID_TYPES = {
    "USER_FACT",
    "USER_PATTERN",
    "SHARED_NARRATIVE"
}
```

---

## Performance Characteristics

**Write Performance**:

- Single fact insert: 10–50 ms
- Batch insert (10 facts): 20–100 ms
- With WriteConcern(w="majority", j=True): +5–20 ms

**Read Performance**:

- Profile lookup (indexed): 1–5 ms
- Fact filtering: 5–20 ms
- Cache hit: <1 ms

**Storage Size**:

- Per-user profile: 10–100 KB
- 1M users: 10–100 GB (raw)
- With compression: 3–30 GB

---

## Migration Strategy

**Version 1.0 → v1.1**:

- Add `constraints` field (backward compatible)
- Existing documents auto-migrated on first read

**Version 1.0 → v2.0**:

- Change memory typing system (breaking change)
- Requires data migration script
- Run migration offline, validate, deploy

---

## Testing Data Model

**Unit Tests**:

- [ ] MemoryFact validates confidence range
- [ ] MemoryPattern validates type
- [ ] CreativeProfile serialization round-trip
- [ ] to_dict() produces valid MongoDB format
- [ ] from_dict() reconstructs object correctly

**Integration Tests**:

- [ ] Profile inserts to MongoDB
- [ ] Unique constraint enforced (user_id + guild_id)
- [ ] Indexes used for queries (explain plan)
- [ ] Event logging works
- [ ] Data validates against schema

**Example Test**:

```python
def test_memory_fact_validation():
    """Confirm MemoryFact validates confidence."""

    # Valid
    fact = MemoryFact(
        fact="Loves fettuccini",
        confidence=0.85,
        type="USER_FACT"
    )
    assert fact.confidence == 0.85

    # Invalid (too low)
    with pytest.raises(ValueError):
        MemoryFact(
            fact="Loves fettuccini",
            confidence=0.50,  # Below 0.60
            type="USER_FACT"
        )

    # Invalid (too high)
    with pytest.raises(ValueError):
        MemoryFact(
            fact="Loves fettuccini",
            confidence=1.5,   # Above 1.0
            type="USER_FACT"
        )
```

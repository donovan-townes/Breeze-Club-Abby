# Intent Architecture Design Document

**Maintenance Horizon:** 50+ Years | **Last Updated:** 2026-01-29 | **Version:** 2.0.0

---

## Executive Summary

Abby Bot uses a **two-layer intent classification architecture** to balance speed, accuracy, and maintainability:

1. **Abby Core Intent System** (Rule-based) - Fast prompt template selection and memory gating
2. **TDOS Intelligence Classifier** (LLM-based) - Dynamic capability routing and RAG triggering

This intentional separation serves different purposes and prevents architectural drift through a **shared capability contract**.

---

## Architecture Overview

```python
┌─────────────────────────────────────────────────────────┐
│                    User Message                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │   Abby Core Intent System   │
         │   (Rule-based, <1ms)        │
         │   Location: abby_core/llm/  │
         └──────────────┬──────────────┘
                        │
                        ├─→ Prompt Template Selection
                        ├─→ Memory Injection Policy
                        └─→ Context Assembly Hints
                        │
                        ▼
         ┌─────────────────────────────┐
         │ TDOS Intelligence Classifier │
         │   (LLM-based, <100ms)       │
         │   Location: tdos_intelligence│
         └──────────────┬──────────────┘
                        │
                        ├─→ RAG Triggering
                        ├─→ Memory System Activation
                        ├─→ Tool Selection
                        └─→ Priority Classification
                        │
                        ▼
         ┌─────────────────────────────┐
         │  Shared Capability Contract  │
         │    INTENT_CAPABILITIES       │
         │  (Prevents Drift)            │
         └─────────────────────────────┘
```python

---

## Layer 1: Abby Core Intent System

### Purpose
Fast, rule-based classification for prompt engineering and memory policies.

### Location

- [abby_core/llm/intent.py](abby_core/llm/intent.py)
- [abby_core/discord/adapters/intent.py](abby_core/discord/adapters/intent.py) (Discord adapter)

### Intent Categories

| Intent | Purpose | Memory Injection | Devlog Injection | Example |
| -------- | --------- | ------------------ | ------------------ | --------- |
| `CASUAL_CHAT` | Greetings, small talk | ❌ No | ❌ No | "hey how are you" |
| `CREATIVE_ASSIST` | Music, art, writing | ✅ Yes | ❌ No | "help me mix this track" |
| `TASK_REQUEST` | Actionable requests | ✅ Yes | ❌ No | "remind me to check inventory" |
| `CONFIG_ADMIN` | Bot configuration | ✅ Yes | ❌ No | "set my timezone to PST" |
| `ANALYSIS_EXTRACTION` | Data analysis | ✅ Yes | ❌ No | "what's our XP trend" |
| `META_SYSTEM` | Self-referential | ✅ Yes | ✅ Yes | "what's under the hood" |

### Rule Patterns

```python
INTENT_PATTERNS = {
    Intent.CASUAL_CHAT: [
        r"\b(hi | hello | hey | sup | what'?s up)\b",
        r"^.{1,20}$",  # Very short = likely casual
    ],
    Intent.META_SYSTEM: [
        r"\b(under the hood | how (are | were) you built)\b",
        r"\b(what'?s new | changelog | dev ?log)\b",
    ],
    # ... more patterns
}
```python

### Key Functions

### `classify_intent(message: str) -> Intent`

- Returns: Intent enum
- Performance: <1ms (regex matching)
- Fallback: `CASUAL_CHAT` if no match

### `route_intent_to_action(intent: Intent, context: ConversationContext) -> dict`

- Returns: `{"use_llm": bool, "needs_memory": bool, "needs_devlog": bool}`
- Used by: Context assembly pipeline

### Memory Injection Policy

```python
## Memory allowed intents (whitelist)
MEMORY_ALLOWED_INTENTS = {
    Intent.CREATIVE_ASSIST,
    Intent.TASK_REQUEST,
    Intent.CONFIG_ADMIN,
    Intent.ANALYSIS_EXTRACTION,
    Intent.META_SYSTEM,
}

## Memory MUST be skipped (safety list)
UNSAFE_MEMORY_INTENTS = {
    Intent.CASUAL_CHAT,  # No memory needed for "hey"
}
```python

### Why This Matters:

- Casual chat doesn't need memory → saves tokens, reduces latency
- Prevents prompt pollution with irrelevant context
- Memory injection only when intent justifies it

---

## Layer 2: TDOS Intelligence Classifier

### Purpose
LLM-powered classification for dynamic routing and capability decisions.

### Location

- [tdos_intelligence/intent/classifier.py](tdos_intelligence/intent/classifier.py)

### Intent Categories

| Intent | RAG | Memory Read | Memory Write | Tools | Priority |
| -------- | ----- | ------------- | -------------- | ------- | ---------- |
| `GENERAL_CHAT` | ❌ | ❌ | ❌ | ❌ | Interactive |
| `KNOWLEDGE_QUERY` | ✅ | ❌ | ❌ | ❌ | Interactive |
| `MEMORY_RECALL` | ❌ | ✅ | ❌ | ❌ | Interactive |
| `PERSONA_ACTION` | ❌ | ❌ | ❌ | ✅ | Interactive |
| `META_CONTROL` | ❌ | ❌ | ❌ | ❌ | System |

### Capability Contract

**Shared Definition** (prevents drift):

```python
## tdos_intelligence/intent/classifier.py
INTENT_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "GENERAL_CHAT": {
        "needs_rag": False,
        "needs_memory_read": False,
        "needs_memory_write": False,
        "needs_tools": False,
        "needs_chat": True,
        "priority": "interactive",
    },
    "KNOWLEDGE_QUERY": {
        "needs_rag": True,
        "needs_memory_read": False,
        "needs_memory_write": False,
        "needs_tools": False,
        "priority": "interactive",
    },
    # ... more capabilities
}
```python

### Contract Enforcement:

- Orchestrator reads `INTENT_CAPABILITIES` to determine processing path
- If `needs_rag=True` → trigger RAG pipeline
- If `needs_tools=True` → skip LLM, route to tool executor
- Single source of truth prevents capability drift

### Classification Flow

```python
## Example usage
from tdos_intelligence.intent import classify_intent

result = classify_intent("What are the rules about XP?")
## IntentResult(
##     intent="KNOWLEDGE_QUERY",
##     confidence="high",
##     capabilities={"needs_rag": True, ...}
## )
```python

### Performance Target

- **<100ms** for classification (local LLM)
- Falls back to `GENERAL_CHAT` if model unavailable

---

## Why Two Layers?

### Design Rationale

| Concern | Solution |
| --------- | ---------- |
| **Speed** | Layer 1 (regex) handles 80% of cases in <1ms |
| **Accuracy** | Layer 2 (LLM) handles ambiguous cases with context |
| **Cost** | Layer 1 is free; Layer 2 only for complex queries |
| **Maintainability** | Rule patterns are explicit and auditable |
| **Extensibility** | LLM layer adapts to new patterns without code changes |

### Example Flow

**User:** "hey what's the current season?"

1. **Layer 1 (Abby Core):**
   - Matches `r"\b(hi | hello | hey)\b"` → `CASUAL_CHAT`
   - Sets: `needs_memory=False`, `needs_devlog=False`
   - Prompt template: Casual greeting style

1. **Layer 2 (TDOS):**
   - Detects "what's the current season" (question pattern)
   - Classifies as `KNOWLEDGE_QUERY`
   - Sets: `needs_rag=True` (trigger rules lookup)

1. **Orchestrator:**
   - Reads both classifications
   - Uses Abby intent for prompt template (casual style)
   - Uses TDOS intent for RAG triggering (fetch season rules)
   - Combines: Casual tone + factual answer from RAG

---

## Anti-Pattern: Don't Consolidate!

### ❌ Wrong Approach
"We have two intent systems, let's merge them into one."

### ✅ Correct Understanding
They serve **different purposes** and use **different trade-offs**:

| Aspect | Abby Core | TDOS Intelligence |
| -------- | ----------- | ------------------- |
| **Speed** | <1ms | <100ms |
| **Method** | Regex rules | LLM classification |
| **Purpose** | Prompt engineering | Capability routing |
| **Scope** | Memory/devlog policy | RAG/tools/priority |
| **Cost** | Free | Token cost |
| **Accuracy** | 80% (simple) | 95% (complex) |

### Contract Prevents Drift

**Problem:** Two systems could define capabilities differently.

**Solution:** Shared `INTENT_CAPABILITIES` contract:
```python
## Both systems reference this single source of truth
from tdos_intelligence.intent.classifier import INTENT_CAPABILITIES

## Orchestrator uses this to make routing decisions
capabilities = INTENT_CAPABILITIES[intent]
if capabilities.get("needs_rag"):
    results = rag_handler.query(...)
```python

---

## 50-Year Maintenance Guidelines

### Adding New Intents

#### Step 1: Add to Abby Core (if simple pattern exists)
```python
## abby_core/llm/intent.py
class Intent(str, Enum):
    # ... existing
    NEW_INTENT = "new_intent"

INTENT_PATTERNS = {
    # ... existing
    Intent.NEW_INTENT: [
        r"\b(keyword | pattern)\b",
    ],
}

## Set memory policy
MEMORY_ALLOWED_INTENTS.add(Intent.NEW_INTENT)
```python

#### Step 2: Add to TDOS Intelligence (if needs LLM)
```python
## tdos_intelligence/intent/classifier.py
IntentType = Literal[
    # ... existing
    "NEW_INTENT",
]

INTENT_CAPABILITIES["NEW_INTENT"] = {
    "needs_rag": False,
    "needs_memory_read": False,
    "needs_tools": True,  # Example: tool-based intent
    "priority": "interactive",
}
```python

#### Step 3: Update Orchestrator (if new capability)
```python
## tdos_intelligence/orchestrator.py
if capabilities.get("needs_new_feature"):
    # Handle new capability
    result = new_feature_handler(...)
```python

### Monitoring Capability Drift

### Warning Signs:

- Abby Core routes to memory, but TDOS says `needs_memory_read=False`
- Intent classified differently by two layers
- Orchestrator ignores capability flags

### Prevention:

- Add tests validating `INTENT_CAPABILITIES` consistency
- Log when Layer 1 and Layer 2 disagree
- Annual audit of intent patterns vs. actual usage

### Deprecating Old Intents

**DON'T:** Remove immediately (breaks backward compatibility)

**DO:** Follow deprecation path:
1. Mark as deprecated in comments
2. Log warning when classified
3. Add grace period (6 months minimum)
4. Remove after grace period + announcement

---

## Testing Strategy

### Unit Tests

```python
## tests/test_intent_classification.py
def test_abby_core_intent():
    """Rule-based classification works."""
    assert classify_intent("hey") == Intent.CASUAL_CHAT
    assert classify_intent("what's new?") == Intent.META_SYSTEM

def test_tdos_intelligence_intent():
    """LLM classification works."""
    result = classify_intent("What are the XP rules?")
    assert result.intent == "KNOWLEDGE_QUERY"
    assert result.capabilities["needs_rag"] is True

def test_capability_contract():
    """Shared capabilities prevent drift."""
    from tdos_intelligence.intent.classifier import INTENT_CAPABILITIES
    
    # All intents must define these keys
    required_keys = {"needs_rag", "priority"}
    for intent, caps in INTENT_CAPABILITIES.items():
        assert required_keys.issubset(caps.keys()), f"Missing keys in {intent}"
```python

### Integration Tests

```python
def test_intent_layering_e2e():
    """Both layers work together."""
    # Layer 1: Abby Core routes to casual prompt
    # Layer 2: TDOS triggers RAG
    # Result: Casual style + factual answer
    
    response = process_message(
        message="hey what's the current season?",
        guild_id=123,
        user_id=456,
    )
    
    assert "season" in response.lower()  # Factual answer
    assert response.tone == "casual"  # Style from Layer 1
```python

---

## Performance Baselines

| Metric | Expected | Warning | Critical |
| -------- | ---------- | --------- | ---------- |
| **Layer 1 (Abby Core)** | <1ms | >5ms | >10ms |
| **Layer 2 (TDOS)** | <100ms | >200ms | >500ms |
| **Combined Latency** | <101ms | >205ms | >510ms |
| **Cache Hit Rate** | >90% | <80% | <70% |

### Monitoring:
```python
## Log intent classification timing
logger.debug(
    f"[Intent] Layer1={layer1_ms}ms Layer2={layer2_ms}ms "
    f"intent_abby={abby_intent} intent_tdos={tdos_intent}"
)
```python

---

## Troubleshooting

### Problem: Intent Mismatch

**Symptom:** Layer 1 says `CASUAL_CHAT`, Layer 2 says `KNOWLEDGE_QUERY`

### Diagnosis:
```python
## Check both classifications
abby_intent = classify_intent(message)  # Layer 1
tdos_result = classify_intent_tdos(message)  # Layer 2

if abby_intent != tdos_result.intent:
    logger.warning(
        f"Intent mismatch: abby={abby_intent} tdos={tdos_result.intent} "
        f"message='{message[:50]}...'"
    )
```python

### Solution:

- If Layer 1 is wrong: Update rule patterns
- If Layer 2 is wrong: Retrain classifier or adjust prompts
- If both valid: This is expected (different purposes)

### Problem: Memory Not Injecting

**Symptom:** `META_SYSTEM` intent but no memory in context

### Diagnosis:
```python
## Check memory policy
intent = classify_intent(message)
if intent in UNSAFE_MEMORY_INTENTS:
    # Memory explicitly blocked
    logger.debug(f"Memory blocked for intent={intent}")
```python

### Solution:

- Verify intent is in `MEMORY_ALLOWED_INTENTS`
- Check intent isn't in `UNSAFE_MEMORY_INTENTS`
- Ensure orchestrator respects capability flags

### Problem: RAG Not Triggering

**Symptom:** Question about rules, but no RAG results

### Diagnosis:
```python
## Check TDOS capabilities
result = classify_intent(message)
if not result.capabilities.get("needs_rag"):
    logger.warning(
        f"RAG not triggered: intent={result.intent} "
        f"capabilities={result.capabilities}"
    )
```python

### Solution:

- Update `INTENT_CAPABILITIES` to set `needs_rag=True`
- Or: User's question is ambiguous, rephrase query

---

## Critical Files Reference

| File | Purpose | Maintenance Frequency |
| ------ | --------- | ---------------------- |
| [abby_core/llm/intent.py](abby_core/llm/intent.py) | Layer 1 rules | Monthly (add patterns) |
| [tdos_intelligence/intent/classifier.py](tdos_intelligence/intent/classifier.py) | Layer 2 LLM | Quarterly (retrain model) |
| [tdos_intelligence/intent/classifier.py](tdos_intelligence/intent/classifier.py#L32-L69) | Capability contract | As needed (new capabilities) |
| [tdos_intelligence/orchestrator.py](tdos_intelligence/orchestrator.py) | Routing logic | As needed (new features) |
| [abby_core/generation/context_factory.py](abby_core/generation/context_factory.py) | Memory policy enforcement | Rarely (stable) |

---

## Version History

| Version | Date | Changes |
| --------- | ------ | --------- |
| 2.0.0 | 2026-01-29 | Initial documentation of two-layer architecture |

---

## Summary

- **Two layers are intentional:** Rule-based (fast) + LLM-based (accurate)
- **Shared contract prevents drift:** `INTENT_CAPABILITIES` is single source of truth
- **Different purposes:** Layer 1 = prompts/memory, Layer 2 = RAG/tools/routing
- **Performance optimized:** <1ms for simple, <100ms for complex
- **50-year maintainable:** Clear separation, explicit contracts, comprehensive tests

**Do NOT consolidate these systems.** They serve different purposes and use different trade-offs optimized for their respective goals.

# Extraction Rules & Validation

**Version**: 1.0  
**Purpose**: Formalize fact extraction, typing, validation, and anti-hallucination strategies  
**TDOS Analog**: Deterministic input transformation (stateless, reproducible)

---

## Overview

The extraction system converts unstructured conversation summaries into typed, validated memories. It uses LLM-assisted extraction with deterministic validation to prevent hallucinations.

**Core Principle**: Extract facts from conversation summaries, ground each fact in the source, and apply confidence-based gating.

---

## Extraction Pipeline

```
Conversation Summary
        ↓
   [LLM Extract]  ← Identify facts, patterns, narratives
        ↓
  [Validate Against Summary]  ← Confirm grounding in source
        ↓
   [Apply Type Rules]  ← Classify by confidence threshold
        ↓
   [Confidence Gate]  ← Only store if meets minimum threshold
        ↓
   [Memory Storage]  ← Write to MongoDB with WriteConcern
        ↓
   [Cache Invalidation]  ← Notify retrieval system of update
```

---

## LLM Extraction Prompt

**Input**: Conversation summary (300–2000 tokens)

**Prompt Template**:

```
Extract memorable facts, patterns, and narratives from this conversation.

Guidelines:
1. Extract ONLY facts mentioned explicitly by the user
2. Patterns: inferred behaviors or tendencies (e.g., "asks step-by-step questions")
3. Narratives: shared context or continuity (e.g., "been using FL Studio since 2020")
4. Assign confidence: 0.60–0.99 (how certain are you?)
5. Categorize each into: USER_FACT | USER_PATTERN | SHARED_NARRATIVE

Format your response as JSON:
{
  "extractions": [
    {
      "text": "The fact or pattern",
      "type": "USER_FACT|USER_PATTERN|SHARED_NARRATIVE",
      "confidence": 0.85,
      "reasoning": "Why confident?"
    },
    ...
  ]
}

Conversation Summary:
---
{summary}
---

Extract:
```

**LLM Used**: GPT-4 Turbo (or compatible)

**Extraction Example**:

```json
{
  "extractions": [
    {
      "text": "Loves fettuccini pasta",
      "type": "USER_FACT",
      "confidence": 0.95,
      "reasoning": "User explicitly said 'Fettuccini is my favorite pasta'"
    },
    {
      "text": "Prefers step-by-step explanations",
      "type": "USER_PATTERN",
      "confidence": 0.8,
      "reasoning": "Asked for 'step by step' breakdown twice in conversation"
    },
    {
      "text": "Been chatting since 2019",
      "type": "SHARED_NARRATIVE",
      "confidence": 0.9,
      "reasoning": "User mentioned 'we've been talking for like 5-6 years'"
    }
  ]
}
```

---

## Type Rules & Thresholds

### USER_FACT

**Definition**: Explicit, factual statement about the user (preferences, experiences, facts)
**Confidence Threshold**: ≥ 0.80
**Decay Window**: 30 days
**Authority**: Never absolute; always advisory
**Example**: "Loves fettuccini", "Works in radiology", "Plays guitar"

**Extraction Rules**:

- ✅ User said it explicitly
- ✅ Current/ongoing preference
- ✅ Factual claim (not opinion)
- ❌ Hypothetical ("would like to try")
- ❌ Vague preference ("kind of likes")
- ❌ Opinion masquerading as fact ("best pasta")

**Confidence Scoring**:

- 0.95: "I love X" (explicit, repeated)
- 0.85: "My favorite is X" (clear preference)
- 0.75: "I really like X" (enthusiastic but singular mention)
- 0.65: "I enjoy X" (positive but casual)
- <0.80: Reject (below threshold)

---

### USER_PATTERN

**Definition**: Inferred behavior or tendency (how they communicate, what they prefer)
**Confidence Threshold**: ≥ 0.75
**Decay Window**: 14 days
**Authority**: Suggestion only; can be overridden by user
**Example**: "Prefers detailed explanations", "Asks questions before diving in", "Uses technical language"

**Extraction Rules**:

- ✅ Observable from communication style
- ✅ Consistent across multiple messages
- ✅ Behavioral tendency (not emotional state)
- ❌ One-time action ("asked for X once")
- ❌ Transient mood ("seems tired today")
- ❌ Ungrounded speculation ("probably likes X")

**Confidence Scoring**:

- 0.90: Pattern observed 3+ times, clear consistency
- 0.80: Pattern observed 2 times, strong signal
- 0.70: Pattern inferred from single detailed interaction
- 0.60: Weak pattern, needs confirmation
- <0.75: Reject (below threshold) or log as proposal

**Confidence Gate Example**:

```python
if confidence >= 0.80:
    # Apply pattern automatically
    apply_pattern_update(pattern_name, confidence)
elif 0.75 <= confidence < 0.80:
    # Log as proposal, don't auto-apply
    log_pattern_proposal(pattern_name, confidence, reasoning)
else:
    # Discard
    discard(pattern_name)
```

---

### SHARED_NARRATIVE

**Definition**: Shared context, continuity, or warm context (not factual authority)
**Confidence Threshold**: ≥ 0.60
**Decay Window**: 7 days
**Authority**: Never; purely for warmth
**Example**: "Been chatting since 2019", "Remember our conversation about music?", "You helped me with that project"

**Extraction Rules**:

- ✅ Shared memory or experience
- ✅ Continuity signal ("remember when...")
- ✅ Connection context ("we've worked together")
- ❌ Factual claim ("you told me X is true")
- ❌ Authority assertion ("you're an expert")
- ❌ Binding future behavior ("you promised")

**Confidence Scoring**:

- 0.95: Confirmed shared history (explicit mention with date)
- 0.85: Strong narrative continuity (clear reference to past)
- 0.70: Implied shared context (context clue)
- 0.60: Weak narrative (could be shared)
- <0.60: Too uncertain, discard

**Warmth Usage Example**:

```python
# ✅ Good: narrative as warmth
"Since we've been chatting since 2019, I remember you love a good debate."

# ❌ Bad: narrative as authority
"We established in 2019 that you prefer formal communication. Comply."
```

---

## Validation Against Summary

**Core Rule**: Every fact must be grounded in the conversation summary.

**Validation Algorithm**:

```python
def validate_fact_against_summary(fact: str, summary: str) -> bool:
    """Confirm fact is grounded in summary."""

    # Step 1: Exact substring match
    if fact in summary or fact.lower() in summary.lower():
        return True

    # Step 2: Key phrase matching
    key_phrases = extract_key_phrases(fact)
    if all_phrases_in_summary(key_phrases, summary):
        return True

    # Step 3: Semantic similarity (embedding-based)
    fact_embedding = embed(fact)
    summary_embedding = embed(summary)

    similarity = cosine_similarity(fact_embedding, summary_embedding)
    if similarity > 0.85:  # High confidence match
        return True

    # Step 4: Reject if not grounded
    return False
```

**Validation Examples**:

✅ **PASS**:

```
Summary: "User said: I absolutely love fettuccini pasta, especially with alfredo sauce."
Fact: "Loves fettuccini"
Validation: Substring "love fettuccini" found → PASS
```

✅ **PASS**:

```
Summary: "Asked for step-by-step explanation of the algorithm."
Pattern: "Prefers step-by-step explanations"
Validation: Key phrases "step-by-step" + "explanation" found → PASS
```

❌ **FAIL**:

```
Summary: "We discussed fettuccini briefly."
Fact: "Absolutely loves fettuccini pasta with truffle oil"
Validation: "loves" not in summary, "truffle oil" not mentioned → FAIL
(Too specific; not grounded)
```

❌ **FAIL**:

```
Summary: "User mentioned liking pasta."
Fact: "Loves fettuccini specifically"
Validation: "fettuccini" not mentioned in summary → FAIL
(Overgeneralized)
```

---

## Anti-Hallucination Strategy

**Problem**: LLMs can generate plausible-sounding facts not actually in the conversation.

**Defense Layers**:

### Layer 1: Validation Against Summary

```python
# Every extracted fact must pass validation
if not validate_fact_against_summary(fact, summary):
    reject_fact(fact, reason="not_grounded_in_summary")
```

### Layer 2: Confidence Gating

```python
# Only store facts above confidence threshold
if fact.confidence < confidence_threshold:
    reject_fact(fact, reason="low_confidence")
```

### Layer 3: Type Rule Enforcement

```python
# Enforce type-specific rules
if fact.type == "USER_FACT" and fact.confidence < 0.80:
    reject_fact(fact, reason="fact_below_threshold")
```

### Layer 4: Semantic Sanity Check

```python
# Reject obviously nonsensical extractions
if is_nonsensical(fact):
    reject_fact(fact, reason="semantically_invalid")
```

**Example Rejection Log**:

```
[EXTRACTION] Processing summary for user:12345
[EXTRACT] Found 5 candidate extractions
[VALIDATE] Fact "loves fettuccini" → validation: PASS (0.95 confidence)
[VALIDATE] Fact "hates broccoli" → validation: FAIL (not in summary)
[VALIDATE] Pattern "prefers detailed explanations" → validation: PASS (0.80 confidence)
[VALIDATE] Narrative "been chatting since 2019" → validation: PASS (0.90 confidence)
[GATE] Fact 1/1 passed confidence gate (0.95 >= 0.80)
[GATE] Pattern 1/1 passed confidence gate (0.80 >= 0.75)
[GATE] Narrative 1/1 passed confidence gate (0.90 >= 0.60)
[STORE] Writing 3 memories to MongoDB
[RESULT] 3/5 extractions stored successfully
```

---

## Confidence Scoring Algorithm

**Input**: Extracted text, category, reasoning from LLM

**Scoring Factors**:

```python
def score_confidence(
    extraction: dict,  # {text, type, reasoning, explicit}
    summary: str
) -> float:
    """Compute confidence score (0.0–1.0)."""

    score = 0.0

    # Factor 1: Explicit mention (0.0–0.3)
    if is_exact_quote(extraction["text"], summary):
        score += 0.30
    elif key_phrases_present(extraction["text"], summary):
        score += 0.20
    elif semantic_similarity(extraction["text"], summary) > 0.85:
        score += 0.10

    # Factor 2: Repetition (0.0–0.2)
    repetition_count = count_mentions(extraction["text"], summary)
    if repetition_count >= 3:
        score += 0.20
    elif repetition_count == 2:
        score += 0.10
    elif repetition_count == 1:
        score += 0.00

    # Factor 3: Consistency with known facts (0.0–0.2)
    known_facts = fetch_subject_facts()
    if is_consistent_with_known(extraction["text"], known_facts):
        score += 0.20
    elif contradicts_known(extraction["text"], known_facts):
        score -= 0.25  # Downgrade contradictions

    # Factor 4: Type credibility (0.0–0.3)
    if extraction["type"] == "USER_FACT" and extraction["explicit"]:
        score += 0.30
    elif extraction["type"] == "USER_PATTERN" and repetition_count >= 2:
        score += 0.20
    elif extraction["type"] == "SHARED_NARRATIVE" and contextual_clue_found():
        score += 0.15

    # Clamp to valid range
    return max(0.0, min(1.0, score))
```

**Confidence Score Table**:

| Score     | Meaning            | Action                                                  | Example                               |
| --------- | ------------------ | ------------------------------------------------------- | ------------------------------------- |
| 0.95–1.0  | Explicit, repeated | Store immediately                                       | "I love fettuccini" (repeated 2x)     |
| 0.85–0.94 | Explicit, clear    | Store                                                   | "My favorite is X" (said once, clear) |
| 0.80–0.84 | Clear but singular | Store (USER_FACT threshold)                             | "I really like X" (said clearly once) |
| 0.75–0.79 | Inferred pattern   | Log as proposal (below USER_FACT, at PATTERN threshold) | "Prefers detailed explanations"       |
| 0.60–0.74 | Weak signal        | Log as narrative only                                   | "Seems interested in X"               |
| <0.60     | Uncertain          | Reject                                                  | "Might like X?"                       |

---

## Type Classification Rules

**Decision Tree**:

```
Is the user stating a preference/fact about themselves explicitly?
├─ YES → Is confidence >= 0.80?
│        └─ YES → USER_FACT
│        └─ NO  → below threshold, reject
├─ NO → Is this an inferred behavioral pattern?
         ├─ YES → Is confidence >= 0.75?
         │        └─ YES → USER_PATTERN
         │        └─ NO  → below threshold, reject
         └─ NO → Is this a shared context or narrative?
                 └─ YES → Is confidence >= 0.60?
                         └─ YES → SHARED_NARRATIVE
                         └─ NO  → reject
```

---

## Practical Extraction Examples

### Example 1: Strong Fact

**Summary**:

```
User: "I absolutely love fettuccini. Seriously, it's my favorite pasta.
The creamy alfredo sauce is just perfect. I make it at home all the time."
```

**Extraction Process**:

```json
{
  "text": "Loves fettuccini with alfredo sauce",
  "type": "USER_FACT",
  "confidence": 0.95,
  "reasoning": "Explicitly stated 'absolutely love', repeated preference",
  "validation": "PASS (direct quote + repetition)",
  "scoring": {
    "exact_quote": 0.3,
    "repetition": 0.2,
    "consistency": 0.2,
    "type_credibility": 0.25,
    "total": 0.95
  }
}
```

**Result**: ✅ **STORED** as USER_FACT (0.95 >= 0.80)

---

### Example 2: Inferred Pattern

**Summary**:

```
User asked: "Can you break this down step by step?"
Later: "Could you walk me through the algorithm step by step?"
Requested detailed explanation with examples.
```

**Extraction Process**:

```json
{
  "text": "Prefers step-by-step explanations",
  "type": "USER_PATTERN",
  "confidence": 0.85,
  "reasoning": "Requested 'step by step' twice, clear communication preference",
  "validation": "PASS (key phrases present, repetition evident)",
  "scoring": {
    "key_phrases": 0.2,
    "repetition": 0.1,
    "consistency": 0.2,
    "type_credibility": 0.35,
    "total": 0.85
  }
}
```

**Result**: ✅ **STORED** as USER_PATTERN (0.85 >= 0.75)

---

### Example 3: Below-Threshold Pattern

**Summary**:

```
User asked: "Can you explain this concept?"
```

**Extraction Process**:

```json
{
  "text": "Prefers conceptual explanations",
  "type": "USER_PATTERN",
  "confidence": 0.65,
  "reasoning": "Asked for explanation once, not enough repetition",
  "validation": "PASS (concept mentioned)",
  "scoring": {
    "key_phrases": 0.2,
    "repetition": 0.0, // Only once
    "consistency": 0.2,
    "type_credibility": 0.25,
    "total": 0.65
  }
}
```

**Result**: ❌ **REJECTED** as pattern (0.65 < 0.75)  
**Logged**: Pattern proposal (not auto-applied)

---

### Example 4: Hallucination Attempt

**Summary**:

```
We discussed music production in FL Studio.
```

**LLM Extracts**:

```json
{
  "text": "Works as a professional FL Studio producer",
  "type": "USER_FACT",
  "confidence": 0.7,
  "reasoning": "Discussed FL Studio extensively"
}
```

**Validation**:

```
is_exact_quote("Works as professional FL Studio producer", summary) → FALSE
key_phrases_present(...) → FALSE ("professional" not mentioned)
semantic_similarity(...) → 0.62 (too low, < 0.85)
validation_score: 0.10 (only semantic match, weak)
confidence_adjusted: 0.70 * 0.10/0.30 = 0.23
```

**Result**: ❌ **REJECTED** as hallucination  
**Reason**: Not grounded in summary; "professional" and "works as" not mentioned

---

## Rejection Logging

**Why Log Rejections?**:

1. Understand what LLM tried to extract
2. Spot patterns in extraction failures
3. Refine prompts based on rejection reasons
4. Audit extraction quality

**Rejection Log Schema**:

```python
{
    "timestamp": "2025-01-15T10:30:45Z",
    "subject_id": "USER:246030816692404234",
    "tenant_id": "TENANT:BreezeCrew",
    "rejection_reason": "confidence_below_threshold|not_grounded_in_summary|hallucination|type_rule_violation",
    "extracted_text": "Text that was rejected",
    "confidence_score": 0.65,
    "threshold": 0.75,
    "type": "USER_PATTERN|USER_FACT|SHARED_NARRATIVE",
    "validation_details": {
        "exact_match": False,
        "key_phrases": True,
        "semantic_similarity": 0.62,
        "reason": "semantic similarity below 0.85 threshold"
    }
}
```

**Aggregation Example**:

```
[REJECTION SUMMARY] Last 100 extractions
  - Below threshold: 24 (24%)
  - Not grounded: 8 (8%)
  - Hallucination: 3 (3%)
  - Accepted: 65 (65%)

[TRENDING] Most common rejection type:
  - USER_PATTERN with confidence 0.65–0.74 (needs 0.75+)
  - Recommendation: Refine extraction prompt to be stricter on pattern confidence
```

---

## Testing Extraction Quality

**Unit Tests**:

- [ ] Exact quote validation works
- [ ] Key phrase matching works
- [ ] Semantic similarity computed correctly
- [ ] Confidence scoring produces valid ranges
- [ ] Type classification correct
- [ ] Hallucinations rejected

**Integration Tests**:

- [ ] End-to-end extraction pipeline
- [ ] Facts stored in MongoDB
- [ ] Cache invalidated after write
- [ ] Rejection logging works
- [ ] Confidence gates enforced

**Example Test**:

```python
def test_extraction_hallucination_rejection():
    """Confirm hallucinations are rejected."""
    summary = "We discussed music production."

    # Simulate LLM extraction
    extraction = {
        "text": "Works as professional producer",
        "type": "USER_FACT",
        "confidence": 0.70,
        "explicit": False
    }

    # Validate
    is_valid = validate_fact_against_summary(extraction["text"], summary)
    assert not is_valid, "Hallucination should be rejected"

    # Score confidence
    score = score_confidence(extraction, summary)
    assert score < 0.80, "Confidence should be lowered by failed validation"

    # Store should be rejected
    with pytest.raises(RejectionError):
        store_fact(extraction)
```

---

## Confidence Decay (Separate Document)

Confidence naturally decays over time. See [ARCHITECTURE.md](ARCHITECTURE.md#decay-rules) for decay windows and application logic.

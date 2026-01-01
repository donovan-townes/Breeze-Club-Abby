"""
LLM-based Memory Extraction System
Extracts memorable facts and patterns from conversation summaries.

Memory Classes (explicit types):
- USER_FACT: Durable facts about the user (goals, tools, expertise, preferences)
- USER_PATTERN: Inferred traits (communication style, learning level, domains)
- SHARED_NARRATIVE: Warm persona memories (not factual, opt-out, never used for inference)
"""
import json
import re
from typing import Dict, List, Any, Optional, Literal
from abby_core.observability.logging import setup_logging, logging
# Import conversation handler (renamed from chat_openai)
import abby_core.llm.conversation as chat_openai

setup_logging()
logger = logging.getLogger(__name__)

# Memory type constants
MemoryType = Literal["USER_FACT", "USER_PATTERN", "SHARED_NARRATIVE"]


def validate_fact_against_summary(fact_text: str, summary: str) -> bool:
    """
    Hard hallucination check: Ensure key words from fact appear in summary.
    Prevents LLM from inventing facts not actually mentioned.
    
    Args:
        fact_text: The extracted fact text
        summary: The original summary to validate against
        
    Returns:
        True if fact is grounded in summary, False if likely hallucinated
    """
    # Extract key nouns/verbs from fact (simple approach)
    # Words > 3 chars, exclude common stop words
    stop_words = {'the', 'and', 'that', 'this', 'with', 'from', 'about', 'for', 'user', 'is', 'are', 'was', 'were'}
    words = [w.lower() for w in re.findall(r'\b\w+\b', fact_text) if len(w) > 3 and w.lower() not in stop_words]
    
    if not words:
        return False  # Can't validate empty fact
    
    summary_lower = summary.lower()
    
    # At least 50% of key words must appear in summary
    matches = sum(1 for w in words if w in summary_lower)
    match_ratio = matches / len(words) if words else 0
    
    if match_ratio < 0.5:
        logger.debug(f"[🧠] Fact validation failed (only {match_ratio:.0%} match): {fact_text[:50]}")
        return False
    
    return True


def extract_facts_from_summary(summary: str, user_id: str, conversation_exchanges: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, Any]]:
    """
    Use LLM to extract discrete memorable facts about the USER from conversation summary.
    
    Args:
        summary: The conversation summary text (source of truth)
        user_id: User ID for context
        conversation_exchanges: Optional raw exchanges (used only for LLM context, not extraction source)
        
    Returns:
        List of fact dicts with {text, type, confidence, category, source}
    """
    if not summary or len(summary.strip()) < 20:
        logger.debug(f"[🧠] Summary too short to extract facts: {len(summary)} chars")
        return []
    
    # NOTE: We extract ONLY from summary, not from raw exchanges
    # This ensures consistency and reduces hallucination
    
    extraction_prompt = f"""Analyze this conversation summary and extract ONLY memorable facts about THE USER (not the assistant).

CONVERSATION SUMMARY:
{summary}

CRITICAL RULES (must follow exactly):
- Extract ONLY facts explicitly mentioned about THE USER
- DO NOT extract facts about what Abby/Kiki (the assistant) said or does
- DO NOT infer facts not directly stated
- DO NOT hallucinate details

Extract USER facts that are:
✅ Personal statements (goals, projects, interests, background)
✅ Tools/Software they use (DAWs, languages, frameworks, software)
✅ Preferences or dislikes
✅ Skills or expertise mentioned
✅ Important life events or milestones
✅ Explicit mentions of what they like/dislike

DO NOT extract:
❌ What the assistant said or likes
❌ Assistant's preferences, activities, or capabilities
❌ Generic pleasantries or small talk
❌ Inferred facts not directly stated

Examples (these are the ONLY acceptable extractions):
✅ "User loves cucumbers" (user explicitly said this)
✅ "User uses FL Studio" (user mentioned their tool)
✅ "User is interested in music production" (user asked about it)
❌ "Abby enjoys helping users" (about assistant, reject)
❌ "User probably likes computers" (inferred, reject)

Confidence scoring:
- 0.9-1.0: User explicitly stated with specifics
- 0.7-0.85: User clearly stated with some detail
- 0.5-0.7: Implied or mentioned briefly
- Below 0.5: Too vague (reject these)

Return ONLY valid JSON (no markdown, no code blocks):
[
  {{"text": "fact about user", "confidence": 0.85, "category": "interest"}}
]

If no facts found, return: []
"""
    
    try:
        # Call LLM for extraction
        response = chat_openai.chat(extraction_prompt, user_id, chat_history=[])
        
        # Clean response
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join([line for line in lines if not line.strip().startswith("```")])
        
        facts = json.loads(cleaned)
        
        if not isinstance(facts, list):
            logger.warning(f"[🧠] LLM returned non-list: {type(facts)}")
            return []
        
        # Validate and type each fact
        valid_facts = []
        for fact in facts:
            if not isinstance(fact, dict) or "text" not in fact or "confidence" not in fact:
                logger.debug(f"[🧠] Skipping malformed fact: {fact}")
                continue
            
            conf = float(fact.get("confidence", 0))
            
            # Reject low confidence
            if conf < 0.5:
                logger.debug(f"[🧠] Rejected low-confidence ({conf:.2f}): {fact['text'][:40]}")
                continue
            
            # CRITICAL: Validate fact is grounded in summary (anti-hallucination)
            if not validate_fact_against_summary(fact["text"], summary):
                logger.warning(f"[🧠] Rejected ungrounded fact (not in summary): {fact['text'][:50]}")
                continue
            
            # Fact passed validation — add memory type
            valid_facts.append({
                "text": str(fact["text"]),
                "type": "USER_FACT",  # Explicit memory type
                "confidence": min(conf, 1.0),
                "category": fact.get("category", "general"),
                "source": "llm_extraction"
            })
        
        logger.info(f"[🧠] Extracted {len(valid_facts)} valid USER_FACT memories")
        return valid_facts
        
    except json.JSONDecodeError as e:
        logger.warning(f"[🧠] JSON parse failed in fact extraction: {e}")
        return []
    except Exception as e:
        logger.error(f"[🧠] Fact extraction error: {e}", exc_info=True)
        return []


def analyze_conversation_patterns(
    summary: str,
    user_id: str,
    existing_profile: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Analyze conversation summary to infer USER_PATTERN updates.
    
    Returns PROPOSED updates, not direct writes. Caller decides whether to apply.
    
    Args:
        summary: Conversation summary (source of truth, not raw exchanges)
        user_id: User ID for context
        existing_profile: Current creative_profile if exists
        
    Returns:
        Dict with {proposed_updates, confidence, requires_confirmation}
    """
    if not summary or len(summary.strip()) < 30:
        logger.debug(f"[🧠] Summary too short for pattern analysis")
        return {}
    
    existing_domains = existing_profile.get("domains", []) if existing_profile else []
    existing_prefs = existing_profile.get("preferences", {}) if existing_profile else {}
    
    analysis_prompt = f"""Analyze this user conversation summary to identify PATTERNS about the USER (not the assistant).

CONVERSATION SUMMARY:
{summary}

Existing Profile:
- Domains: {', '.join(existing_domains) if existing_domains else 'None'}
- Preferences: {json.dumps(existing_prefs) if existing_prefs else 'None'}

Identify patterns EXPLICITLY MENTIONED or STRONGLY IMPLIED about THE USER:

1. NEW domains/interests the USER cares about (tools, topics, expertise areas)
   - Only if clearly mentioned or asked about
   - Examples: "music production", "FL Studio", "beat making"

2. USER's communication preferences
   - Formal vs casual tone they use
   - Detail level they prefer (high/medium/low)
   - Learning style they mention

3. USER's skill level (beginner/intermediate/advanced)
   - What they say about their expertise

CRITICAL: Do NOT infer things not stated. Do NOT extract facts about the assistant.

Return ONLY valid JSON (no markdown):
{{
  "new_domains": ["domain1", "domain2"],
  "preferences": {{
    "communication_style": "casual|formal|technical|mixed",
    "detail_level": "high|medium|low",
    "explanation_style": "step-by-step|conceptual|examples|mixed"
  }},
  "learning_level": "beginner|intermediate|advanced|unknown",
  "confidence": <0.0-1.0 based on how clearly patterns are stated>
}}

Confidence guidelines:
- 0.9-1.0: User explicitly stated preferences/expertise
- 0.7-0.9: Strong implications from conversation context
- 0.5-0.7: Weak signals, needs more validation
- Below 0.5: Too ambiguous, don't update

If no clear patterns found, return: {{"new_domains": [], "preferences": {{}}, "confidence": 0.0}}
"""
    
    try:
        response = chat_openai.chat(analysis_prompt, user_id, chat_history=[])
        
        # Clean response
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join([line for line in lines if not line.strip().startswith("```")])
        
        analysis = json.loads(cleaned)
        
        confidence = float(analysis.get("confidence", 0))
        
        # Don't apply low-confidence updates silently
        if confidence < 0.6:
            logger.debug(f"[🧠] Pattern analysis confidence too low ({confidence:.2f}), not applying")
            return {}
        
        # Build PROPOSED updates (not directly applied)
        proposed_updates = {}
        
        new_domains = analysis.get("new_domains", [])
        if new_domains:
            merged = list(set(existing_domains + new_domains))
            if merged != existing_domains:
                proposed_updates["domains"] = merged
        
        new_prefs = analysis.get("preferences", {})
        if new_prefs:
            merged = {**existing_prefs, **new_prefs}
            if merged != existing_prefs:
                proposed_updates["preferences"] = merged
        
        learning_level = analysis.get("learning_level")
        if learning_level and learning_level != "unknown":
            proposed_updates["learning_level"] = learning_level
        
        logger.info(f"[🧠] Pattern analysis proposed {len(proposed_updates)} updates (conf: {confidence:.2f})")
        
        return {
            "proposed_updates": proposed_updates,
            "confidence": confidence,
            "requires_confirmation": confidence < 0.8  # High threshold for auto-apply
        }
        
    except json.JSONDecodeError as e:
        logger.warning(f"[🧠] Pattern analysis JSON parse failed: {e}")
        return {}
    except Exception as e:
        logger.error(f"[🧠] Pattern analysis error: {e}", exc_info=True)
        return {}


def apply_confidence_decay(memorable_facts: List[Dict[str, Any]], decay_days: int = 30) -> List[Dict[str, Any]]:
    """
    Apply time-based confidence decay to memorable facts.
    Facts not mentioned in decay_days lose 0.1 confidence.
    
    Args:
        memorable_facts: List of fact dicts with last_confirmed timestamps
        decay_days: Days before decay applies
        
    Returns:
        Updated facts list with decayed confidence (facts < 0.3 removed)
    """
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    decay_threshold = now - timedelta(days=decay_days)
    
    updated_facts = []
    for fact in memorable_facts:
        last_confirmed = fact.get("last_confirmed")
        if isinstance(last_confirmed, str):
            # Parse ISO datetime string
            last_confirmed = datetime.fromisoformat(last_confirmed.replace('Z', '+00:00'))
        
        # Apply decay if not confirmed recently (only for USER_FACT, not SHARED_NARRATIVE)
        if fact.get("type") == "SHARED_NARRATIVE":
            # Shared narratives don't decay (they're warm memories, not factual)
            updated_facts.append(fact)
            continue
        
        confidence = fact.get("confidence", 0.7)
        if last_confirmed and last_confirmed < decay_threshold:
            days_old = (now - last_confirmed).days
            decay_periods = days_old // decay_days
            confidence -= (decay_periods * 0.1)
            logger.debug(f"[⏱️] Applied decay to {fact.get('type', 'UNKNOWN')} (age: {days_old}d): {fact.get('text', 'unknown')[:30]}... → {confidence:.2f}")
        
        # Keep fact if confidence still acceptable
        if confidence >= 0.3:
            fact["confidence"] = max(confidence, 0.3)
            updated_facts.append(fact)
        else:
            logger.info(f"[🗑️] Pruned low-confidence {fact.get('type', 'fact')} ({confidence:.2f}): {fact.get('text', 'unknown')[:50]}")
    
    return updated_facts


def reinforce_fact(
    user_id: str,
    guild_id: Optional[str],
    fact_text: str,
    boost: float = 0.15
) -> bool:
    """
    Reinforce a fact's confidence when user mentions it again.
    
    Args:
        user_id: User ID
        guild_id: Guild ID
        fact_text: Text of fact to reinforce (fuzzy match)
        boost: Confidence boost amount
        
    Returns:
        True if fact was found and reinforced
    """
    from abby_core.database.mongodb import connect_to_mongodb
    from datetime import datetime
    
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    
    profile = db["discord_profiles"].find_one({"user_id": str(user_id)})
    if not profile or "creative_profile" not in profile:
        return False
    
    facts = profile["creative_profile"].get("memorable_facts", [])
    
    # Fuzzy match fact (simple contains check)
    fact_lower = fact_text.lower()
    for fact in facts:
        fact_match_field = fact.get("text") or fact.get("fact")  # Support both old/new format
        if fact_lower in fact_match_field.lower() or fact_match_field.lower() in fact_lower:
            # Boost confidence (max 0.95)
            new_confidence = min(fact.get("confidence", 0.7) + boost, 0.95)
            
            # Update fact (support both old "fact" and new "text" field names)
            db["discord_profiles"].update_one(
                {
                    "user_id": str(user_id),
                    "$or": [
                        {"creative_profile.memorable_facts.text": fact_match_field},
                        {"creative_profile.memorable_facts.fact": fact_match_field}
                    ]
                },
                {
                    "$set": {
                        "creative_profile.memorable_facts.$.confidence": new_confidence,
                        "creative_profile.memorable_facts.$.last_confirmed": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"[📈] Reinforced fact confidence: {fact_match_field[:50]}... → {new_confidence:.2f}")
            return True
    
    return False


def add_shared_narrative(
    user_id: str,
    guild_id: Optional[str],
    memory: str,
    tone: str = "playful",
    auto_expire_days: Optional[int] = None
) -> bool:
    """
    Add a SHARED_NARRATIVE memory (warm persona memories, not factual).
    
    Examples:
    - "Abby calls them Ace the Mixer"
    - "We joked about cats together"
    - "They prefer when Abby uses emojis"
    
    These memories:
    - NEVER used for inference or decision-making
    - NEVER embedded in system prompts as facts
    - CAN be referenced for warmth and continuity
    - User can delete them anytime
    
    Args:
        user_id: User ID
        guild_id: Guild ID
        memory: The shared memory text
        tone: Tone of memory (playful, warm, funny, inside_joke)
        auto_expire_days: Days until memory auto-deletes (None = never expire)
        
    Returns:
        True if added successfully
    """
    from datetime import datetime, timedelta
    from abby_core.database.mongodb import connect_to_mongodb
    
    if not memory or len(memory.strip()) < 10:
        logger.warning(f"[📖] Shared narrative too short: {len(memory)}")
        return False
    
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    
    # Create shared narrative record
    narrative = {
        "type": "SHARED_NARRATIVE",
        "user_id": str(user_id),
        "guild_id": str(guild_id) if guild_id else None,
        "memory": memory,
        "tone": tone,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=auto_expire_days) if auto_expire_days else None,
        "deletable": True  # User can delete anytime
    }
    
    try:
        db["shared_narratives"].insert_one(narrative)
        logger.info(f"[📖] Added shared narrative: {memory[:50]}...")
        return True
    except Exception as e:
        logger.error(f"[📖] Failed to add shared narrative: {e}")
        return False


def get_shared_narratives(user_id: str, guild_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get all non-expired SHARED_NARRATIVE memories for a user.
    
    Args:
        user_id: User ID
        guild_id: Optional guild ID filter
        
    Returns:
        List of active shared narratives
    """
    from datetime import datetime
    from abby_core.database.mongodb import connect_to_mongodb
    
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    
    query = {"type": "SHARED_NARRATIVE", "user_id": str(user_id)}
    if guild_id:
        query["guild_id"] = str(guild_id)
    
    # Filter out expired narratives
    narratives = db["shared_narratives"].find(query)
    active = []
    for narrative in narratives:
        if narrative.get("expires_at"):
            if narrative["expires_at"] > datetime.utcnow():
                active.append(narrative)
        else:
            active.append(narrative)
    
    return active


def delete_shared_narrative(user_id: str, memory_text: str) -> bool:
    """
    Delete a SHARED_NARRATIVE memory (user opt-out).
    
    Args:
        user_id: User ID
        memory_text: Text to match and delete
        
    Returns:
        True if deleted
    """
    from abby_core.database.mongodb import connect_to_mongodb
    
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    
    result = db["shared_narratives"].delete_one({
        "user_id": str(user_id),
        "memory": memory_text,
        "deletable": True
    })
    
    if result.deleted_count > 0:
        logger.info(f"[📖] Deleted shared narrative: {memory_text[:50]}...")
        return True
    
    logger.warning(f"[📖] Could not delete shared narrative (not found or protected)")
    return False

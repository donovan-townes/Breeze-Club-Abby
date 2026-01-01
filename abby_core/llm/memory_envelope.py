"""
Memory Envelope System for Abby
Implements structured, cached user memory with confidence scoring.
"""
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from abby_core.database.mongodb import connect_to_mongodb
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)

# In-memory cache for memory envelopes
_memory_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes


def _cache_key(user_id: str, guild_id: Optional[str] = None) -> str:
    """Generate cache key for user memory."""
    return f"{guild_id or 'global'}:{user_id}"


def get_memory_envelope(user_id: str, guild_id: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Get or build the memory envelope for a user.
    Returns a small, cached snapshot of identity + relational memory.
    
    Args:
        user_id: Discord user ID
        guild_id: Optional guild ID for guild-specific memory
        force_refresh: Force rebuild from database
        
    Returns:
        Memory envelope dict with identity, relational, and recent_context
    """
    cache_key = _cache_key(user_id, guild_id)
    
    # Check cache first
    if not force_refresh and cache_key in _memory_cache:
        cached = _memory_cache[cache_key]
        age = time.time() - cached.get('_cached_at', 0)
        if age < CACHE_TTL_SECONDS:
            logger.debug(f"[📦] Using cached memory envelope for {user_id} (age: {age:.1f}s)")
            return cached['envelope']
    
    # Build fresh envelope
    logger.info(f"[📦] Building memory envelope for {user_id}")
    envelope = _build_envelope(user_id, guild_id)
    
    # Cache it
    _memory_cache[cache_key] = {
        'envelope': envelope,
        '_cached_at': time.time()
    }
    
    return envelope


def _build_envelope(user_id: str, guild_id: Optional[str] = None) -> Dict[str, Any]:
    """Build memory envelope from database."""
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    
    # Layer 1: Identity (stable facts)
    profile = db["discord_profiles"].find_one({"user_id": str(user_id)})
    identity = {
        "name": profile.get("username", "User") if profile else "User",
        "nickname": profile.get("nickname") if profile else None,
        "user_id": str(user_id),
        "guild_id": str(guild_id) if guild_id else None,
    }
    
    # Layer 2: Relational (evolving traits)
    # Check for creative_profile if it exists
    relational = profile.get("creative_profile", {}) if profile else {}
    if not relational:
        # Default empty relational memory
        relational = {
            "domains": [],
            "preferences": {},
            "memorable_facts": [],
            "confidence": {}
        }
    
    # Layer 3: Recent Context (last session summary only)
    recent_session = db["chat_sessions"].find_one(
        {"user_id": str(user_id), "guild_id": str(guild_id) if guild_id else None, "status": "closed"},
        sort=[("closed_at", -1)]
    )
    recent_context = {
        "last_session_summary": recent_session.get("summary") if recent_session else None,
        "last_session_date": recent_session.get("closed_at").isoformat() if recent_session and recent_session.get("closed_at") else None
    }
    
    return {
        "identity": identity,
        "relational": relational,
        "recent_context": recent_context,
        "last_built": datetime.utcnow().isoformat(),
        "version": "1.0"
    }


def invalidate_cache(user_id: str, guild_id: Optional[str] = None):
    """Invalidate cached memory envelope for a user."""
    cache_key = _cache_key(user_id, guild_id)
    if cache_key in _memory_cache:
        del _memory_cache[cache_key]
        logger.debug(f"[📦] Invalidated cache for {user_id}")


def update_relational_memory(
    user_id: str,
    guild_id: Optional[str],
    updates: Dict[str, Any],
    confidence: float = 0.7
):
    """
    Update relational memory for a user.
    
    Args:
        user_id: Discord user ID
        guild_id: Optional guild ID
        updates: Dict of fields to update in creative_profile
        confidence: Confidence score (0-1)
    """
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    
    # Update or create creative_profile in discord_profiles
    update_doc = {}
    for key, value in updates.items():
        update_doc[f"creative_profile.{key}"] = value
    
    update_doc["creative_profile.last_updated"] = datetime.utcnow()
    update_doc["creative_profile.confidence_score"] = confidence
    
    db["discord_profiles"].update_one(
        {"user_id": str(user_id)},
        {"$set": update_doc},
        upsert=True
    )
    
    # Invalidate cache
    invalidate_cache(user_id, guild_id)
    logger.info(f"[📦] Updated relational memory for {user_id}")


def add_memorable_fact(
    user_id: str,
    guild_id: Optional[str],
    fact: str,
    source: str = "conversation",
    confidence: float = 0.7
):
    """Add a memorable fact to user's relational memory."""
    try:
        client = connect_to_mongodb()
        db = client["Abby_Database"]
        
        fact_doc = {
            "fact": fact,
            "source": source,
            "confidence": confidence,
            "added_at": datetime.utcnow(),
            "last_confirmed": datetime.utcnow()
        }
        
        logger.debug(f"[📦] Attempting to add fact to {user_id}: {fact[:50]}...")
        
        # Explicit write concern to ensure persistence
        from pymongo.write_concern import WriteConcern
        profiles_collection = db["discord_profiles"].with_options(
            write_concern=WriteConcern(w="majority", j=True)  # j=True ensures journal fsync
        )
        
        result = profiles_collection.update_one(
            {"user_id": str(user_id)},
            {"$push": {"creative_profile.memorable_facts": fact_doc}},
            upsert=True
        )
        
        logger.debug(f"[📦] MongoDB result - acknowledged: {result.acknowledged}, matched: {result.matched_count}, modified: {result.modified_count}")
        
        # Check if write was acknowledged
        if result.acknowledged:
            
            invalidate_cache(user_id, guild_id)
            logger.info(f"[📦] Added memorable fact for {user_id}: {fact[:50]}...")
            return True
        else:
            logger.warning(f"[⚠️] Write not acknowledged by MongoDB for {user_id}")
            return False
    except Exception as e:
        logger.error(f"[❌] Error adding memorable fact for {user_id}: {e}", exc_info=True)
        return False


def format_envelope_for_llm(envelope: Dict[str, Any], max_facts: int = 5) -> str:
    """
    Format memory envelope into concise text for LLM context.
    
    Args:
        envelope: Memory envelope dict
        max_facts: Maximum number of memorable facts to include
        
    Returns:
        Formatted string for LLM system prompt
    """
    identity = envelope.get("identity", {})
    relational = envelope.get("relational", {})
    recent = envelope.get("recent_context", {})
    
    lines = []
    
    # Identity
    name = identity.get("nickname") or identity.get("name", "User")
    lines.append(f"User: {name}")
    
    # Domains/roles
    domains = relational.get("domains", [])
    if domains:
        lines.append(f"Domains: {', '.join(domains)}")
    
    # Preferences
    prefs = relational.get("preferences", {})
    if prefs:
        pref_str = ", ".join([f"{k}: {v}" for k, v in prefs.items() if v])
        if pref_str:
            lines.append(f"Preferences: {pref_str}")
    
    # Memorable facts (top N by confidence)
    facts = relational.get("memorable_facts", [])
    if facts:
        # Sort by confidence
        sorted_facts = sorted(facts, key=lambda x: x.get("confidence", 0), reverse=True)[:max_facts]
        lines.append("Known facts:")
        for f in sorted_facts:
            conf = f.get("confidence", 0)
            lines.append(f"  • {f['fact']} (confidence: {conf:.0%})")
    
    # Recent context
    last_summary = recent.get("last_session_summary")
    if last_summary:
        lines.append(f"\nLast conversation: {last_summary}")
    
    return "\n".join(lines)

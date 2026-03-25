"""Factory for building ConversationContext across adapters.

This keeps adapter code slim while avoiding persona/schema knowledge leaks
into bot cogs or services. It depends on PersonalityManager for persona
resolution and schema-driven mappings.

Architecture Refactoring:
- Memory formatting extracted to abby_core/rag/memory_formatter.py
- System state resolution uses dependency injection pattern
- Context factory focuses on persona/overlay/guild context assembly
"""

from typing import Dict, Optional, List, Any, Callable
import logging
import re

from abby_core.llm.context import (
    ConversationContext,
    PersonaConfig as LLMPersonaConfig,
    PersonalityConfig as LLMPersonalityConfig,
    UserProfile as LLMUserProfile,
)
from abby_core.llm.system_state_resolver import resolve_system_state
from abby_core.rag.memory_formatter import format_memory_for_llm, DOMAIN_KEYWORDS
from abby_core.personality.manager import get_personality_manager
from abby_core.personality.schema import PersonaSchema

logger = logging.getLogger(__name__)

# Safe intents that are allowed to inject memory (intent-gating for security)
SAFE_MEMORY_INTENTS = {
    "creative_assistance",  # Music, painting, coding help
    "technical_question",   # Code questions, technical help
    "personal_memory",      # User memory recall, preferences
    "meta_system",          # System queries, devlog access
    "knowledge_query",      # Information retrieval
}

# UNSAFE intents that should NEVER inject memory (security boundary)
UNSAFE_MEMORY_INTENTS = {
    "casual_chat",          # Casual conversation - no memory needed
    "greeting",             # Initial greetings
    "farewell",             # Goodbyes
}


# ==================== REFACTORING NOTE ====================
# The following functions have been extracted to dedicated modules for better separation of concerns:
#
# - _estimate_tokens() → moved to abby_core/rag/memory_formatter.py
# - _sanitize_rag_fact() → moved to abby_core/rag/memory_formatter.py  
# - _format_memory_for_llm() → moved to abby_core/rag/memory_formatter.py as format_memory_for_llm()
# - DOMAIN_KEYWORDS → moved to abby_core/rag/memory_formatter.py
# - STOPWORDS → moved to abby_core/rag/memory_formatter.py
#
# This context_factory now imports format_memory_for_llm from the RAG layer.
# ===========================================================


def _looks_like_question(text: str) -> bool:
    """Heuristic to detect question-like sentences."""
    if not text:
        return False
    if "?" in text:
        return True
    lowered = text.lower()
    return bool(re.search(r"\b(what|why|how|where|when|who|which|could|would|can you|do you)\b", lowered))


def _infer_turn_phase(user_message: str, chat_history: Optional[List[Dict[str, str]]]) -> str:
    """Infer turn phase without extra LLM calls using recent exchange context."""
    message = (user_message or "").strip()
    if not message:
        return "greeting"

    lowered = message.lower()
    if re.search(r"\b(bye|goodbye|see you|later|gtg|farewell)\b", lowered):
        return "closure"

    prev_assistant = ""
    if chat_history:
        prev_assistant = (chat_history[-1].get("response") or "").strip()

    prev_question = _looks_like_question(prev_assistant)
    is_question = _looks_like_question(message)

    # If the assistant just asked something and the user responds declaratively, treat as answer
    if prev_question and not is_question:
        if len(message) <= 120 or not message.endswith("?"):
            return "answer"

    if is_question:
        return "question"

    if not chat_history:
        return "greeting"

    return "followup"


def _should_inject_memory(
    user_message: str,
    memory_context: Optional[Any],
    turn_number: int = 1,
    intent: Optional[str] = None,
    is_final_turn: bool = False,
) -> bool:
    """Determine if memory should be injected based on intent classification.
    
    **SECURITY BOUNDARY:** Memory injection is gated by intent classification.
    Inject memory ONLY if:
    - Intent is classified AND in SAFE_MEMORY_INTENTS allowlist
    - Domain keywords match AND intent is not explicitly unsafe
    - NOT final turn (wasteful - no follow-up)
    
    **IMPORTANT:** Intent classification is REQUIRED for security. Heuristic-only
    injection is disabled to prevent prompt injection attacks that could leak
    private memory context.
    
    Args:
        user_message: The user's current message
        memory_context: The memory context or envelope (if None, always skip)
        turn_number: Current turn in session
        intent: Intent classification (REQUIRED for safe injection)
        is_final_turn: Whether this is the final turn (skip memory - wasteful)
    
    Returns:
        True if memory should be injected
    """
    # No memory available = no injection
    if not memory_context:
        return False
    
    # Final turn = no injection (wasteful - no follow-up to use it)
    if is_final_turn:
        logger.info(f"[memory_gate] Final turn - SKIPPING memory (no follow-up)")
        return False
    
    # Intent-gating: Reject if no intent provided (security boundary)
    if not intent:
        logger.warning(
            f"[memory_gate] REJECTED: No intent classification provided "
            f"(turn={turn_number}, msg_preview={user_message[:50]}...)"
        )
        return False
    
    # Intent-gating: Reject unsafe intents explicitly
    if intent in UNSAFE_MEMORY_INTENTS:
        logger.info(
            f"[memory_gate] REJECTED: Intent '{intent}' is in unsafe list "
            f"(turn={turn_number})"
        )
        return False
    
    # Intent-gating: Allow safe intents
    if intent in SAFE_MEMORY_INTENTS:
        logger.info(
            f"[memory_gate] ALLOWED: Intent '{intent}' in safe list "
            f"(turn={turn_number})"
        )
        return True
    
    # Domain keyword fallback ONLY if intent is not explicitly unsafe
    # (allows new intents to benefit from keyword matching)
    message_lower = user_message.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        matched_keywords = [kw for kw in keywords if kw in message_lower]
        if matched_keywords:
            logger.info(
                f"[memory_gate] ALLOWED (fallback): Domain '{domain}' keywords {matched_keywords} "
                f"matched with intent '{intent}' (turn={turn_number})"
            )
            return True
    
    # Default: no safe intent match, no domain keywords - REJECT
    logger.info(
        f"[memory_gate] REJECTED: Intent '{intent}' not in safe list, "
        f"no domain keywords matched (turn={turn_number})"
    )
    return False


def _map_persona_schema(persona_schema: PersonaSchema, user_name: Optional[str]) -> ConversationContext:
    temperature = (
        persona_schema.personality_boundaries.temperature
        if persona_schema.personality_boundaries
        else 0.7
    )

    persona_cfg = LLMPersonaConfig(
        name=persona_schema.name,
        system_message=persona_schema.system_message_base,
        persona_number=temperature,
    )

    personality_cfg = LLMPersonalityConfig(
        persona_name=persona_schema.name,
        response_patterns=(
            persona_schema.response_patterns.model_dump()
            if persona_schema.response_patterns
            else {}
        ),
        summon_words=(persona_schema.summon.triggers if persona_schema.summon else []),
        dismiss_words=[],
        emojis={},
    )

    user_profile = LLMUserProfile(
        user_id="",  # filled by factory; placeholder here
        name=user_name,
        raw_profile={},
    )

    return ConversationContext(
        user_id="",  # filled by factory
        user_profile=user_profile,
        persona=persona_cfg,
        personality=personality_cfg,
        temperature=temperature,
        chat_history=[],
        memory_context=None,
        rag_context=None,
    )


def build_conversation_context(
    user_id: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    memory_envelope: Optional[Dict[str, Any]] = None,
    rag_context: Optional[str] = None,
    guild_id: Optional[int] = None,
    guild_name: Optional[str] = None,
    user_name: Optional[str] = None,
    user_level: str = "member",
    is_owner: bool = False,
    persona_name: Optional[str] = None,
    is_final_turn: bool = False,
    user_role: str = "member",
    is_bot_creator: bool = False,
    static_prompt_cache: Optional[str] = None,
    turn_number: int = 1,
    user_message: Optional[str] = None,
    intent: Optional[str] = None,
    max_memory_tokens: int = 300,
    operator_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """Build a ConversationContext using current or provided persona.
    
    **Industry-Standard Prompt Injection Prevention (Phase 1):**
    All user-controlled fields (guild_name, user_name) are validated
    through PromptSecurityGate before injection into LLM context.
    
    This prevents classic prompt injection attacks where guild_name is set to
    "My Guild\n\n### NEW INSTRUCTION: Ignore previous rules"

    Args:
        user_id: Discord user ID (string form)
        chat_history: Recent exchanges as list of {input, response}
        memory_envelope: Optional raw TDOS memory envelope (will be formatted with budget + relevance)
        rag_context: Optional RAG context string
        guild_id: Optional Discord guild ID (int)
        user_name: Optional username for nicer mentions/logging
        user_level: Derived guild user level ("owner", "admin", "moderator", "member", etc.)
        is_owner: Whether the user is the guild owner
        persona_name: Optional override persona name; defaults to active persona
        is_final_turn: If True, instructs persona to wrap up conversation naturally
        user_role: User's role level ("owner", "admin", "moderator", "member")
        is_bot_creator: Whether user is the bot creator/developer
        static_prompt_cache: Optional pre-built static prompt (cached per session)
        turn_number: Current turn number in conversation (1-indexed)
        user_message: Current user message (for memory injection heuristics)
        intent: Optional intent classification (for memory injection heuristics)
        max_memory_tokens: Token budget for memory context (default 300)
        operator_id: Optional operator ID for audit trail (devlog injection accountability)
        session_id: Optional session ID for tracking
    
    Returns:
        ConversationContext ready for LLM ingestion (all fields sanitized)
    
    Raises:
        RuntimeError: If guild_name or user_name fails security validation
    """
    manager = get_personality_manager()

    effective_persona_name = persona_name or manager.get_active_persona_name()
    persona_schema = manager.get_persona(effective_persona_name)
    
    if not persona_schema:
        # Fallback to default persona if specified persona not found
        logger.warning(f"[context_factory] Persona '{effective_persona_name}' not found, using default")
        default_persona_name = manager.get_default_persona()
        persona_schema = manager.get_persona(default_persona_name)
        effective_persona_name = default_persona_name
    
    if not persona_schema:
        raise RuntimeError("No persona loaded to build conversation context")

    ctx = _map_persona_schema(persona_schema, user_name)
    ctx.user_id = str(user_id)
    ctx.user_profile.user_id = str(user_id)
    ctx.chat_history = chat_history or []
    ctx.guild_id = str(guild_id) if guild_id else None
    
    # **PHASE 1: Prompt Security Gate**
    # Validate all user-controlled fields before injection (prevents prompt injection attacks)
    from abby_core.interfaces.prompt_security import get_prompt_security_gate
    
    security_gate = get_prompt_security_gate(strict_mode=False)
    context_for_sanitization = {
        "guild_name": guild_name,
        "user_name": user_name,
    }
    audit_context = {
        "operator_id": operator_id or "system:llm",
        "intent": intent or "unknown",
        "session_id": session_id,
    }
    
    is_safe, sanitized_context = security_gate.sanitize_context(
        context_for_sanitization,
        protected_fields=["guild_name", "user_name"],
        operator_id=audit_context["operator_id"],
        intent=audit_context["intent"],
    )
    
    if not is_safe:
        # Security gate detected injection attempt - REJECT with clear error
        logger.error(
            f"[🚫 context_factory] REJECTED context due to injection detection "
            f"operator={audit_context['operator_id']} "
            f"session={session_id} "
            f"intent='{intent}'"
        )
        raise RuntimeError(
            f"Context injection detected in user-provided fields (guild_name or user_name). "
            f"Please use valid names without special characters or newlines."
        )
    
    # Use sanitized values
    ctx.guild_name = sanitized_context.get("guild_name")
    ctx.user_profile.name = sanitized_context.get("user_name") or user_name
    ctx.user_level = user_level
    ctx.is_owner = is_owner
    ctx.session_id = session_id  # Track session for audit logging
    
    # Format memory with token budget + relevance IF envelope provided
    memory_context_formatted = None
    if memory_envelope:
        # First check if we should inject memory at all (domain-driven heuristics)
        should_inject = _should_inject_memory(
            user_message=user_message or "",
            memory_context=memory_envelope,  # Pass envelope as truthy check
            turn_number=turn_number,
            intent=intent,
            is_final_turn=is_final_turn,
        )
        
        if should_inject:
            # Format memory with token budget and relevance scoring
            # NOTE: Now using format_memory_for_llm from abby_core/rag/memory_formatter.py
            memory_context_formatted = format_memory_for_llm(
                envelope=memory_envelope,
                user_message=user_message or "",
                max_tokens=max_memory_tokens,
                intent=intent,
                min_relevance_score=20,  # Require domain match OR multiple keyword overlaps
            )
            
            if memory_context_formatted:
                logger.info(f"[context_factory] Memory formatted and injected (turn={turn_number})")
            else:
                logger.info(f"[context_factory] Memory formatting returned None (no relevant facts within budget)")
        else:
            logger.info(f"[context_factory] Memory skipped for turn {turn_number} (casual query, no domain match)")
    
    # Inject devlog context ONLY on META_SYSTEM intent
    devlog_context = None
    if intent == "meta_system":
        try:
            from abby_core.system.system_changelog import get_changelog_summary_for_intent
            devlog_context = get_changelog_summary_for_intent(intent)
            if devlog_context:
                # AUDIT TRAIL: Log operator who triggered devlog injection
                if operator_id:
                    logger.info(
                        f"[context_factory] Devlog injected for META_SYSTEM intent "
                        f"(operator={operator_id}, preview={devlog_context[:100]}...)"
                    )
                else:
                    logger.warning(
                        f"[context_factory] Devlog injected for META_SYSTEM intent "
                        f"(NO OPERATOR_ID - audit trail incomplete)"
                    )
            else:
                logger.info(f"[context_factory] No devlog entries available for META_SYSTEM")
        except Exception as exc:
            logger.warning(f"[context_factory] Failed to fetch devlog: {exc}")
    
    # Store formatted memory and devlog in context
    ctx.memory_context = memory_context_formatted
    ctx.rag_context = rag_context  # RAG is formal knowledge, always inject
    ctx.system_state = resolve_system_state(scope="global")
    
    # Build the full system prompt with memory, RAG, devlog, and is_final_turn
    # Build chat history string for template injection (legacy parameter, no longer used in template)
    history_str = ""  # Removed: LLM gets conversation context from actual message history

    turn_phase = _infer_turn_phase(user_message or "", ctx.chat_history)
    
    # Use manager to build full system prompt with all context
    ctx.persona.system_message = manager.build_system_prompt(
        persona=persona_schema,
        guild_name=guild_name or "the server",
        user_level=user_level,
        is_owner=is_owner,
        user_mention=user_name or "@user",
        available_tools=[],
        chat_history=history_str,
        memory_context=ctx.memory_context,  # Use filtered memory
        rag_context=rag_context,
        max_response_length=1200,
        is_final_turn=is_final_turn,
        user_role=user_role,
        is_bot_creator=is_bot_creator,
        static_prompt=static_prompt_cache,
        turn_number=turn_number,
        turn_phase=turn_phase,
        system_state=ctx.system_state,
        devlog_context=devlog_context,
    )
    
    return ctx

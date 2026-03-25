"""Conversation module - streamlined chat flow without data retrieval.

This module provides conversation functions that operate on injected ConversationContext.
All data retrieval (user profiles, persona selection, personality config) is handled
by PersonalityManager and passed in as context.

This keeps the conversation flow clean and preparation-ready for:
- Intent gating (classify intent before responding)
- Function listing (what can Abby do?)
- Memory injection (RAG context)
- Streaming responses
- Conversation analytics

Architecture:
    ConversationContext (all injected data)
         ↓
    chat() / summarize() / analyze() (pure conversation logic)
         ↓
    LLMClient (TDOS)

Responsibilities:
- Build final messages list from context
- Call LLM with appropriate parameters
- Handle retries
- Log conversation flow
"""

import os
import time
import uuid
from typing import List, Dict, Optional

from tdos_intelligence.llm import LLMClient
from abby_core.personality.manager import get_personality_manager
from abby_core.llm.context import ConversationContext
from abby_core.observability.logging import setup_logging, logging
from abby_core.services.generation_audit_service import get_generation_audit_service

setup_logging()
logger = logging.getLogger(__name__)
PROMPT_VERBOSE = os.getenv("PROMPT_VERBOSE", "0") in {"1", "true", "True"}

# LLM client singleton
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create LLMClient singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


async def respond(
    user_message: str,
    context: ConversationContext,
    max_retries: int = 3,
    max_tokens: int = 1500,
) -> str:
    """Generate a response using the LLM with full context.
    
    All persona, personality, and user profile data is pre-injected in the context.
    This function only handles conversation flow and LLM interaction.
    
    Args:
        user_message: The user's message
        context: ConversationContext with all injected data
        max_retries: Number of times to retry on failure (default 3)
        max_tokens: Maximum tokens in response (default 1500)
    
    Returns:
        Assistant's response string
    
    Usage:
        from abby_core.llm.context_factory import build_conversation_context
        context = build_conversation_context(
            user_id=ctx.author.id,
            chat_history=stored_history
        )
        
        response = await respond(ctx.message.content, context)
    
    Preparation for Future (Intent Gating):
        # Soon we'll add intent classification here:
        intent = await classify_intent(user_message, context)
        if intent.requires_function:
            # List available functions for the intent
            functions = get_available_functions(intent)
            context.intent_info = {
                "intent": intent,
                "available_functions": functions,
                "available_functions_summary": format_functions_summary(functions)
            }
    """
    try:
        llm = get_llm_client()
        
        # NOTE: persona_schema already obtained in build_conversation_context()
        # We can use context.persona.system_message directly instead of re-fetching
        # Build final messages list using PersonalityManager system prompt
        manager = get_personality_manager()
        # Get persona - but ONLY if we need more than what context already has
        # context.persona already has the system_message from build_conversation_context()
        available_tools = []
        if context.intent_info and isinstance(context.intent_info.get("available_functions"), list):
            available_tools = [fn.get("name", "unknown") for fn in context.intent_info.get("available_functions", [])]

        # Build a compact chat history string for template injection (last 3 exchanges)
        history_pairs = []
        for item in context.chat_history[-3:]:
            user = item.get("input", "")
            assistant = item.get("response", "")
            history_pairs.append(f"User: {user}\nAssistant: {assistant}")
        history_str = "\n\n".join(history_pairs) if history_pairs else ""

        # Use system message from context (already built in build_conversation_context)
        # No need to fetch persona again - we have system_message ready to use
        system_prompt = context.persona.system_message

        system_len = len(system_prompt)
        approx_tokens = int(system_len / 4)  # rough token estimate
        if PROMPT_VERBOSE:
            logger.debug(
                f"[Prompt] System prompt size: {system_len} chars (~{approx_tokens} tokens) | "
                f"chat_history chars={len(history_str)} memory={len(context.memory_context or '')} rag={len(context.rag_context or '')}"
            )
            logger.debug("[Prompt] ---- SYSTEM PROMPT BEGIN ----\n%s\n[Prompt] ---- SYSTEM PROMPT END ----", system_prompt)

        messages = [{"role": "system", "content": system_prompt}]
        
        # Add chat history (last 2 exchanges) as message pairs for grounding
        for message in context.chat_history[-2:]:
            user_text = message.get("input")
            assistant_text = message.get("response")
            if user_text is not None:
                messages.append({"role": "user", "content": str(user_text)})
            if assistant_text is not None:
                messages.append({"role": "assistant", "content": str(assistant_text)})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Store content for audit logging (available in all scopes)
        content = user_message

        if PROMPT_VERBOSE:
            total_chars = sum(len(m.get("content", "")) for m in messages)
            logger.debug(f"[Prompt] messages_count={len(messages)} total_chars={total_chars}")
            logger.debug("[Prompt] ---- FULL MESSAGES ARRAY BEGIN ----")
            for idx, msg in enumerate(messages):
                role = msg.get("role", "unknown")
                msg_content = msg.get("content", "")
                logger.debug(f"[Prompt] [{idx}] role={role} | content_length={len(msg_content)} chars")
                logger.debug(f"[Prompt] [{idx}] {msg_content[:500]}..." if len(msg_content) > 500 else f"[Prompt] [{idx}] {msg_content}")
            logger.debug("[Prompt] ---- FULL MESSAGES ARRAY END ----")
        
        # Attempt with retries
        retry_count = 0
        while retry_count < max_retries:
            try:
                logger.debug(
                    f"[💬] Chat with {context.user_profile.name or context.user_id} "
                    f"(persona: {context.persona.name}, temp: {context.temperature})"
                )
                
                start_time = time.time()
                response = llm.chat(
                    messages,
                    temperature=context.temperature,
                )
                latency_ms = int((time.time() - start_time) * 1000)
                
                logger.debug(f"[✅] Chat response generated ({len(response)} chars)")
                
                # Audit logging for cost tracking and observability
                try:
                    audit_service = get_generation_audit_service()
                    # Estimate tokens (rough: 1 token ≈ 4 chars)
                    input_tokens = sum(len(m.get("content", "")) for m in messages) // 4
                    output_tokens = len(response) // 4
                    
                    # Generate audit ID from session and timestamp
                    audit_id = f"{context.session_id or 'no-session'}_{uuid.uuid4().hex[:8]}"
                    
                    audit_service.log_generation(
                        audit_id=audit_id,
                        provider="openai",  # LLM client determines actual provider
                        model=llm.openai_model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency_ms,
                        session_id=context.session_id,
                        user_id=str(context.user_id),
                        guild_id=context.guild_id,
                        intent=context.intent_info.get("intent") if context.intent_info else None,
                        system_prompt=system_prompt[:500] if system_prompt else None,
                        user_message=content[:500],
                        response=response[:500],
                    )
                except Exception as audit_error:
                    # Don't fail the request if audit logging fails
                    logger.warning(f"[⚠️] Generation audit logging failed: {audit_error}")
                
                return response
            
            except Exception as e:
                retry_count += 1
                logger.warning(
                    f"[⚠️] Chat request failed (attempt {retry_count}/{max_retries}): {str(e)}"
                )
                
                if retry_count < max_retries:
                    logger.info(f"[⏳] Retrying in 1 second...")
                    time.sleep(1)
        
        logger.error("[❌] Chat failed after all retries")
        return "Oops, something went wrong. Please try again later."
    
    except Exception as e:
        logger.error(f"[❌] Unexpected error in chat(): {str(e)}")
        return "Oops, something went wrong. Please try again later."




async def summarize(
    chat_session: List[Dict] | str,
    max_tokens: int = 300,
    max_retries: int = 3,
) -> str:
    """
    Generate a summary from chat history.
    
    Args:
        chat_session: List of dicts with 'input'/'response' keys, or a string
        max_tokens: Maximum tokens in summary (default 300)
        max_retries: Number of times to retry on failure (default 3)
    
    Returns:
        Summary string
    
    Future: Will accept ConversationContext to preserve persona in summary tone
    """
    try:
        llm = get_llm_client()
        
        # Convert to text if needed
        if isinstance(chat_session, list):
            formatted_text = "\n\n".join([
                f"User: {item.get('input', '')}\nAbby: {item.get('response', '')}"
                for item in chat_session
                if isinstance(item, dict) and (item.get('input') or item.get('response'))
            ])
            chat_text = formatted_text if formatted_text else str(chat_session)
        else:
            chat_text = str(chat_session)
        
        # Attempt with retries
        retry_count = 0
        while retry_count < max_retries:
            try:
                logger.debug("[📝] Generating chat summary...")
                
                start_time = time.time()
                response = llm.summarize(chat_text, max_tokens=max_tokens)
                latency_ms = int((time.time() - start_time) * 1000)
                
                logger.debug(f"[✅] Summary generated ({len(response)} chars)")
                
                # Audit logging for summarization
                try:
                    audit_service = get_generation_audit_service()
                    input_tokens = len(chat_text) // 4  # Rough estimate
                    output_tokens = len(response) // 4
                    
                    # Generate audit ID
                    audit_id = f"summarize_{uuid.uuid4().hex[:8]}"
                    
                    audit_service.log_generation(
                        audit_id=audit_id,
                        provider="openai",
                        model=llm.openai_model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency_ms,
                        intent="summarize",
                        user_message=chat_text[:500],
                        response=response[:500],
                    )
                except Exception as audit_error:
                    logger.warning(f"[⚠️] Summarize audit logging failed: {audit_error}")
                
                return response
            
            except Exception as e:
                retry_count += 1
                logger.warning(
                    f"[⚠️] Summarize request failed (attempt {retry_count}/{max_retries}): {str(e)}"
                )
                
                if retry_count < max_retries:
                    time.sleep(1)
        
        logger.error("[❌] Summarize failed after all retries")
        return "Unable to generate summary at this time."
    
    except Exception as e:
        logger.error(f"[❌] Unexpected error in summarize(): {str(e)}")
        return "Unable to generate summary at this time."




async def analyze(
    content: str,
    context: ConversationContext,
    max_tokens: int = 3000,
    max_retries: int = 3,
) -> str:
    """
    Perform detailed analysis of content with persona-aware feedback.
    
    Args:
        content: Content to analyze (chat history, idea, proposal, etc.)
        context: ConversationContext with persona and user info
        max_tokens: Maximum tokens in analysis (default 3000)
        max_retries: Number of times to retry on failure (default 3)
    
    Returns:
        Analysis and recommendations string
    """
    try:
        llm = get_llm_client()
        
        # Build analysis prompt with persona context
        analysis_prompt = (
            f"You are {context.persona.name}. "
            f"Perform a detailed analysis and summarize the key points from the following content. "
            f"Provide actionable feedback and recommendations for {context.user_profile.name or 'the user'} "
            f"to improve effectiveness for the {context.guild_name or 'community'}.\n\n"
            f"Content to analyze:\n{content}"
        )
        
        manager = get_personality_manager()
        persona_schema = manager.get_persona(context.persona.name) if context.persona else None
        if persona_schema is None:
            analysis_system_prompt = context.persona.system_message
        else:
            analysis_system_prompt = manager.build_system_prompt(
                persona=persona_schema,
                guild_name=context.guild_name or "this community",
                user_level=context.user_level,
                is_owner=context.is_owner,
                user_mention=context.user_profile.name or "@user",
                available_tools=[],
                chat_history="",
                memory_context=None,
                rag_context=None,
                max_response_length=1200,
                system_state=getattr(context, "system_state", None),
            )

        messages = [
            {"role": "system", "content": analysis_system_prompt},
            {"role": "user", "content": analysis_prompt},
        ]
        
        # Attempt with retries
        retry_count = 0
        while retry_count < max_retries:
            try:
                logger.debug(f"[🔍] Analyzing content for {context.user_profile.name or context.user_id}...")
                
                response = llm.chat(
                    messages,
                    temperature=0.3,  # Lower temp for analytical consistency
                    max_tokens=max_tokens,
                )
                
                logger.debug(f"[✅] Analysis generated ({len(response)} chars)")
                return response
            
            except Exception as e:
                retry_count += 1
                logger.warning(
                    f"[⚠️] Analyze request failed (attempt {retry_count}/{max_retries}): {str(e)}"
                )
                
                if retry_count < max_retries:
                    time.sleep(1)
        
        logger.error("[❌] Analyze failed after all retries")
        return "Unable to generate analysis at this time."
    
    except Exception as e:
        logger.error(f"[❌] Unexpected error in analyze(): {str(e)}")
        return "Unable to generate analysis at this time."


__all__ = [
    "respond",
    "summarize",
    "analyze",
    "get_llm_client",
]


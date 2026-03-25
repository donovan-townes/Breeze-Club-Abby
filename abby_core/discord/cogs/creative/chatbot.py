import json
import abby_core.llm.conversation as chat_openai  # Renamed from chat_openai for clarity
import asyncio
import random
import uuid
import time
import discord
import os
from datetime import datetime, timezone
from typing import Optional, Any
from discord import app_commands
from discord.ext import commands

from abby_core.personality.manager import get_personality_manager
from abby_core.llm.context_factory import build_conversation_context
from abby_core.llm.intent import classify_intent, route_intent_to_action
from abby_core.llm.intent_tools import execute_tool
from abby_core.discord.adapters.intent import build_intent_context

# Import platform-agnostic services (lift Discord dependencies)
from abby_core.services.conversation_service import get_conversation_service
from abby_core.services.usage_gate_service import get_usage_gate_service

# Import unified MongoDB client for session management
# sys.path already configured in launch.py
from abby_core.database.mongodb import upsert_user
# Memory envelope system for contextual intelligence (TDOS Memory v1.2)
from tdos_intelligence.memory import (
    get_memory_envelope, format_envelope_for_llm,
    invalidate_cache, add_memorable_fact, update_relational_memory,
    extract_facts_from_summary, analyze_conversation_patterns,
    apply_decay
)
from tdos_intelligence.memory.extraction import (
    add_shared_narrative, get_shared_narratives
)
from tdos_intelligence.memory.storage import MemoryStore
from abby_core.services.memory_service_factory import create_discord_memory_store
from tdos_intelligence.memory.service import MemoryService, create_memory_service
# RAG is now handled by Orchestrator (no direct imports needed)
# Intent-driven RAG retrieval happens automatically for KNOWLEDGE_QUERY
from tdos_intelligence.observability import logging
from abby_core.database.collections.guild_configuration import (
    get_guild_config,
    get_memory_settings,
)
from abby_core.database.collections.users import ensure_user_from_discord

logger = logging.getLogger(__name__)

class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.TIMEOUT_SECONDS = 60.0
        
        self.personality_manager = get_personality_manager()
        
        # Lazy MongoDB initialization - defer connection until first use
        self._memory_store: MemoryStore | None = None
        self._memory_service: MemoryService | None = None
        
        self.user_channel = {}      # Track the channel of each user's chat
        self.active_instances = []  # Track active chatbot instances
        
        # Static prompt cache: {session_id: static_prompt_string}
        # Caches persona core + guild context + boundaries per session
        self._static_prompt_cache = {}
        
        logger.debug(
            "[💬] Chatbot initialized (adapter=discord, memory=mongodb, RAG via Orchestrator)",
            extra={
                "adapter": "discord",
                "memory_backend": "mongodb (lazy)",
                "memory_service_enabled": True,
                "rag_mode": "orchestrator_intent_driven"
            }
        )
    
    @property
    def memory_store(self) -> MemoryStore:
        """Lazy initialization of MongoDB memory store."""
        if self._memory_store is None:
            # Initialize MemoryStore (MongoDB-backed, parameterized for Discord)
            self._memory_store = create_discord_memory_store()
            logger.debug("[Chatbot] MongoDB memory store initialized")
        
        return self._memory_store
    
    @property
    def memory_service(self) -> MemoryService:
        """Lazy initialization of memory service."""
        if self._memory_service is None:
            # This will trigger memory_store property which does the real initialization
            self._memory_service = create_memory_service(
                store=self.memory_store,
                source_id="discord",
                logger=logger
            )
            logger.debug("[Chatbot] Memory service initialized")
        
        return self._memory_service

    def get_greeting(self, user):
        """Generate a role-specific persona-driven greeting via PersonalityManager."""
        name = user.mention
        
        # Determine user role and privileges
        user_role = "member"  # default
        is_bot_creator = False
        
        # Check if bot creator (hardcoded bot creator ID from config)
        bot_creator_id = int(os.getenv("BOT_CREATOR_ID", "0"))
        if bot_creator_id and user.id == bot_creator_id:
            is_bot_creator = True
        
        # Check guild roles if in a guild
        if hasattr(user, 'guild') and user.guild and hasattr(user, 'guild_permissions'):
            if user.guild.owner_id == user.id:
                user_role = "owner"
            elif user.guild_permissions.administrator:
                user_role = "admin"
            elif user.guild_permissions.manage_messages or user.guild_permissions.manage_channels:
                user_role = "moderator"
        
        persona_name = self.personality_manager.get_active_persona_name()
        greet = self.personality_manager.get_greeting_for_persona(
            persona_name, 
            formal=False,
            user_role=user_role,
            is_bot_creator=is_bot_creator
        )
        return f"{greet} {user.mention}"
    
    async def send_message(self, channel, message):
        if len(message) <= 2000:
            await channel.send(message)
        else:
            chunks = [message[i: i + 1999] for i in range(0, len(message), 1999)]
            for chunk in chunks:
                await channel.send(chunk)
            
    def remove_user(self, user_id):
        if user_id in self.active_instances:
            self.active_instances.remove(user_id)   # Remove the user from active instances
        self.user_channel.pop(user_id, None)        # Reset user channel after conversation ends
    
    def end_cleanup(self,user,start_time):
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.info(
            "conversation_ended",
            extra={
                "user_id": str(user.id),
                "username": user.name,
                "elapsed_seconds": round(elapsed_time, 4)
            }
        )
    
    async def end_summary(self,user_id,session_id,chat_history,guild_id=None):
        # === MEMORY ENVELOPE: Extract facts and update creative_profile ===
        logger.info(
            "generating_summary",
            extra={"user_id": user_id, "session_id": session_id}
        )
        
        # Filter out memory context (first item with "Memory Context" as input)
        # Only summarize actual conversation exchanges from this session
        actual_conversation = [
            item for item in chat_history 
            if "Memory Context" not in item.get("input", "")
        ]
        
        logger.info(
            "summarizing_conversation",
            extra={
                "user_id": user_id,
                "conversation_length": len(actual_conversation),
                "excluded_memory_context": True
            }
        )
        
        # Don't generate summary if conversation too short or no LLM calls
        # Heuristic: if all responses are tool outputs (short, structured), skip summary
        if len(actual_conversation) == 0:
            logger.info(
                "summary_skipped_no_exchanges",
                extra={"user_id": user_id}
            )
            conversation_service = get_conversation_service()
            success, error = conversation_service.close_session(
                int(user_id), session_id, summary=None, reason="completed"
            )
            if error:
                logger.warning(f"Failed to close session: {error}")
            return
        
        # Skip summarization if conversation is tool-only (no LLM reasoning)
        # Heuristic: Check if responses are predominantly tool outputs (short, no conversational depth)
        total_response_length = sum(len(item.get("response", "")) for item in actual_conversation)
        avg_response_length = total_response_length / len(actual_conversation) if actual_conversation else 0
        
        # If responses are very short (< 100 chars avg), likely tool-only execution
        if avg_response_length < 100 and len(actual_conversation) <= 3:
            logger.info(
                "summary_skipped_tool_only_conversation",
                extra={
                    "user_id": user_id,
                    "avg_response_length": avg_response_length,
                    "conversation_length": len(actual_conversation),
                    "reason": "No LLM conversation detected (tool-only execution)"
                }
            )
            conversation_service = get_conversation_service()
            success, error = conversation_service.close_session(
                int(user_id), session_id, summary=None, reason="completed"
            )
            if error:
                logger.warning(f"Failed to close session: {error}")
            return
        
        recent_chat_history = actual_conversation[-5:] if len(actual_conversation) >= 5 else actual_conversation
        summary = await chat_openai.summarize(recent_chat_history)
        
        # Close session with summary using ConversationService
        conversation_service = get_conversation_service()
        success, error = conversation_service.close_session(
            int(user_id), session_id, summary=summary, reason="completed"
        )
        if error:
            logger.warning(f"Failed to close session: {error}")
        
        # === SPAWN ASYNC BACKGROUND TASK FOR MEMORY EXTRACTION ===
        # Don't block Discord event loop - run extraction in background
        asyncio.create_task(self._extract_and_update_memory(
            user_id, guild_id, summary, actual_conversation
        ))
        
        # Invalidate memory cache immediately so next conversation gets fresh data
        invalidate_cache(user_id, guild_id, source_id="discord")
        logger.info(
            "memory_cache_invalidated",
            extra={"user_id": user_id, "guild_id": guild_id, "reason": "session_closed", "source_id": "discord"}
        )
    
    async def _extract_and_update_memory(self, user_id, guild_id, summary, actual_conversation):
        """
        Background task: Extract facts and update memory without blocking Discord event loop.
        Runs asynchronously so heartbeat/event processing continues normally.
        
        Uses MemoryService for all memory operations (adapter-agnostic).
        """
        try:
            await asyncio.sleep(0.1)  # Yield to event loop first
            
            # === LLM-BASED MEMORY EXTRACTION ===
            profile = None  # Initialize to avoid UnboundLocalError
            
            try:
                # Ensure profile exists using MemoryService abstraction
                profile = self.memory_service.get_profile(user_id, guild_id)
                if not profile:
                    logger.warning(
                        "profile_not_found_during_extraction",
                        extra={"user_id": user_id, "guild_id": guild_id}
                    )
                    # Create minimal profile using MemoryService abstraction
                    self.memory_service.ensure_user_profile(
                        user_id=user_id,
                        guild_id=guild_id,
                        metadata={"username": f"User_{user_id[:8]}"}
                    )
                    profile = self.memory_service.get_profile(user_id, guild_id)
                
                # 1. Extract memorable facts from summary (validated & typed)
                logger.info(
                    "extracting_memorable_facts",
                    extra={"user_id": user_id, "summary_length": len(summary)}
                )
                extracted_facts = extract_facts_from_summary(summary, user_id)  # ← CHANGED: No conversation_exchanges param
                
                # Filter for USER_FACT type (only these go to profile)
                user_facts = [f for f in extracted_facts if f.get("type") == "USER_FACT"]
                
                # Add each fact to user's memory using MemoryService
                facts_stored_count = 0
                for fact_data in user_facts:
                    fact_text = fact_data.get("text") or fact_data.get("fact")
                    if not fact_text:  # Skip if no fact text found
                        continue
                    
                    success = self.memory_service.add_fact(
                        user_id=user_id,
                        guild_id=guild_id,
                        fact_text=fact_text,  # Now guaranteed to be str
                        source=fact_data.get("source", "llm_extraction"),
                        confidence=fact_data["confidence"],
                        origin=fact_data.get("origin", "explicit"),
                        category=fact_data.get("category")
                    )
                    if success:
                        facts_stored_count += 1
                        logger.info(
                            "fact_stored",
                            extra={
                                "user_id": user_id,
                                "confidence": round(fact_data['confidence'], 2),
                                "fact_preview": fact_text[:50],
                                "fact_type": "USER_FACT"
                            }
                        )
                    else:
                        logger.warning(
                            "fact_storage_failed",
                            extra={
                                "user_id": user_id,
                                "fact_preview": fact_text[:50]
                            }
                        )
                
                if facts_stored_count > 0:
                    logger.info(
                        "facts_batch_stored",
                        extra={
                            "user_id": user_id,
                            "stored_count": facts_stored_count,
                            "total_extracted": len(user_facts)
                        }
                    )
                
                # 2. Analyze conversation patterns for domains/preferences
                if len(actual_conversation) >= 2:
                    logger.info(
                        "analyzing_conversation_patterns",
                        extra={"user_id": user_id, "conversation_length": len(actual_conversation)}
                    )
                    
                    existing_profile = profile.get("creative_profile", {}) if profile else {}
                    
                    # Create adapter function for TDOS Memory compatibility
                    # ARCHITECTURAL NOTE:
                    # - TDOS Memory's analyze_conversation_patterns is SYNCHRONOUS
                    # - It expects llm_chat_fn(prompt, user_id, chat_history=[]) → str
                    # - Our chat() is ASYNC and needs ConversationContext
                    # - We're already in an async context (background task)
                    # 
                    # SOLUTION: Use ThreadPoolExecutor to run async code in separate thread
                    # This is the standard pattern for sync-calling-async when already in async context
                    from concurrent.futures import ThreadPoolExecutor
                    import threading
                    
                    def tdos_memory_llm_adapter(prompt: str, user_id_str: str, chat_history=None):
                        """
                        Adapter to bridge TDOS Memory's synchronous call with our async chat.
                        
                        Uses ThreadPoolExecutor to run async code in a separate thread
                        with its own event loop, avoiding the "already running" error.
                        """
                        def run_in_thread():
                            # Create new event loop for this thread
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                # Build context and run chat
                                async def _run_chat():
                                    context = build_conversation_context(
                                        user_id=user_id_str,
                                        chat_history=chat_history or [],
                                        guild_id=guild_id if guild_id else None
                                    )
                                    if context:
                                        return await chat_openai.respond(prompt, context)
                                    return ""  # Fallback if context build fails
                                
                                return loop.run_until_complete(_run_chat())
                            finally:
                                loop.close()
                        
                        # Run in thread pool and wait for result
                        with ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(run_in_thread)
                            return future.result()  # Blocks until complete
                    
                    def analytical_llm_adapter(prompt: str, user_id_str: str, chat_history=None):
                        """
                        Boring adapter for pattern extraction.
                        Uses minimal analytical prompt - no persona, no style.
                        """
                        def run_in_thread():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                async def _run_chat():
                                    # Build analytical prompt (no persona, no data duplication)
                                    analytical_prompt = self.personality_manager.build_analytical_prompt(
                                        task_description="Extract conversation patterns as JSON"
                                    )
                                    
                                    # Build minimal context for analytical work (no guild/user context needed)
                                    context = build_conversation_context(
                                        user_id=user_id_str or user_id,
                                        chat_history=chat_history or [],
                                        guild_id=guild_id if guild_id else None,
                                        user_name=None,
                                        user_level="member",
                                        is_owner=False,
                                        is_final_turn=False,
                                        user_role="member",
                                        is_bot_creator=False,
                                        turn_number=1  # Pattern analysis is always step 1 of analysis
                                    )
                                    # Override system message with analytical prompt
                                    if context:
                                        context.persona.system_message = analytical_prompt
                                        # Set to deterministic temperature
                                        context.temperature = 0.0
                                        # Pass data as user message (not in system prompt)
                                        return await chat_openai.respond(prompt, context)
                                    return ""  # Fallback if context build fails
                                
                                return loop.run_until_complete(_run_chat())
                            finally:
                                loop.close()
                        
                        with ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(run_in_thread)
                            return future.result()
                    
                    # Analyze patterns (use boring prompt)
                    pattern_result = analyze_conversation_patterns(
                        summary=summary,
                        user_id=user_id,
                        existing_profile=existing_profile,
                        llm_chat_fn=analytical_llm_adapter,  # Boring adapter with minimal context
                        logger=logger
                    )
                    
                    # Check if pattern updates are proposed
                    if pattern_result and pattern_result.get("proposed_updates"):
                        proposed = pattern_result["proposed_updates"]
                        confidence = pattern_result.get("confidence", 0)
                        requires_confirmation = pattern_result.get("requires_confirmation", False)
                        
                        # Override package default: lower threshold to 0.65 for Abby's conversational context
                        # (package default 0.8 is too strict for explicit conversation mentions)
                        override_confidence_threshold = 0.65
                        should_apply = confidence >= override_confidence_threshold and not requires_confirmation
                        
                        if not should_apply and requires_confirmation:
                            # Low confidence — log for review, don't auto-apply
                            logger.warning(
                                "pattern_update_low_confidence",
                                extra={
                                    "user_id": user_id,
                                    "confidence": round(confidence, 2),
                                    "threshold": override_confidence_threshold,
                                    "proposed_fields": list(proposed.keys())
                                }
                            )
                        elif should_apply:
                            # Confidence acceptable — safe to apply automatically
                            # Update profile with pattern changes using MemoryService
                            if pattern_result.get("proposed_updates"):
                                success = self.memory_service.update_profile_metadata(
                                    user_id=user_id,
                                    guild_id=guild_id,
                                    updates=proposed,
                                    confidence=confidence
                                )
                                if success:
                                    logger.info(
                                        "pattern_updates_applied",
                                        extra={
                                            "user_id": user_id,
                                            "confidence": round(confidence, 2),
                                            "updated_fields": list(proposed.keys())
                                        }
                                    )
                    else:
                        logger.debug(
                            "no_pattern_updates",
                            extra={"user_id": user_id}
                        )
                
                # 3. Invalidate cache after extraction/pattern updates
                # NOTE: Decay is already applied by envelope.py at read-time, so we don't apply it here
                # (applying it twice would double-penalize facts)
                invalidate_cache(user_id, guild_id, source_id="discord")

            except Exception as e:
                logger.error(
                    "memory_extraction_failed",
                    extra={"user_id": user_id, "error": str(e)},
                    exc_info=True
                )
                # Don't fail if extraction fails
        
        except Exception as e:
            logger.error(
                "background_extraction_task_failed",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True
            )
    
    async def user_chat_mode(self, user_id, chat_history, user_input, session_id=None, persona_name=None, is_final_turn=False, memory_envelope=None):
        """Generate chatbot response with optional RAG context injection.
        
        Args:
            user_id: Discord user ID
            chat_history: List of previous exchanges
            user_input: Discord message object
            session_id: Current session ID for static prompt cache lookup
            persona_name: Optional persona override
            is_final_turn: If True, instructs LLM to naturally close conversation
            memory_envelope: Raw TDOS memory envelope (will be formatted with budget + relevance)
        """
        content = user_input.content
        
        # Load memory envelope if not provided (for call sites outside __call__)
        if memory_envelope is None:
            guild_id_for_memory = None
            if hasattr(user_input, 'guild') and user_input.guild:
                guild_id_for_memory = str(user_input.guild.id)
            
            try:
                memory_envelope = self.memory_service.get_memory_envelope(
                    user_id, 
                    guild_id_for_memory, 
                    force_refresh=False
                )
            except (ValueError, ConnectionError) as e:
                logger.warning(
                    "memory_envelope_error_in_chat_mode",
                    extra={"user_id": user_id, "error": str(e)}
                )
                memory_envelope = None

        # RAG REMOVED: Now handled by Orchestrator for KNOWLEDGE_QUERY intents
        # This ensures consistent RAG injection across all entry points
        # See: tdos_intelligence/orchestrator.py -> _process_knowledge_query()

        # Build ConversationContext using PersonalityManager
        memory_context = None
        if chat_history and isinstance(chat_history[0], dict):
            first_entry = chat_history[0]
            if "Memory Context" in first_entry.get("input", ""):
                memory_context = first_entry.get("response")
                # Exclude memory context from conversation history passed to chat
                history_for_llm = chat_history[1:]
            else:
                history_for_llm = chat_history
        else:
            history_for_llm = chat_history

        # Derive guild-level flags
        guild = getattr(user_input, 'guild', None)
        member = guild.get_member(int(user_id)) if guild else None
        is_owner = bool(guild and getattr(guild, 'owner_id', None) == int(user_id))
        
        # Detect user role and privileges
        user_role = "member"  # default
        is_bot_creator = False
        
        # Check if bot creator
        bot_creator_id = int(os.getenv("BOT_CREATOR_ID", "0"))
        if bot_creator_id and int(user_id) == bot_creator_id:
            is_bot_creator = True
        
        # Check guild roles
        if guild and member and hasattr(member, 'guild_permissions'):
            if is_owner:
                user_role = "owner"
            elif member.guild_permissions.administrator:
                user_role = "admin"
            elif member.guild_permissions.manage_messages or member.guild_permissions.manage_channels:
                user_role = "moderator"
        
        # Derive user_level (legacy name, for compatibility)
        if is_owner:
            user_level = "owner"
        elif member and getattr(member, 'guild_permissions', None) and member.guild_permissions.administrator:
            user_level = "admin"
        elif member and getattr(member, 'guild_permissions', None) and (
            member.guild_permissions.manage_guild or
            member.guild_permissions.manage_messages or
            member.guild_permissions.kick_members or
            member.guild_permissions.ban_members
        ):
            user_level = "moderator"
        else:
            user_level = "member"

        display_name = None
        if hasattr(user_input, 'author') and user_input.author:
            display_name = getattr(user_input.author, 'display_name', None) or getattr(user_input.author, 'name', None)

        # Lookup cached static prompt for this session
        cached_static_prompt = self._static_prompt_cache.get(session_id) if session_id else None
        
        # Calculate turn number (1-based) from chat history length
        turn_number = len(chat_history) + 1 if chat_history else 1

        # Classify user intent for memory injection heuristics
        user_intent = classify_intent(content)
        logger.info(f"[intent] Turn {turn_number}: {user_intent.value} (message: {content[:50]}...)")

        # Route intent to action using Discord adapter for platform-agnostic context
        intent_context = build_intent_context(
            user=user_input.author,
            guild=guild,
            bot=self.bot,
            message_content=content,
            user_level=user_level,
            is_owner=is_owner,
        )
        action = route_intent_to_action(user_intent, context=intent_context)
        
        # IMPORTANT: Skip memory injection for tool-based intents (task/config)
        # Memory is only needed for LLM paths (casual chat, creative, analysis)
        if not action.use_llm:
            logger.info(f"[memory] Skipping memory injection for {user_intent.value} (tool-based intent)")
            memory_envelope = None
        
        # If action doesn't require LLM, execute tool or return pre-computed response
        if not action.use_llm:
            logger.info(f"[intent_route] Returning non-LLM response: action_type={action.action_type}")
            
            # Execute actual tool if action_type is "tool"
            if action.action_type == "tool":
                try:
                    tool_result = await execute_tool(action, bot=self.bot)
                    
                    # Return dict as-is so caller can handle embed sending
                    # (embed will be sent by user_chat_mode caller with proper channel context)
                    if isinstance(tool_result, dict):
                        return tool_result  # Return dict with text + optional embed
                    else:
                        # Backward compatibility if tool returns string
                        return tool_result
                except Exception as e:
                    logger.error(f"[intent_tools] Tool execution failed: {e}")
                    return f"Tool execution error: {str(e)}"
            
            # Otherwise return pre-computed text
            return action.text or "Acknowledged."

        # Otherwise, proceed with LLM call
        context = build_conversation_context(
            user_id=user_id,
            chat_history=history_for_llm,
            memory_envelope=memory_envelope,  # Pass raw envelope; formatting happens in factory with token budget
            rag_context=None,
            guild_id=(int(guild.id) if guild else None),
            guild_name=(guild.name if guild else None),
            user_name=display_name,
            user_level=user_level,
            is_owner=is_owner,
            persona_name=persona_name,  # Pass the cached persona name to avoid re-fetching
            is_final_turn=is_final_turn,  # Pass final turn flag to system prompt builder
            user_role=user_role,  # Pass role for role-based farewells
            is_bot_creator=is_bot_creator,  # Pass bot creator status
            static_prompt_cache=cached_static_prompt,  # Pass cached static prompt
            turn_number=turn_number,  # Pass turn number for conditional guild context
            user_message=content,  # Pass for conditional memory injection heuristics
            intent=user_intent.value,  # Pass classified intent as string for memory injection decision
            max_memory_tokens=300,  # Token budget for memory (300 tokens = ~1200 chars)
            session_id=session_id,  # Pass session_id for audit logging
        )

        # Apply hard context ceiling guard before LLM call
        context = self._apply_context_ceiling(context, content, max_total_tokens=2000)

        response = await chat_openai.respond(
            content,
            context,
        )
        return response

    def _apply_context_ceiling(self, context, user_content: str, max_total_tokens: int = 2000) -> Any:
        """Apply hard context ceiling guard before LLM call.
        
        Args:
            context: ConversationContext object
            user_content: Current user message
            max_total_tokens: Maximum total tokens allowed (default 2000)
        
        Returns:
            Modified context if over ceiling, otherwise original
        """
        # Rough token estimation: 1 token ~= 4 chars
        def estimate_tokens(text: str) -> int:
            return len(text) // 4
        
        system_tokens = estimate_tokens(context.persona.system_message or "")
        user_tokens = estimate_tokens(user_content)
        history_tokens = sum(
            estimate_tokens(str(msg.get("input", ""))) + 
            estimate_tokens(str(msg.get("response", ""))) 
            for msg in (context.chat_history or [])
        )
        
        total_estimated = system_tokens + user_tokens + history_tokens
        
        if total_estimated <= max_total_tokens:
            return context
        
        # Over ceiling - apply pruning strategy
        logger.warning(
            "context_ceiling_exceeded",
            extra={
                "estimated_tokens": total_estimated,
                "max_tokens": max_total_tokens,
                "system_tokens": system_tokens,
                "user_tokens": user_tokens,
                "history_tokens": history_tokens
            }
        )
        
        # Pruning order: older chat history first, memory last
        overage = total_estimated - max_total_tokens
        
        if history_tokens > 0 and overage > 0:
            # Drop oldest messages first
            messages_to_keep = len(context.chat_history or [])
            while messages_to_keep > 0 and overage > 0:
                messages_to_keep -= 1
                dropped_msg = context.chat_history[0] if context.chat_history else {}
                dropped_tokens = estimate_tokens(str(dropped_msg.get("input", ""))) + \
                                estimate_tokens(str(dropped_msg.get("response", "")))
                overage -= dropped_tokens
                if context.chat_history:
                    context.chat_history = context.chat_history[1:]
            
            logger.info(
                "context_pruned",
                extra={
                    "pruned_messages": len(context.chat_history or []) - messages_to_keep,
                    "new_estimated_tokens": total_estimated - overage
                }
            )
        
        return context

    async def user_update_chat_history(self,user_id,session_id, chat_history,user_input,response):
        # Append both user message and assistant response to session (handles encryption)
        conversation_service = get_conversation_service()
        success, error = conversation_service.record_exchange(
            user_id=user_id,
            session_id=session_id,
            user_message=user_input.content,
            assistant_message=response
        )
        if error:
            logger.warning(f"Failed to record exchange: {error}")
        
        chat_history.append(
            {
                "input": user_input.content,
                "response": response,
            }
        )
        logger.info(
            "chat_history_updated",
            extra={"user_id": user_id, "session_id": session_id}
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for all messages and check for summon triggers."""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Ignore DMs (only listen in guilds)
        if not message.guild:
            return
        
        # Only process in the specific bot channel if configured
        if message.author.id == self.bot.user.id:
            return
        
        try:
            # Delegate to handle_chatbot for summon detection
            await self.handle_chatbot(self.bot, message)
        except Exception as e:
            logger.error(
                "on_message_error",
                extra={"user_id": str(message.author.id), "error": str(e)},
                exc_info=True
            )

    def initalize_user(self,user_id,session_id,message):
        # === MEMORY ENVELOPE SYSTEM (3-Layer Architecture) ===
        # Replaces legacy summary chain with structured, cached memory
        logger.info(
            "initializing_user_session",
            extra={"user_id": user_id, "session_id": session_id, "loading_memory": True}
        ) 
        
        # Ensure user has a profile with up-to-date Discord metadata
        # Uses canonical database-side function (not MemoryService method)
        ensure_user_from_discord(message.author, message.guild)
        
        # Upsert user metadata using unified client
        upsert_user(user_id, message.author.name)
        
        # Guild ID - pass as int, tdos_memory will handle type conversion internally
        guild_id = int(message.guild.id) if message.guild else None
        
        # Initialize chat history with memory envelope context
        chat_history = []
        
        # Get or build memory envelope (cached 15min)
        # Uses MemoryService with source_id for multi-adapter isolation
        try:
            envelope = self.memory_service.get_memory_envelope(user_id, str(guild_id) if guild_id else None, force_refresh=False)
            
            # Log envelope loaded (formatting now happens in context_factory with token budget)
            if envelope:
                logger.info(
                    "memory_envelope_loaded",
                    extra={
                        "user_id": user_id,
                        "facts_count": len(envelope.get('relational', {}).get('memorable_facts', [])),
                        "has_recent_context": bool(envelope.get('recent_context'))
                    }
                )
            else:
                logger.info(
                    "memory_envelope_not_found",
                    extra={"user_id": user_id}
                )
        except (ValueError, ConnectionError) as e:
            logger.warning(
                "memory_envelope_error",
                extra={"user_id": user_id, "guild_id": guild_id, "error": str(e)},
            )
            envelope = None  # Gracefully degrade - continue without memory
        
        # Create new session using ConversationService
        try:
            conversation_service = get_conversation_service()
            session, error = conversation_service.create_session(
                user_id=int(user_id),
                session_id=session_id,
                channel_id=message.channel.id,
                guild_id=int(guild_id) if guild_id else None,
            )
            if error:
                logger.warning(
                    "session_creation_error",
                    extra={"user_id": user_id, "session_id": session_id, "error": error}
                )
                # Continue without persisting session - user can still chat
        except Exception as e:
            logger.warning(
                "session_creation_error",
                extra={"user_id": user_id, "session_id": session_id, "error": str(e)}
            )
            # Continue without persisting session - user can still chat
        
        return chat_history, envelope

    async def handle_chatbot(self, client, message):
        """Handle incoming message and summon chatbot if triggers detected."""
        # logger.info("[💭] Handling Chatbot")
        start_time = time.perf_counter()
        user_id = str(message.author.id)
        guild_id = str(message.guild.id) if message.guild else None

        # If the bot is already active for the user, return
        if user_id in self.active_instances:
            logger.info(
                "chatbot_already_active",
                extra={"user_id": user_id}
            )
            return
        # Check guild settings for summon mode
        settings = get_memory_settings(int(guild_id) if guild_id else 0)
        summon_mode = settings.get("conversation", {}).get("summon_mode", "both")
        default_chat_mode = settings.get("conversation", {}).get("default_chat_mode", "multi_turn")

        # If slash-only mode, skip mention-based summoning
        if summon_mode == "slash_only":
            return

        # Check for summon words using current persona triggers
        # This is the ONLY place get_persona should be called for every message
        if self.personality_manager.check_summon_trigger(message.content):
            logger.info(
                "chatbot_summoned",
                extra={"user_id": user_id}
            )
            # Set the user's channel if not already set
            if user_id not in self.user_channel:
                logger.info(
                    "user_channel_set",
                    extra={"user_id": user_id, "channel_id": str(message.channel.id)}
                )
                self.user_channel[user_id] = message.channel

            # Send a persona-specific processing message
            processing_text = self.personality_manager.get_processing_message(
                self.personality_manager.get_active_persona_name()
            )
            processing_message = await message.channel.send(processing_text)

            # Create new session ID for the user
            session_id = str(uuid.uuid4())
            
            # --- Close any old active sessions for this user before creating new one ---
            try:
                conversation_service = get_conversation_service()
                expired_count, error = conversation_service.expire_active_sessions(
                    int(user_id), 
                    int(guild_id) if guild_id else None
                )
                if error:
                    logger.warning(f"[session_cleanup] Failed to close old sessions for user {user_id}: {error}")
            except Exception as e:
                logger.warning(f"[session_cleanup] Failed to close old sessions for user {user_id}: {e}")

            # NOTE: Usage gate is checked ONLY on follow-up messages, not on initial summon
            # Initial summon always creates a fresh session

            # Ignore the message if the user is in a different channel
            if message.channel != self.user_channel[user_id]:
                logger.info(
                    "user_in_different_channel",
                    extra={"user_id": user_id, "current_channel": str(message.channel.id)}
                )
                return 

            # Initialize the user's chat history
            chat_history, envelope = self.initalize_user(user_id, session_id, message)

            # Build and cache static prompt for this session (one-time cost)
            guild = message.guild
            member = guild.get_member(int(user_id)) if guild else None
            is_owner = bool(guild and getattr(guild, 'owner_id', None) == int(user_id))
            user_role = "member"
            if is_owner:
                user_role = "owner"
            elif member and hasattr(member, 'guild_permissions'):
                if member.guild_permissions.administrator:
                    user_role = "admin"
                elif member.guild_permissions.manage_messages or member.guild_permissions.manage_channels:
                    user_role = "moderator"
            
            persona = self.personality_manager.get_persona(
                self.personality_manager.get_active_persona_name()
            )
            if persona:
                static_prompt = self.personality_manager.build_static_prompt(
                    persona=persona,
                    guild_name=guild.name if guild else "the server",
                    user_level="owner" if is_owner else "member",
                    is_owner=is_owner,
                    user_mention=message.author.mention,
                    max_response_length=1200,
                    user_role=user_role
                )
                self._static_prompt_cache[session_id] = static_prompt
                logger.debug(f"[StaticPromptCache] Cached for session {session_id[:8]}")

            # Extract user input after summon word (if any)
            message_lower = message.content.lower()
            user_input_text = message.content
            active_persona = self.personality_manager.get_persona(
                self.personality_manager.get_active_persona_name()
            )
            if active_persona and active_persona.summon and active_persona.summon.triggers:
                for trig in active_persona.summon.triggers:
                    if trig.lower() in message_lower:
                        if message_lower.startswith(trig.lower()):
                            user_input_text = message.content[len(trig) :].strip()
                        break

            # Add the user to active instances    
            self.active_instances.append(user_id)

            # Get the active persona name once at session start (don't re-fetch on every message)
            active_persona_name = self.personality_manager.get_active_persona_name()

            if user_input_text:
                # If there is an input after the summon word, process it as usual
                class MockMessage:
                    def __init__(self, original_message, new_content):
                        self.content = new_content
                        self.author = original_message.author
                        self.channel = original_message.channel
                        self.guild = original_message.guild

                mock_message = MockMessage(message, user_input_text)
                response = await self.user_chat_mode(
                    user_id, 
                    chat_history, 
                    mock_message,
                    session_id=session_id,
                    persona_name=active_persona_name,
                    memory_envelope=envelope
                )

                # Delete the "processing" message and send the actual response
                await processing_message.delete()
                await self.send_message(message.channel, response)

                # Update the chat history after each response
                await self.user_update_chat_history(user_id, session_id, chat_history, mock_message, response)
            else:
                # If there is no input after the summon word, update the processing message with a greeting
                greeting = self.get_greeting(message.author)
                await processing_message.edit(content=greeting)

            # Log Chatbot Startup Time
            end_time = time.perf_counter()
            elapsed_time = end_time - start_time
            logger.info(
                "chatbot_startup_complete",
                extra={"elapsed_seconds": round(elapsed_time, 4)}
            )

            # Continue the listener loop (persona_name already captured above)
            await self.handle_conversation(
                client, message, user_id, session_id, chat_history, 
                persona_name=active_persona_name
            )

    async def handle_conversation(self, client, message_or_interaction, user_id, session_id, chat_history, persona_name=None):
        """Main conversation loop handling multi-turn interactions."""
        user = message_or_interaction.user if hasattr(message_or_interaction, 'user') else message_or_interaction.author
        guild_id = str(message_or_interaction.guild.id) if message_or_interaction.guild else None
        
        logger.info(
            "handling_conversation",
            extra={"user_id": str(user.id), "username": user.name}
        ) 
        start_time = time.perf_counter()
        
        # Calculate user role and bot creator status for farewells
        guild = message_or_interaction.guild
        member = guild.get_member(int(user_id)) if guild else None
        is_owner = bool(guild and getattr(guild, 'owner_id', None) == int(user_id))
        
        user_role = "member"  # default
        is_bot_creator = False
        
        # Check if bot creator
        bot_creator_id = int(os.getenv("BOT_CREATOR_ID", "0"))
        if bot_creator_id and int(user_id) == bot_creator_id:
            is_bot_creator = True
        
        # Check guild roles
        if guild and member and hasattr(member, 'guild_permissions'):
            if is_owner:
                user_role = "owner"
            elif member.guild_permissions.administrator:
                user_role = "admin"
            elif member.guild_permissions.manage_messages or member.guild_permissions.manage_channels:
                user_role = "moderator"
        
        # Determine message channel
        if hasattr(message_or_interaction, 'channel'):
            message_channel = message_or_interaction.channel
        else:
            message_channel = message_or_interaction.channel

        # Start the conversation loop
        user_input = None  # Initialize to avoid possibly-unbound error
        response_to_log = None  # Initialize for farewell logic
        is_tool_only = False  # Initialize for farewell logic
        while True:
            try:
                # Wait for user input
                user_input = await client.wait_for(
                    "message", 
                    timeout=self.TIMEOUT_SECONDS, 
                    check=lambda m: m.author == user and not m.content.startswith('!') and m.channel == self.user_channel[user_id]
                )

                # Track exchange count
                
                # --- USAGE GATE: Atomic turn limit check-and-increment ---
                usage_gate_service = get_usage_gate_service()
                conversation_service = get_conversation_service()
                session_obj, error_msg = conversation_service.get_active_session(
                    int(user.id),
                    int(guild_id) if guild_id else None
                )
                
                if not session_obj:
                    logger.error(f"[usage_gate] No session found for user {user_id} (guild={guild_id}) - error: {error_msg}")
                    await user_input.channel.send("Sorry, I lost track of our conversation. Please try again!")
                    self.remove_user(user_id)
                    self.end_cleanup(user, start_time)
                    break
                
                # Get config to determine max turns
                guild_config = get_memory_settings(int(guild_id) if guild_id else 0)
                usage_limits = guild_config.get("usage_limits", {})
                conv_limits = usage_limits.get("conversation", {})
                max_turns = conv_limits.get("max_turns_per_session", 3)
                
                # Extract session_id (guaranteed to exist at this point, but Pylance needs explicit check)
                session_id = session_obj.get("session_id")
                if not session_id:
                    logger.error(f"[usage_gate] Session object missing session_id for user {user_id}")
                    await user_input.channel.send("Sorry, I lost track of our conversation. Please try again!")
                    self.remove_user(user_id)
                    self.end_cleanup(user, start_time)
                    break
                
                # Atomically increment turn and check limit
                logger.info(f"[usage_gate] Attempting atomic turn increment for session {session_id[:8]}... (max={max_turns})")
                turn_result = usage_gate_service.increment_and_check_turn_limit(
                    session_id=session_id,
                    max_turns=max_turns
                )
                
                # Check if increment failed (limit exceeded or error)
                if isinstance(turn_result, tuple) and turn_result[0] is None:
                    # Error occurred
                    error_msg = turn_result[1]
                    logger.error(f"[usage_gate] Turn increment failed for user {user_id}: {error_msg}")
                    await user_input.channel.send("Sorry, something went wrong. Please try again!")
                    self.remove_user(user_id)
                    self.end_cleanup(user, start_time)
                    break
                
                allowed, new_turn_count, is_final_turn = turn_result
                
                if not allowed:
                    # Turn limit exceeded - send graceful closure
                    response_text = self.personality_manager.get_usage_gate_message(
                        "turn_limit_reached"
                    )
                    await user_input.channel.send(response_text)
                    
                    # Extract summary and close session
                    await self.end_summary(
                        user_id=user_id,
                        session_id=session_obj.get("session_id"),
                        chat_history=chat_history,
                        guild_id=str(guild_id) if guild_id else None
                    )
                    
                    success, error = await usage_gate_service.close_session_gracefully(
                        user_id=int(user.id),
                        session_id=str(session_obj.get("session_id")),
                        reason="completed"
                    )
                    if error:
                        logger.warning(f"Failed to close session: {error}")
                    
                    # End conversation
                    self.remove_user(user_id)
                    self.end_cleanup(user, start_time)
                    logger.info(f"[usage_gate] Turn limit exceeded for user {user_id} ({new_turn_count}/{max_turns})")
                    break
                
                # Turn incremented successfully - create gate result for downstream use
                class GateResult:
                    def __init__(self, allowed, is_final_turn):
                        self.allowed = allowed
                        self.is_final_turn = is_final_turn
                        self.turn_limit_hit = False
                        self.session_expired = False
                
                gate_result = GateResult(allowed=True, is_final_turn=is_final_turn)
                logger.debug(f"[usage_gate] User {user_id} turn {new_turn_count}/{max_turns} (final={is_final_turn})")
                
                # All conversation length control now via turn limits (atomic, persistent)
                
                # If the user says the dismiss word, send a message and reset the chatbot
                dismiss_triggered = self.personality_manager.check_dismiss_trigger(user_input.content)
                if dismiss_triggered:
                    # Get persona farewell for the user's role
                    # Dismissal is checked BEFORE getting LLM response for current message,
                    # so only send farewell (don't append stale response_to_log from previous turn)
                    persona_farewell = self.personality_manager.get_farewell_for_persona(
                        persona_name=self.personality_manager.get_active_persona_name(),
                        user_role=user_role,
                        is_bot_creator=is_bot_creator
                    )
                    await user_input.channel.send(persona_farewell)
                    self.remove_user(user_id)
                    # Generate a summary of last conversation
                    guild_id = str(user_input.guild.id) if user_input.guild else None
                    await self.end_summary(user_id,session_id,chat_history,guild_id)
                    # End the conversation
                    self.end_cleanup(user,start_time)
                    break

                async with user_input.channel.typing():
                    # Check user's chat mode and respond accordingly
                    # Pass is_final_turn flag from gate check to enable natural closure
                    response = await self.user_chat_mode(
                        user_id, 
                        chat_history, 
                        user_input,
                        session_id=session_id,
                        persona_name=persona_name,
                        is_final_turn=gate_result.is_final_turn
                    )

                # Handle tool responses with embeds or text
                # Tool responses return dicts with text + optional embed
                response_to_log = None
                if isinstance(response, dict):
                    if response.get("embed"):
                        # Send embed only; suppress text to avoid duplicate output
                        await user_input.channel.send(embed=response["embed"])
                        response_to_log = ""  # No text to log for embed-only
                    else:
                        response_text = response.get("text", "")
                        if response_text:
                            await self.send_message(user_input.channel, response_text)
                            response_to_log = response_text
                        else:
                            response_to_log = ""
                    # Tool-only conversation - don't trigger summarization
                    # Summarization should only happen for actual LLM exchanges
                    is_tool_only = True
                else:
                    # Normal text response (from LLM)
                    await self.send_message(user_input.channel, response)
                    response_to_log = response
                    is_tool_only = False

                # Update the chat history after each response (only when we have text)
                if response_to_log:
                    await self.user_update_chat_history(user_id,session_id, chat_history,user_input,response_to_log)
                
                # Note: Turn count already incremented atomically before LLM call
                # No need for separate update_session_after_turn call
                
                # If this was the final turn, end conversation gracefully after response
                if gate_result.is_final_turn:
                    # Don't send extra farewell - LLM already includes farewell in its final response
                    # Extract conversation summary before closing
                    conversation_service = get_conversation_service()
                    session_obj, _ = conversation_service.get_active_session(
                        int(user.id),
                        int(guild_id) if guild_id else None
                    )
                    
                    if session_obj:
                        await self.end_summary(
                            user_id=user_id,
                            session_id=session_obj.get("session_id"),
                            chat_history=chat_history,
                            guild_id=str(guild_id) if guild_id else None
                        )
                    
                    # Close session gracefully
                    if session_obj:
                        usage_gate_service = get_usage_gate_service()
                        session_id = session_obj.get("session_id")
                        if session_id:
                            success, error = await usage_gate_service.close_session_gracefully(
                                user_id=int(user.id),
                                session_id=str(session_id),
                                reason="completed"
                            )
                            if error:
                                logger.warning(f"Failed to close session: {error}")
                    
                    # End conversation - don't wait for more messages
                    self.remove_user(user_id)
                    self.end_cleanup(user, start_time)
                    logger.info(f"[usage_gate] Conversation ended gracefully after final turn for user {user_id}")
                    break
  
            # If the user does not respond within the timeout, send a message and reset the chatbot
            except asyncio.TimeoutError:
                # user_input is None if timeout before first message
                if user_input and hasattr(user_input, 'channel'):
                    await user_input.channel.send(f"Hey {user.mention}, I’ll be around if you need me.")
                else:
                    await message_channel.send(f"Hey {user.mention}, I’ll be around if you need me.")
                self.remove_user(user_id)
                # Generate a summary of last conversation
                await self.end_summary(user_id,session_id,chat_history,guild_id)       
                # End the conversation
                self.end_cleanup(user,start_time)
                break

            # If there is an error, send a message and reset the chatbot
            except Exception as e:
                logger.error(
                    f"[conversation_error] {type(e).__name__}: {str(e)}",
                    extra={"user_id": user_id, "error": str(e)},
                    exc_info=True  # Include full traceback
                )
                # user_input may be None if error before first message
                if user_input and hasattr(user_input, 'channel'):
                    await user_input.channel.send(f"Oops, there was an error. Please try again.")
                else:
                    await message_channel.send(f"Oops, there was an error. Please try again.")
                # Remove User from Chatbot
                self.remove_user(user_id)
                # End the conversation
                self.end_cleanup(user,start_time)
                break
            
    @app_commands.command(name="chat", description="Chat with Abby")
    async def chat_command(self, interaction: discord.Interaction, question: Optional[str] = None):
        await interaction.response.defer(thinking=False)
        
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id) if interaction.guild else None
        
        # Check if already in conversation
        if user_id in self.active_instances:
            await interaction.followup.send("You're already chatting with me! Finish that conversation first.", ephemeral=True)
            return
        
        try:
            # Get guild settings for summon and chat modes
            settings = get_memory_settings(int(guild_id) if guild_id else 0)
            summon_mode = settings.get("conversation", {}).get("summon_mode", "both")
            default_chat_mode = settings.get("conversation", {}).get("default_chat_mode", "multi_turn")
            
            # Check if slash command summoning is enabled
            if summon_mode == "mention_only":
                await interaction.followup.send("Slash commands are not enabled for this server. Try mentioning me instead!", ephemeral=True)
                return
            
            # Create session
            session_id = str(uuid.uuid4())
            
            # Initialize user profile and chat history
            self.user_channel[user_id] = interaction.channel
            self.active_instances.append(user_id)
            
            # Create a wrapper object to provide message-like interface for interaction
            class InteractionWrapper:
                def __init__(self, interaction):
                    self.author = interaction.user
                    self.guild = interaction.guild
                    self.channel = interaction.channel
            
            wrapper = InteractionWrapper(interaction)
            chat_history, envelope = self.initalize_user(user_id, session_id, wrapper)
            
            # Determine behavior based on question and default_chat_mode
            if question:
                # User provided a question - ALWAYS one-shot
                class MockMessage:
                    def __init__(self, content, channel, author, guild):
                        self.content = content
                        self.channel = channel
                        self.author = author
                        self.guild = guild
                
                mock_message = MockMessage(question, interaction.channel, interaction.user, interaction.guild)
                
                async with interaction.channel.typing():  # type: ignore[union-attr]
                    response = await self.user_chat_mode(user_id, chat_history, mock_message, session_id=session_id)
                
                # Include the question in the response for reference
                formatted_response = f"**Question:** {question}\n\n{response}"
                await interaction.followup.send(formatted_response)
                self.remove_user(user_id)
                await self.end_summary(user_id, session_id, chat_history, guild_id)
                
            else:
                # No question provided - enter conversation mode based on default_chat_mode
                if default_chat_mode == "one_shot":
                    # One-shot mode: wait for single response
                    greeting = self.get_greeting(interaction.user)
                    await interaction.followup.send(greeting)
                    
                    # Wait for user response
                    try:
                        user_input = await self.bot.wait_for(
                            'message',
                            timeout=self.TIMEOUT_SECONDS,
                            check=lambda msg: msg.author == interaction.user and msg.channel == interaction.channel
                        )
                        
                        async with interaction.channel.typing():  # type: ignore[union-attr]
                            response = await self.user_chat_mode(user_id, chat_history, user_input, session_id=session_id)
                        
                        await self.send_message(interaction.channel, response)
                        self.remove_user(user_id)
                        await self.end_summary(user_id, session_id, chat_history, guild_id)
                        
                    except asyncio.TimeoutError:
                        await interaction.channel.send(f"Hey {interaction.user.mention}, I’ll be around if you need me.")  # type: ignore[union-attr]
                        self.remove_user(user_id)
                        await self.end_summary(user_id, session_id, chat_history, guild_id)
                
                else:
                    # Multi-turn mode: full conversation loop
                    greeting = self.get_greeting(interaction.user)
                    await interaction.followup.send(greeting)
                    
                    # Enter conversation loop
                    await self.handle_conversation(self.bot, interaction, user_id, session_id, chat_history)
        
        except Exception as e:
            logger.error(f"[/chat] Error: {e}", exc_info=True)
            await interaction.followup.send("An error occurred. Please try again later.", ephemeral=True)
            if user_id in self.active_instances:
                self.remove_user(user_id)

async def setup(bot):
    await bot.add_cog(Chatbot(bot))
    

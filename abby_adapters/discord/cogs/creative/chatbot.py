import json
import abby_core.llm.conversation as chat_openai  # Renamed from chat_openai for clarity
import asyncio
import random
import uuid
import time
import discord
import os
from datetime import datetime
from typing import Optional
from discord import app_commands
from discord.ext import commands

# Import personality configuration system
from abby_core.personality import get_personality_config

# Import unified MongoDB client for session management
# sys.path already configured in launch.py
from abby_core.database.mongodb import (
    create_session, append_session_message, close_session, 
    get_sessions_collection, upsert_user
)
# Memory envelope system for contextual intelligence (TDOS Memory v1.2)
import tdos_memory as memory
from tdos_memory import (
    get_memory_envelope, format_envelope_for_llm, 
    invalidate_cache, add_memorable_fact, update_relational_memory,
    extract_facts_from_summary, analyze_conversation_patterns,
    apply_decay, add_shared_narrative, get_shared_narratives
)
from tdos_memory.storage import MongoMemoryStore
from tdos_memory.service import MemoryService, create_memory_service
# Optional RAG integration
try:
    from abby_core.rag import query as rag_query
except ImportError:
    rag_query = None
from abby_core.observability.logging import logging
from abby_core.database.memory_settings import get_memory_settings

logger = logging.getLogger(__name__)

class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.TIMEOUT_SECONDS = 60.0
        self.exchange_count = {}  # Track exchanges per user session
        
        # Load personality configuration (summon/dismiss words, response patterns)
        self.personality = get_personality_config()
        
        # Connect to MongoDB for memory storage
        # TDOS Memory v1.2+ requires explicit storage_client (no auto-connect)
        from abby_core.database.mongodb import connect_to_mongodb
        mongo_client = connect_to_mongodb()
        
        # Initialize MemoryStore (MongoDB-backed, parameterized for Discord)
        self.memory_store = MongoMemoryStore(
            storage_client=mongo_client,
            profile_collection="discord_profiles",
            session_collection="chat_sessions",
            narrative_collection="shared_narratives"
        )
        
        # Create high-level MemoryService for adapter-agnostic access
        # All memory operations go through this service, not direct store calls
        self.memory_service = create_memory_service(
            store=self.memory_store,
            source_id="discord",
            logger=logger
        )
        
        self.user_channel = {}      # Track the channel of each user's chat
        self.active_instances = []  # Track active chatbot instances
        self.rag_enabled = os.getenv("RAG_CONTEXT_ENABLED", "false").lower() == "true"
        
        logger.info(
            "chatbot_initialized",
            extra={
                "adapter": "discord",
                "memory_backend": "mongodb",
                "summon_words_count": len(self.personality.summon_words),
                "dismiss_words_count": len(self.personality.dismiss_words),
                "memory_service_enabled": True
            }
        )

    def get_greeting(self, user):
        """Generate a random greeting using personality config."""
        name = user.mention
        
        # Get random emoji for greeting
        emoji_choices = ['abby_run', 'abby_jump', 'abby_idle']
        emoji_key = random.choice(emoji_choices)
        emoji = self.personality.get_emoji(emoji_key, "")
        
        # Use personality config to generate greeting
        return self.personality.get_random_greeting(name, emoji=emoji, include_action=True)
    
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

    def ensure_user_profile(self, user, guild):
        """Ensure user has a profile using MemoryService abstraction."""
        user_id = str(user.id)
        guild_id = str(guild.id) if guild else None
        
        # Build metadata from Discord user object
        metadata = {
            "username": user.name,
            "discriminator": user.discriminator if hasattr(user, 'discriminator') else None,
            "display_name": user.display_name if hasattr(user, 'display_name') else user.name,
            "avatar_url": str(user.avatar.url) if user.avatar else None,
            "last_seen": datetime.utcnow()
        }
        
        # Add guild-specific data if available
        if guild:
            member = guild.get_member(user.id)
            if member:
                metadata["nickname"] = member.nick
                metadata["guild_id"] = guild_id
                metadata["guild_name"] = guild.name
                if member.joined_at:
                    metadata["joined_at"] = member.joined_at
        
        # Use MemoryService abstraction (idempotent, adapter-agnostic)
        # This replaces direct MemoryStore/Mongo calls
        profile = self.memory_service.ensure_user_profile(
            user_id=user_id,
            guild_id=guild_id,
            metadata=metadata
        )
        
        if profile.get("created_at") == metadata.get("last_seen"):
            logger.info(
                "profile_created",
                extra={
                    "user_id": user_id,
                    "username": user.name,
                    "guild_id": guild_id
                }
            )
        else:
            logger.debug(
                "profile_metadata_updated",
                extra={"user_id": user_id, "username": user.name}
            )
        
        return user_id
    
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
    
    def end_summary(self,user_id,session_id,chat_history,guild_id=None):
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
                "exchange_count": len(actual_conversation),
                "excluded_memory_context": True
            }
        )
        
        # Don't generate summary if conversation too short
        if len(actual_conversation) == 0:
            logger.info(
                "summary_skipped_no_exchanges",
                extra={"user_id": user_id}
            )
            close_session(user_id, session_id, None)
            return
        
        recent_chat_history = actual_conversation[-5:] if len(actual_conversation) >= 5 else actual_conversation
        summary = chat_openai.summarize(recent_chat_history)
        
        # Close session with summary using unified client
        close_session(user_id, session_id, summary)
        
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
                    success = self.memory_service.add_fact(
                        user_id=user_id,
                        guild_id=guild_id,
                        fact_text=fact_data.get("text") or fact_data.get("fact"),  # Support both field names
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
                                "fact_preview": (fact_data.get('text') or fact_data.get('fact'))[:50],
                                "fact_type": "USER_FACT"
                            }
                        )
                    else:
                        logger.warning(
                            "fact_storage_failed",
                            extra={
                                "user_id": user_id,
                                "fact_preview": (fact_data.get('text') or fact_data.get('fact'))[:50]
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
                        extra={"user_id": user_id, "exchange_count": len(actual_conversation)}
                    )
                    
                    existing_profile = profile.get("creative_profile", {}) if profile else {}
                    
                    # Analyze patterns
                    pattern_result = analyze_conversation_patterns(
                        summary=summary,  # ← CHANGED: summary instead of chat_history
                        user_id=user_id,
                        existing_profile=existing_profile
                    )
                    
                    # Check if pattern updates are proposed
                    if pattern_result and pattern_result.get("proposed_updates"):
                        proposed = pattern_result["proposed_updates"]
                        confidence = pattern_result.get("confidence", 0)
                        requires_confirmation = pattern_result.get("requires_confirmation", False)
                        
                        if requires_confirmation:
                            # Low confidence — log for review, don't auto-apply
                            logger.warning(
                                "pattern_update_low_confidence",
                                extra={
                                    "user_id": user_id,
                                    "confidence": round(confidence, 2),
                                    "proposed_fields": list(proposed.keys())
                                }
                            )
                        else:
                            # High confidence — safe to apply automatically
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
    
    def user_chat_mode(self, user_id, chat_history, user_input):
        """Generate chatbot response with optional RAG context."""
        content = user_input.content

        # Optional RAG context injection
        if self.rag_enabled and rag_query:
            try:
                # Get guild_id from user input
                guild_id = None
                if hasattr(user_input, 'guild') and user_input.guild:
                    guild_id = str(user_input.guild.id)
                
                rag_result = rag_query(
                    text=content,
                    user_id=None,  # None = search guild-wide documents
                    guild_id=guild_id,
                    top_k=3
                )
                contexts = [item.get("text", "") for item in rag_result.get("results", [])]
                if contexts:
                    context_block = "\n".join([f"[RAG] {c}" for c in contexts])
                    content = f"Context:\n{context_block}\n\nUser: {content}"
            except Exception as exc:
                logger.warning(
                    "rag_context_fetch_failed",
                    extra={"error": str(exc)}
                )

        # Always use normal chat (code mode is deprecated)
        response = chat_openai.chat(content, user_id, chat_history=chat_history)
        return response

    def user_update_chat_history(self,user_id,session_id, chat_history,user_input,response):
        # Append both user message and assistant response to session (handles encryption)
        append_session_message(user_id, session_id, "user", user_input.content)
        append_session_message(user_id, session_id, "assistant", response)
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

    def initalize_user(self,user_id,session_id,message):
        # === MEMORY ENVELOPE SYSTEM (3-Layer Architecture) ===
        # Replaces legacy summary chain with structured, cached memory
        logger.info(
            "initializing_user_session",
            extra={"user_id": user_id, "session_id": session_id, "loading_memory": True}
        ) 
        
        # Ensure user has a profile with up-to-date Discord metadata
        # Uses MemoryService for adapter-agnostic access
        self.ensure_user_profile(message.author, message.guild)
        
        # Upsert user metadata using unified client
        upsert_user(user_id, message.author.name)
        
        guild_id = str(message.guild.id) if message.guild else None
        
        # Get or build memory envelope (cached 15min)
        # Uses MemoryService with source_id for multi-adapter isolation
        envelope = self.memory_service.get_memory_envelope(user_id, guild_id, force_refresh=False)
        
        # Format envelope for LLM context (includes identity + relational + recent context)
        memory_context = format_envelope_for_llm(envelope, max_facts=5)
        
        # Create new session using unified client
        create_session(user_id, session_id, message.channel.id, guild_id)
        
        # Initialize chat history with memory envelope context
        chat_history = []
        if memory_context:
            logger.info(
                "memory_envelope_loaded",
                extra={
                    "user_id": user_id,
                    "facts_count": len(envelope.get('relational', {}).get('memorable_facts', [])),
                    "has_recent_context": bool(envelope.get('recent_context'))
                }
            )
            chat_history.insert(0, {
                "input": "Memory Context (Identity + Relationships + Recent Session):",
                "response": memory_context,
            })
        else:
            logger.info(
                "memory_envelope_not_found",
                extra={"user_id": user_id}
            )
        
        return chat_history

    # Event Listeners
    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore the message if the author is a bot
        if message.author.bot:
            return

        if isinstance(message.channel, discord.DMChannel):
            return

        # If message starts with '!', ignore it
        if message.content.startswith('!'):
            return

        # Lightweight toggle for RAG context (global toggle)
        if message.content.lower().strip() == "rag on":
            self.rag_enabled = True
            await message.channel.send("RAG context enabled for chatbot.")
            return
        if message.content.lower().strip() == "rag off":
            self.rag_enabled = False
            await message.channel.send("RAG context disabled for chatbot.")
            return

        await self.handle_chatbot(self.bot, message)

    async def handle_conversation(self, client, message_or_interaction, user_id, session_id, chat_history, max_exchanges=None):
        user = message_or_interaction.user if hasattr(message_or_interaction, 'user') else message_or_interaction.author
        guild_id = str(message_or_interaction.guild.id) if message_or_interaction.guild else None
        
        # Get max exchanges from guild settings if not provided
        if max_exchanges is None:
            settings = get_memory_settings(int(guild_id) if guild_id else 0)
            max_exchanges = settings.get("max_conversation_exchanges", 10)
        
        logger.info(
            "handling_conversation",
            extra={"user_id": str(user.id), "username": user.name, "max_exchanges": max_exchanges}
        ) 
        start_time = time.perf_counter()
        self.exchange_count[user_id] = 0  # Initialize exchange counter
        
        # Determine message channel
        if hasattr(message_or_interaction, 'channel'):
            message_channel = message_or_interaction.channel
        else:
            message_channel = message_or_interaction.channel

        # Start the conversation loop
        while True:
            try:
                # Wait for user input
                user_input = await client.wait_for(
                    "message", 
                    timeout=self.TIMEOUT_SECONDS, 
                    check=lambda m: m.author == user and not m.content.startswith('!') and m.channel == self.user_channel[user_id]
                )

                # Track exchange count
                self.exchange_count[user_id] += 1
                
                # Check if exchange ceiling reached
                if self.exchange_count[user_id] >= max_exchanges:
                    emoji = self.personality.get_emoji('abby_run', '')
                    await user_input.channel.send(f"I've enjoyed our chat! Feel free to ask me something else later 😊 {emoji}")
                    self.remove_user(user_id)
                    # Generate a summary of last conversation
                    self.end_summary(user_id,session_id,chat_history,guild_id)
                    # End the conversation
                    self.end_cleanup(user,start_time)
                    if user_id in self.exchange_count:
                        del self.exchange_count[user_id]
                    break
                
                # If the user says the dismiss word, send a message and reset the chatbot
                if self.personality.check_dismiss_trigger(user_input.content):
                    emoji = self.personality.get_emoji('abby_run', '')
                    await user_input.channel.send(f"So happy to help {user.mention}! *happily hops off*! {emoji}")
                    self.remove_user(user_id)
                    # Generate a summary of last conversation
                    guild_id = str(user_input.guild.id) if user_input.guild else None
                    self.end_summary(user_id,session_id,chat_history,guild_id)
                    # End the conversation
                    self.end_cleanup(user,start_time)
                    if user_id in self.exchange_count:
                        del self.exchange_count[user_id]
                    break

                async with user_input.channel.typing():
                    # Check user's chat mode and respond accordingly
                    response = self.user_chat_mode(user_id, chat_history, user_input)
                await self.send_message(user_input.channel, response)
                
                # Update the chat history after each response
                self.user_update_chat_history(user_id,session_id, chat_history,user_input,response)
  
            # If the user does not respond within the timeout, send a message and reset the chatbot
            except asyncio.TimeoutError:
                emoji = self.personality.get_emoji('abby_jump', '')
                await user_input.channel.send(f"Hey {user.mention}, I've gotta hop! {emoji}")
                self.remove_user(user_id)
                # Generate a summary of last conversation
                self.end_summary(user_id,session_id,chat_history,guild_id)       
                # End the conversation
                self.end_cleanup(user,start_time)
                if user_id in self.exchange_count:
                    del self.exchange_count[user_id]
                break

            # If there is an error, send a message and reset the chatbot
            except Exception as e:
                logger.warning(
                    "conversation_error",
                    extra={"user_id": user_id, "error": str(e)}
                )
                await user_input.channel.send(f"Oops, there was an error. Please try again.")
                # Remove User from Chatbot
                self.remove_user(user_id)
                # End the conversation
                self.end_cleanup(user,start_time)
                if user_id in self.exchange_count:
                    del self.exchange_count[user_id]
                break

    async def handle_chatbot(self, client, message):
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
        summon_mode = settings.get("summon_mode", "both")
        default_chat_mode = settings.get("default_chat_mode", "multi_turn")
        max_exchanges = settings.get("max_conversation_exchanges", 10)
        
        # If slash-only mode, skip mention-based summoning
        if summon_mode == "slash_only":
            return
        
        # Check for summon words using personality config
        if self.personality.check_summon_trigger(message.content):
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

            # Send a "processing" message in bunny talk
            emoji_choices = ['abby_run', 'abby_jump', 'abby_idle']
            emoji_key = random.choice(emoji_choices)
            emoji = self.personality.get_emoji(emoji_key, "")
            processing_text = self.personality.get_random_processing_message(emoji=emoji)
            processing_message = await message.channel.send(processing_text)
            
            # Create new session ID for the user
            session_id = str(uuid.uuid4())  
            
            # Ignore the message if the user is in a different channel
            if message.channel != self.user_channel[user_id]:
                logger.info(
                    "user_in_different_channel",
                    extra={"user_id": user_id, "current_channel": str(message.channel.id)}
                )
                return 
            
            # Initialize the user's chat history
            chat_history = self.initalize_user(user_id, session_id, message)

            # Extract user input after summon word (if any)
            # Find which summon word was used and strip it
            message_lower = message.content.lower()
            user_input_text = message.content
            for summon_word in self.personality.summon_words:
                if summon_word in message_lower:
                    # Remove the summon word from the message
                    user_input_text = message.content[len(summon_word):].strip()
                    break
            
            # Add the user to active instances    
            self.active_instances.append(user_id)

            if user_input_text:
                # If there is an input after the summon word, process it as usual
                # Create a mock message object with the stripped content
                class MockMessage:
                    def __init__(self, original_message, new_content):
                        self.content = new_content
                        self.author = original_message.author
                        self.channel = original_message.channel
                        self.guild = original_message.guild
                
                mock_message = MockMessage(message, user_input_text)
                response = self.user_chat_mode(user_id, chat_history, mock_message)

                # Delete the "processing" message and send the actual response
                await processing_message.delete()
                await self.send_message(message.channel, response)

                # Update the chat history after each response
                self.user_update_chat_history(user_id, session_id, chat_history, mock_message, response)
            else:
                # If there is no input after the summon word, update the "processing" message with a greeting
                greeting = self.get_greeting(message.author)
                wave_emoji = self.personality.get_emoji('wave', '')
                await processing_message.edit(content=f"{greeting} How can I assist you today? {wave_emoji}")
            
            # Log Chatbot Startup Time
            end_time = time.perf_counter()
            elapsed_time = end_time - start_time
            logger.info(
                "chatbot_startup_complete",
                extra={"elapsed_seconds": round(elapsed_time, 4)}
            )
            
            # Continue the listener loop
            await self.handle_conversation(client, message, user_id, session_id, chat_history)

    @app_commands.command(name="chat", description="Chat with Abby")
    async def chat_command(self, interaction: discord.Interaction, question: Optional[str] = None):
        """
        Slash command to start a chat with Abby.
        
        Args:
            interaction: Discord interaction
            question: Optional question to ask (if not provided, enters conversation mode)
        """
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
            summon_mode = settings.get("summon_mode", "both")
            default_chat_mode = settings.get("default_chat_mode", "multi_turn")
            max_exchanges = settings.get("max_conversation_exchanges", 10)
            
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
            chat_history = self.initalize_user(user_id, session_id, wrapper)
            
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
                
                async with interaction.channel.typing():
                    response = self.user_chat_mode(user_id, chat_history, mock_message)
                
                # Include the question in the response for reference
                formatted_response = f"**Question:** {question}\n\n{response}"
                await interaction.followup.send(formatted_response)
                self.remove_user(user_id)
                self.end_summary(user_id, session_id, chat_history, guild_id)
                
            else:
                # No question provided - enter conversation mode based on default_chat_mode
                if default_chat_mode == "one_shot":
                    # One-shot mode: wait for single response
                    greeting = self.get_greeting(interaction.user)
                    wave_emoji = self.personality.get_emoji('wave', '')
                    await interaction.followup.send(f"{greeting} How can I assist you today? {wave_emoji}")
                    
                    # Wait for user response
                    try:
                        user_input = await self.bot.wait_for(
                            'message',
                            timeout=self.TIMEOUT_SECONDS,
                            check=lambda msg: msg.author == interaction.user and msg.channel == interaction.channel
                        )
                        
                        async with interaction.channel.typing():
                            response = self.user_chat_mode(user_id, chat_history, user_input)
                        
                        await self.send_message(interaction.channel, response)
                        self.remove_user(user_id)
                        self.end_summary(user_id, session_id, chat_history, guild_id)
                        
                    except asyncio.TimeoutError:
                        emoji = self.personality.get_emoji('abby_jump', '')
                        await interaction.channel.send(f"Hey {interaction.user.mention}, I've gotta hop! {emoji}")
                        self.remove_user(user_id)
                        self.end_summary(user_id, session_id, chat_history, guild_id)
                
                else:
                    # Multi-turn mode: full conversation loop
                    greeting = self.get_greeting(interaction.user)
                    wave_emoji = self.personality.get_emoji('wave', '')
                    await interaction.followup.send(f"{greeting} How can I assist you today? {wave_emoji}")
                    
                    # Enter conversation loop
                    await self.handle_conversation(self.bot, interaction, user_id, session_id, chat_history, max_exchanges)
                # No question provided
                if default_chat_mode == "one_shot":
                    # One-shot mode: send greeting and close
                    greeting = self.get_greeting(interaction.user)
                    wave_emoji = self.personality.get_emoji('wave', '')
                    await interaction.followup.send(f"{greeting} How can I assist you today? {wave_emoji}")
                    self.remove_user(user_id)
                    self.end_summary(user_id, session_id, chat_history, guild_id)
                else:
                    # Multi-turn mode: send greeting and enter conversation loop
                    greeting = self.get_greeting(interaction.user)
                    wave_emoji = self.personality.get_emoji('wave', '')
                    await interaction.followup.send(f"{greeting} How can I assist you today? {wave_emoji}")
                    
                    # Enter conversation loop
                    await self.handle_conversation(self.bot, interaction, user_id, session_id, chat_history, max_exchanges)
        
        except Exception as e:
            logger.error(f"[/chat] Error: {e}", exc_info=True)
            await interaction.followup.send("An error occurred. Please try again later.", ephemeral=True)
            if user_id in self.active_instances:
                self.remove_user(user_id)

async def setup(bot):
    await bot.add_cog(Chatbot(bot))
    

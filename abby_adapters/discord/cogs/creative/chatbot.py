import json
import abby_core.llm.conversation as chat_openai  # Renamed from chat_openai for clarity
import asyncio
import random
import uuid
import time
import discord
import os
from datetime import datetime
from discord.ext import commands

# Import personality configuration system
from abby_core.personality import get_personality_config

# Import unified MongoDB client for session management
# sys.path already configured in launch.py
from abby_core.database.mongodb import (
    create_session, append_session_message, close_session, 
    get_sessions_collection, upsert_user
)
# Memory envelope system for contextual intelligence (TDOS Memory v1.0)
import tdos_memory as memory
from tdos_memory import (
    get_memory_envelope, format_envelope_for_llm, 
    invalidate_cache, add_memorable_fact, update_relational_memory,
    extract_facts_from_summary, analyze_conversation_patterns,
    apply_decay, add_shared_narrative, get_shared_narratives
)
# Optional RAG integration
try:
    from abby_core.rag import query as rag_query
except ImportError:
    rag_query = None
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)

def apply_pattern_updates(user_id: str, updates: dict) -> None:
    """Apply proposed pattern updates to user profile."""
    from abby_core.database.mongodb import connect_to_mongodb
    from typing import Any, Dict
    
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    
    update_doc = {"$set": {}}
    
    # Map updates to creative_profile fields
    if "domains" in updates:
        update_doc["$set"]["creative_profile.domains"] = updates["domains"]
    if "preferences" in updates:
        update_doc["$set"]["creative_profile.preferences"] = updates["preferences"]
    if "learning_level" in updates:
        update_doc["$set"]["creative_profile.learning_level"] = updates["learning_level"]
    
    if len(update_doc["$set"]) > 0:
        from pymongo.write_concern import WriteConcern
        profiles_collection = db["discord_profiles"].with_options(
            write_concern=WriteConcern(w="majority", j=True)
        )
        profiles_collection.update_one(
            {"user_id": str(user_id)},
            update_doc,
            upsert=True
        )

class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.TIMEOUT_SECONDS = 60.0
        
        # Load personality configuration (summon/dismiss words, response patterns)
        self.personality = get_personality_config()
        
        self.user_channel = {}      # Track the channel of each user's chat
        self.active_instances = []  # Track active chatbot instances
        self.rag_enabled = os.getenv("RAG_CONTEXT_ENABLED", "false").lower() == "true"
        
        logger.info(f"[💭] Chatbot initialized with unified database structure")
        logger.info(f"[🐰] Loaded {len(self.personality.summon_words)} summon words, {len(self.personality.dismiss_words)} dismiss words")

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
        """Ensure user has a profile in discord_profiles, create/update if needed."""
        from abby_core.database.mongodb import connect_to_mongodb
        from datetime import datetime
        
        client = connect_to_mongodb()
        db = client["Abby_Database"]
        user_id = str(user.id)
        
        # Build metadata from Discord user object
        profile_data = {
            "user_id": user_id,
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
                profile_data["nickname"] = member.nick
                profile_data["guild_id"] = str(guild.id)
                profile_data["guild_name"] = guild.name
                if member.joined_at:
                    profile_data["joined_at"] = member.joined_at
        
        # Upsert profile with metadata, preserve creative_profile if exists
        result = db["discord_profiles"].update_one(
            {"user_id": user_id},
            {
                "$set": profile_data,
                "$setOnInsert": {
                    "created_at": datetime.utcnow(),
                    "creative_profile": {
                        "domains": [],
                        "preferences": {},
                        "memorable_facts": [],
                        "confidence_score": 0.0
                    }
                }
            },
            upsert=True
        )
        
        if result.upserted_id:
            logger.info(f"[📝] Created new profile for {user.name} ({user_id})")
        else:
            logger.debug(f"[📝] Updated profile metadata for {user.name}")
        
        return user_id
    
    def end_cleanup(self,user,start_time):
        logger.info(f"[💭] Ending Conversation with {user.name}")
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.info(f"[⏱️] (Conversation) Elapsed Time: {elapsed_time:0.4f} seconds")
    
    def end_summary(self,user_id,session_id,chat_history,guild_id=None):
        # === MEMORY ENVELOPE: Extract facts and update creative_profile ===
        logger.info(f"[💭] Generating summary for user {user_id}, session {session_id}")
        
        # Filter out memory context (first item with "Memory Context" as input)
        # Only summarize actual conversation exchanges from this session
        actual_conversation = [
            item for item in chat_history 
            if "Memory Context" not in item.get("input", "")
        ]
        
        logger.info(f"[💭] Summarizing {len(actual_conversation)} conversation exchanges (excluded memory context)")
        
        # Don't generate summary if conversation too short
        if len(actual_conversation) == 0:
            logger.info(f"[💭] No actual conversation to summarize, skipping extraction")
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
        invalidate_cache(user_id, guild_id)
        logger.info(f"[🧠] Memory cache invalidated for user {user_id} - next conversation will rebuild envelope")
    
    async def _extract_and_update_memory(self, user_id, guild_id, summary, actual_conversation):
        """
        Background task: Extract facts and update memory without blocking Discord event loop.
        Runs asynchronously so heartbeat/event processing continues normally.
        """
        try:
            await asyncio.sleep(0.1)  # Yield to event loop first
            
            # === LLM-BASED MEMORY EXTRACTION ===
            profile = None  # Initialize to avoid UnboundLocalError
            
            try:
                # Get database connection
                from abby_core.database.mongodb import connect_to_mongodb
                client = connect_to_mongodb()
                db = client["Abby_Database"]
                
                # Get or ensure profile exists
                profile = db["discord_profiles"].find_one({"user_id": str(user_id)})
                if not profile:
                    logger.warning(f"[📝] No profile found for {user_id} during extraction, profile should have been created")
                    # Create minimal profile
                    db["discord_profiles"].insert_one({
                        "user_id": str(user_id),
                        "username": f"User_{user_id[:8]}",
                        "created_at": datetime.utcnow(),
                        "creative_profile": {
                            "domains": [],
                            "preferences": {},
                            "memorable_facts": [],
                            "confidence_score": 0.0
                        }
                    })
                    profile = db["discord_profiles"].find_one({"user_id": str(user_id)})
                
                # 1. Extract memorable facts from summary (validated & typed)
                logger.info(f"[🧠] Extracting memorable facts from summary...")
                extracted_facts = extract_facts_from_summary(summary, user_id)  # ← CHANGED: No conversation_exchanges param
                
                # Filter for USER_FACT type (only these go to profile)
                user_facts = [f for f in extracted_facts if f.get("type") == "USER_FACT"]
                
                # Add each fact to user's memory
                facts_stored_count = 0
                for fact_data in user_facts:
                    success = add_memorable_fact(
                        user_id=user_id,
                        guild_id=guild_id,
                        fact=fact_data.get("text") or fact_data.get("fact"),  # Support both field names
                        source=fact_data.get("source", "llm_extraction"),
                        confidence=fact_data["confidence"]
                    )
                    if success:
                        facts_stored_count += 1
                        logger.info(f"[🧠] Stored validated USER_FACT (conf: {fact_data['confidence']:.2f}): {(fact_data.get('text') or fact_data.get('fact'))[:50]}...")
                    else:
                        logger.warning(f"[⚠️] Failed to store USER_FACT: {(fact_data.get('text') or fact_data.get('fact'))[:50]}...")
                
                if facts_stored_count > 0:
                    logger.info(f"[🧠] Successfully stored {facts_stored_count}/{len(user_facts)} USER_FACT memories")
                
                # 2. Analyze conversation patterns for domains/preferences
                if len(actual_conversation) >= 2:
                    logger.info(f"[🧠] Analyzing conversation patterns...")
                    
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
                            logger.warning(f"[🧠] Low-confidence pattern update (conf: {confidence:.2f})")
                            logger.warning(f"[🧠] Proposed updates: {proposed}")
                            logger.warning(f"[🧠] (User interactions can reinforce these patterns)")
                        else:
                            # High confidence — safe to apply automatically
                            apply_pattern_updates(user_id, proposed)
                            logger.info(f"[🧠] Applied pattern updates (conf: {confidence:.2f}): {list(proposed.keys())}")
                    else:
                        logger.debug("[🧠] No pattern updates proposed")
                
                # 3. Apply confidence decay to existing facts
                # CRITICAL: Re-read profile to include facts just added in step 1
                profile_for_decay = db["discord_profiles"].find_one(
                    {"user_id": str(user_id)},
                    {"creative_profile.memorable_facts": 1}
                )
                if profile_for_decay and "creative_profile" in profile_for_decay:
                    facts = profile_for_decay["creative_profile"].get("memorable_facts", [])
                    if facts:
                        logger.info(f"[⏱️] Applying confidence decay to {len(facts)} existing facts...")
                        updated_facts = apply_decay(facts)
                        
                        # Update facts in database with write concern
                        from pymongo.write_concern import WriteConcern
                        profiles_collection = db["discord_profiles"].with_options(
                            write_concern=WriteConcern(w="majority", j=True)
                        )
                        profiles_collection.update_one(
                            {"user_id": str(user_id)},
                            {"$set": {"creative_profile.memorable_facts": updated_facts}}
                        )
                        
                        pruned_count = len(facts) - len(updated_facts)
                        if pruned_count > 0:
                            logger.info(f"[🗑️] Pruned {pruned_count} low-confidence facts")
            
            except Exception as e:
                logger.error(f"[❌] Memory extraction failed: {e}", exc_info=True)
                # Don't fail if extraction fails
        
        except Exception as e:
            logger.error(f"[❌] Background memory extraction task failed: {e}", exc_info=True)
    
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
                logger.warning(f"[RAG] Context fetch failed: {exc}")

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
        logger.info(f"[💭] Updated chat history for user {user_id}, session {session_id}")

    def initalize_user(self,user_id,session_id,message):
        # === MEMORY ENVELOPE SYSTEM (3-Layer Architecture) ===
        # Replaces legacy summary chain with structured, cached memory
        logger.info(f"[💭] Initializing user {user_id}, session {session_id} - Loading memory envelope!") 
        
        # Ensure user has a profile with up-to-date Discord metadata
        self.ensure_user_profile(message.author, message.guild)
        
        # Upsert user metadata using unified client
        upsert_user(user_id, message.author.name)
        
        guild_id = str(message.guild.id) if message.guild else None
        
        # Get or build memory envelope (cached 15min)
        envelope = get_memory_envelope(user_id, guild_id)
        
        # Format envelope for LLM context (includes identity + relational + recent context)
        memory_context = format_envelope_for_llm(envelope, max_facts=5)
        
        # Create new session using unified client
        create_session(user_id, session_id, message.channel.id, guild_id)
        
        # Initialize chat history with memory envelope context
        chat_history = []
        if memory_context:
            logger.info(f"[🧠] Memory envelope loaded: {len(envelope.get('relational', {}).get('memorable_facts', []))} facts, recent context: {bool(envelope.get('recent_context'))}")
            chat_history.insert(0, {
                "input": "Memory Context (Identity + Relationships + Recent Session):",
                "response": memory_context,
            })
        else:
            logger.info(f"[🧠] No existing memory for user {user_id} - starting fresh")
        
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

    async def handle_conversation(self, client, message, user_id, session_id, chat_history):
        user = message.author
        logger.info(f"[💭] Handling Conversation with {user.name}") 
        start_time = time.perf_counter()

        # Start the conversation loop
        while True:
            try:
                # Wait for user input
                user_input = await client.wait_for(
                    "message", 
                    timeout=self.TIMEOUT_SECONDS, 
                    check=lambda m: m.author == user and not m.content.startswith('!') and m.channel == self.user_channel[user_id]
                )

                # If the user says the dismiss word, send a message and reset the chatbot
                if self.personality.check_dismiss_trigger(user_input.content):
                    emoji = self.personality.get_emoji('abby_run', '')
                    await user_input.channel.send(f"So happy to help {user.mention}! *happily hops off*! {emoji}")
                    self.remove_user(user_id)
                    # Generate a summary of last conversation
                    guild_id = str(message.guild.id) if message.guild else None
                    self.end_summary(user_id,session_id,chat_history,guild_id)
                    # End the conversation
                    self.end_cleanup(user,start_time)
                    break

                async with message.channel.typing():
                    # Check user's chat mode and respond accordingly
                    response = self.user_chat_mode(user_id, chat_history, user_input)
                await self.send_message(user_input.channel, response)
                
                # Update the chat history after each response
                self.user_update_chat_history(user_id,session_id, chat_history,user_input,response)
  
            # If the user does not respond within the timeout, send a message and reset the chatbot
            except asyncio.TimeoutError:
                emoji = self.personality.get_emoji('abby_jump', '')
                await message.channel.send(f"Hey {user.mention}, I've gotta hop! {emoji}")
                self.remove_user(user_id)
                # Generate a summary of last conversation
                guild_id = str(message.guild.id) if message.guild else None
                self.end_summary(user_id,session_id,chat_history,guild_id)       
                # End the conversation
                self.end_cleanup(user,start_time)
                break

            # If there is an error, send a message and reset the chatbot
            except Exception as e:
                logger.warning(f"[❌] There was an error (handle_conversation) {str(e)}")
                await message.channel.send(f"Oops, there was an error. Please try again.")
                # Remove User from Chatbot
                self.remove_user(user_id)
                # End the conversation
                self.end_cleanup(user,start_time)
                break

    async def handle_chatbot(self, client, message):
        # logger.info("[💭] Handling Chatbot")
        start_time = time.perf_counter()
        user_id = str(message.author.id)

        # If the bot is already active for the user, return
        if user_id in self.active_instances:
            logger.info(f"[💭] Chatbot is already active for {user_id}")
            return
        
        # Check for summon words using personality config
        if self.personality.check_summon_trigger(message.content):
            logger.info(f"[💭] Summoning Chatbot for {user_id}")        
            # Set the user's channel if not already set
            if user_id not in self.user_channel:
                logger.info(f"[💭] Setting user channel for {user_id}")
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
                logger.info(f"[💭] User {user_id} is in a different channel")
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
            logger.info(f"[⏱️] (Startup) Elapsed Time: {elapsed_time:0.4f} seconds")
            
            # Continue the listener loop
            await self.handle_conversation(client, message, user_id, session_id, chat_history)

async def setup(bot):
    await bot.add_cog(Chatbot(bot))
    

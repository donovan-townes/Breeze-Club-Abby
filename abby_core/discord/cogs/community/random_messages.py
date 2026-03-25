"""
Random Messages Cog - Periodic guild-aware message generation.

Posts inspirational/entertaining messages every 3 hours.
Uses PersonalityManager + ConversationContext with guild context for coherent messaging.
Demonstrates the unified LLM architecture pattern.
"""

import os
import discord
from discord import app_commands
from discord.ext import tasks, commands
import random
from typing import Optional

from abby_core.database.collections.guild_configuration import (
    get_memory_settings,
    set_guild_config,
)
from abby_core.personality.manager import get_personality_manager
from abby_core.services.conversation_service import get_conversation_service
from abby_core.llm.context_factory import build_conversation_context
from abby_core.discord.config import get_discord_config
from abby_core.observability.logging import logging
from datetime import datetime

logger = logging.getLogger(__name__)
PROMPT_VERBOSE = os.getenv("PROMPT_VERBOSE", "0") in {"1", "true", "True"}


class RandomMessages(commands.Cog):
    """Periodic random inspirational messages."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.personality_manager = get_personality_manager()
        self.config = get_discord_config()
        
        # Message categories and prompts
        self.message_types = {
            "inspiration": "Generate an inspiring message about creativity, growth, or pursuing dreams.",
            "encouragement": "Generate an encouraging message to boost morale and positivity.",
            "creativity": "Generate a message celebrating creativity, art, music, or self-expression.",
            "community": "Generate a warm welcoming message that brings people together.",
            "fun_fact": "Share a fun or interesting fact in an engaging conversational way.",
            "challenge": "Suggest a fun creative challenge the community could try together.",
        }
        
        logger.debug("[Random Messages] Cog loaded")
    
    async def generate_random_message(
        self, 
        guild_name: str, 
        message_type: Optional[str] = None
    ) -> str:
        """
        Generate a random message using LLM with guild context.
        
        Args:
            guild_name: Name of the guild/server for context
            message_type: Type of message to generate (random if None)
        
        Returns:
            Generated message text
        """
        try:
            # Pick random message type if not specified
            if message_type is None:
                message_type = random.choice(list(self.message_types.keys()))
            
            prompt_description = self.message_types.get(
                message_type, 
                self.message_types["inspiration"]
            )
            
            # Build conversation context with persona injection
            context = build_conversation_context(
                user_id="random_messages_generator",
                chat_history=[],
                guild_name=guild_name,
            )
            
            # Craft the message generation prompt with guild context
            prompt = f"""Task: {prompt_description}

Guidelines:
- Keep it concise (1-3 sentences, max 250 characters)
- Warm, genuine, and friendly tone
- Relevant to a creative community
- Use 1-2 emojis maximum
- No markdown formatting
- Sound natural and conversational
- Do not mention Abby by name

Generate one message:"""

            if PROMPT_VERBOSE:
                logger.info(
                    "[Random Messages] Prompt (user message to LLM):\n%s",
                    prompt,
                )
            
            # Generate using async respond
            conversation_service = get_conversation_service()
            response, error = await conversation_service.generate_response(prompt, context, max_retries=2)
            if error or response is None:
                logger.warning(f"[Random Messages] Generation failed: {error or 'no response'}")
                return "✨ Stay creative and keep shining!"
            message_text = response.strip()
            
            # Remove any markdown formatting
            message_text = message_text.replace("**", "").replace("*", "").replace("__", "")
            
            # Limit length
            if len(message_text) > 300:
                message_text = message_text[:297] + "..."
            
            logger.info(f"[Random Messages] Generated {message_type}: {message_text[:50]}...")
            return message_text
            
        except Exception as e:
            logger.error(f"[Random Messages] Error generating message: {e}", exc_info=True)
            # Fallback messages
            fallbacks = [
                "Keep creating amazing things! Your efforts matter.",
                "Every masterpiece started as an idea. What will you create today?",
                "Your unique voice is valuable to this community.",
                "Growth happens outside your comfort zone. Try something new!",
                "Take a moment to celebrate how far you have come.",
            ]
            return random.choice(fallbacks)
    
    async def send_random_message_to_channel(
        self,
        guild_id: int,
        channel_id: int,
        guild_name: str,
        check_dedup: bool = False,
    ) -> bool:
        """
        Generate and send random message to specified channel.
        
        Args:
            channel_id: Discord channel ID
            guild_name: Name of the guild for context
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                logger.warning(f"[Random Messages] Channel {channel_id} not found")
                return False
            
            # Ensure it is a text channel
            if not isinstance(channel, discord.TextChannel):
                logger.warning(f"[Random Messages] Channel {channel_id} is not a text channel")
                return False
            
            # Check permissions
            permissions = channel.permissions_for(channel.guild.me)
            if not permissions.send_messages:
                logger.warning(f"[Random Messages] No permission to send in {channel_id}")
                return False
            
            # Generate random message (optionally avoid repeats)
            message_text = await self.generate_random_message(guild_name)
            message_hash = None
            if check_dedup:
                try:
                    settings = get_memory_settings(guild_id)
                    last_hash = (
                        settings
                        .get("scheduling", {})
                        .get("jobs", {})
                        .get("community", {})
                        .get("random_messages", {})
                        .get("last_message_hash")
                    )
                    attempts = 0
                    while attempts < 2:
                        message_hash = str(hash(message_text))
                        if message_hash != last_hash:
                            break
                        message_text = await self.generate_random_message(guild_name)
                        attempts += 1
                except Exception as e:
                    logger.debug(f"[Random Messages] Dedup check failed: {e}")
            
            # Send message
            await channel.send(message_text)
            if check_dedup and message_hash is not None:
                set_guild_config(
                    guild_id,
                    {
                        "scheduling": {
                            "jobs": {
                                "community": {
                                    "random_messages": {
                                        "last_message_hash": message_hash,
                                        "last_sent_at": datetime.utcnow().isoformat(),
                                    }
                                }
                            }
                        }
                    },
                    audit_user_id="scheduler",
                )
            logger.info(f"[Random Messages] Sent to {guild_name}")
            return True
            
        except discord.Forbidden:
            logger.error(f"[Random Messages] Forbidden to send in {channel_id}")
            return False
        except Exception as e:
            logger.error(f"[Random Messages] Error sending message: {e}", exc_info=True)
            return False
    
    @app_commands.command(
        name="random_message", 
        description="Generate a random inspirational message"
    )
    @app_commands.describe(
        message_type="Select message type",
        send_to_channel="Send to breeze_lounge (admin only)"
    )
    @app_commands.choices(
        message_type=[
            app_commands.Choice(name="Inspiration", value="inspiration"),
            app_commands.Choice(name="Encouragement", value="encouragement"),
            app_commands.Choice(name="Creativity", value="creativity"),
            app_commands.Choice(name="Community", value="community"),
            app_commands.Choice(name="Fun Fact", value="fun_fact"),
            app_commands.Choice(name="Challenge", value="challenge"),
        ]
    )
    async def random_message_command(
        self,
        interaction: discord.Interaction,
        message_type: app_commands.Choice[str],
        send_to_channel: bool = False
    ):
        """Manually trigger random message generation."""
        await interaction.response.defer(ephemeral=not send_to_channel)
        
        try:
            guild_name = interaction.guild.name if interaction.guild else "our community"
            selected_type = message_type.value
            
            if send_to_channel:
                # Check admin permissions
                if not isinstance(interaction.user, discord.Member) or \
                   not interaction.user.guild_permissions.administrator:
                    await interaction.followup.send(
                        "Only administrators can send to channel.",
                        ephemeral=True
                    )
                    return

                if not interaction.guild:
                    await interaction.followup.send(
                        "This command must be used in a server.",
                        ephemeral=True
                    )
                    return
                
                settings = get_memory_settings(interaction.guild.id) if interaction.guild else {}
                channel_id = settings.get("channels", {}).get("random_messages", {}).get("id") or self.config.channels.breeze_lounge

                if not channel_id:
                    await interaction.followup.send(
                        "No channel configured for random messages.",
                        ephemeral=True
                    )
                    return
                
                # Handle MongoDB NumberLong format
                try:
                    if isinstance(channel_id, dict):
                        channel_id = int(channel_id.get("$numberLong", 0))
                    else:
                        channel_id = int(channel_id)
                except (TypeError, ValueError):
                    await interaction.followup.send(
                        "Invalid channel ID format.",
                        ephemeral=True
                    )
                    return
                
                success = await self.send_random_message_to_channel(
                    interaction.guild.id,
                    channel_id,
                    guild_name,
                    check_dedup=False,
                )
                
                if success:
                    await interaction.followup.send(
                        f"Random message sent to <#{channel_id}>",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "Failed to send message. Check logs.",
                        ephemeral=True
                    )
            else:
                # Generate and show privately
                message_text = await self.generate_random_message(
                    guild_name, 
                    selected_type
                )
                
                await interaction.followup.send(
                    f"**Random Message Preview:**\n{message_text}",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"[Random Messages] Command error: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while generating the message.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Load the Random Messages cog."""
    await bot.add_cog(RandomMessages(bot))

"""
Message of the Day (MOTD) Cog

Generates and posts daily motivational messages using the new async architecture.
Uses PersonalityManager and ConversationContext for proper persona injection.
Supports per-guild timezone configuration with dynamic scheduling.

Architecture:
- Guild timezone stored in guild_config.timezone (e.g., "US/Central", "Europe/London")
- MOTD time stored as local time in guild_config.motd_time (e.g., "08:00")
- Background task runs every 5 minutes, checking if any guild needs MOTD
- Tracks last_sent_date to prevent duplicate sends
"""

import discord
from discord import app_commands
from discord.ext import tasks, commands
from datetime import datetime, timezone
from typing import Optional
import pytz

from abby_core.personality.manager import get_personality_manager
from abby_core.services.conversation_service import get_conversation_service
from abby_core.llm.context_factory import build_conversation_context
from abby_core.discord.config import get_discord_config
from abby_core.database.collections.guild_configuration import (
    get_guild_config,
    set_guild_config,
    get_memory_settings,
    set_memory_settings,
)
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


class MOTD(commands.Cog):
    """Daily Message of the Day generator."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.personality_manager = get_personality_manager()
        self.config = get_discord_config()
        logger.debug("[📅] MOTD cog loaded")

    async def cog_unload(self):
        """Clean up when cog is unloaded."""
        pass
    
    async def generate_motd(self, guild_name: str = "our community") -> str:
        """
        Generate a Message of the Day using the new async architecture.
        
        Args:
            guild_name: Name of the guild/server for context
        
        Returns:
            Generated MOTD text
        """
        try:
            # Build conversation context with persona injection
            # Use a system user ID for MOTD generation
            system_user_id = "motd_generator"
            
            context = build_conversation_context(
                user_id=system_user_id,
                chat_history=[],
                guild_name=guild_name,
            )
            
            # Craft the MOTD generation prompt
            prompt = f"""Generate an inspiring, uplifting Message of the Day for {guild_name}.

Guidelines:
- Keep it concise (150-200 characters)
- Warm, motivational tone
- Encourage creativity and positivity
- Suitable for Discord community
- Use 1-2 emojis maximum
- No markdown formatting

Examples:
"Good morning! Today is a canvas waiting for your creativity. What will you create? 🎨"
"Remember: Every expert was once a beginner. Keep learning, keep growing! 🌱"
"Your unique perspective matters. Share your ideas and inspire others today! ✨"

Generate one inspirational message now:"""
            
            # Generate using async respond
            conversation_service = get_conversation_service()
            response, error = await conversation_service.generate_response(prompt, context, max_retries=2)
            if error or response is None:
                logger.warning(f"[MOTD] Generation failed: {error or 'no response'}")
                return "🌟 Make today amazing!"
            
            # Clean up response
            motd_text = response.strip()
            
            # Remove any markdown formatting
            motd_text = motd_text.replace("**", "").replace("*", "").replace("__", "")
            
            # Limit length
            if len(motd_text) > 250:
                motd_text = motd_text[:247] + "..."
            
            logger.info(f"[📅] MOTD generated: {motd_text[:50]}...")
            return motd_text
            
        except Exception as e:
            logger.error(f"[📅] Error generating MOTD: {e}", exc_info=True)
            # Fallback message
            return "Good morning! Let's make today creative and inspiring! 🌟"
    
    async def send_motd_to_channel(self, channel_id: int, guild_name: str) -> bool:
        """
        Generate and send MOTD to specified channel.
        
        Args:
            channel_id: Discord channel ID
            guild_name: Name of the guild for context
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                logger.warning(f"[📅] MOTD channel {channel_id} not found")
                return False
            
            # Ensure it's a text channel
            if not isinstance(channel, discord.TextChannel):
                logger.warning(f"[📅] Channel {channel_id} is not a text channel")
                return False
            
            # Check permissions
            permissions = channel.permissions_for(channel.guild.me)
            if not permissions.send_messages or not permissions.embed_links:
                logger.warning(f"[📅] No permission to send MOTD in {channel_id}")
                return False
            
            # Generate MOTD
            motd_text = await self.generate_motd(guild_name)
            self.last_motd = motd_text
            
            # Create embed
            embed = discord.Embed(
                title="📅 Message of the Day",
                description=motd_text,
                color=discord.Color.purple()
            )
            embed.set_footer(text=f"Generated for {guild_name}")
            
            # Send message
            await channel.send(embed=embed)
            logger.info(f"[📅] MOTD sent to {guild_name} (channel: {channel_id})")
            return True
            
        except discord.Forbidden:
            logger.error(f"[📅] Forbidden: Cannot send to channel {channel_id}")
            return False
        except Exception as e:
            logger.error(f"[📅] Error sending MOTD: {e}", exc_info=True)
            return False
    
    async def send_scheduled_motd(self, guild_id: int):
        """Scheduler entrypoint to send MOTD for a guild."""
        settings = get_memory_settings(guild_id)
        motd_channel_id = settings.get("channels", {}).get("motd", {}).get("id") if settings else None
        if not motd_channel_id:
            logger.debug(f"[📅] Guild {guild_id} has MOTD enabled but no channel set")
            return
        # Handle MongoDB NumberLong (stored as dict: {"$numberLong": "123..."})
        try:
            if isinstance(motd_channel_id, dict):
                motd_channel_id = int(motd_channel_id.get("$numberLong", 0))
            else:
                motd_channel_id = int(motd_channel_id)
        except (TypeError, ValueError) as e:
            logger.warning(f"[📅] Failed to parse MOTD channel ID for guild {guild_id}: {e}")
            return
        
        guild = self.bot.get_guild(guild_id)
        guild_name = guild.name if guild else "our community"
        await self.send_motd_to_channel(motd_channel_id, guild_name)
    
    def _get_cached_motd(self, guild_id: Optional[int]) -> Optional[str]:
        """Get cached MOTD from guild settings if it was generated today."""
        if not guild_id:
            return None
        
        try:
            settings = get_memory_settings(guild_id)
            motd_data = settings.get("motd_cache", {})
            
            # Check if MOTD was generated today
            if motd_data and motd_data.get("timestamp"):
                last_generated = datetime.fromisoformat(motd_data["timestamp"])
                if last_generated.date() == datetime.now().date():
                    return motd_data.get("text")
        except Exception as e:
            logger.warning(f"[📅] Error retrieving cached MOTD: {e}")
        
        return None
    
    def _cache_motd(self, guild_id: int, motd_text: str):
        """Cache MOTD in guild settings with timestamp."""
        try:
            settings = get_memory_settings(guild_id)
            settings["motd_cache"] = {
                "text": motd_text,
                "timestamp": datetime.now().isoformat()
            }
            set_memory_settings(guild_id, settings)
            logger.info(f"[📅] Cached MOTD for guild {guild_id}")
        except Exception as e:
            logger.warning(f"[📅] Error caching MOTD: {e}")
    
    async def motd_command(
        self, 
        interaction: discord.Interaction,
        send_to_channel: bool = False
    ):
        """Manually trigger MOTD generation or retrieval."""
        await interaction.response.defer(ephemeral=not send_to_channel)
        
        try:
            guild_name = interaction.guild.name if interaction.guild else "our community"
            guild_id = interaction.guild.id if interaction.guild else None
            
            if send_to_channel:
                # Check if user has admin permissions
                if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
                    await interaction.followup.send(
                        "❌ Only administrators can send MOTD to the channel.",
                        ephemeral=True
                    )
                    return
                
                # Send to configured channel
                motd_channel_id = self.config.channels.motd_channel
                if not motd_channel_id or motd_channel_id == 0:
                    await interaction.followup.send(
                        "❌ MOTD channel not configured. Set MOTD_CHANNEL_ID in environment.",
                        ephemeral=True
                    )
                    return
                
                success = await self.send_motd_to_channel(motd_channel_id, guild_name)
                
                if success:
                    await interaction.followup.send(
                        f"✅ MOTD sent to <#{motd_channel_id}>",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Failed to send MOTD. Check logs for details.",
                        ephemeral=True
                    )
            else:
                # Get cached MOTD or generate new one
                motd_text = self._get_cached_motd(guild_id)
                
                if not motd_text:
                    # Generate new MOTD and cache it
                    motd_text = await self.generate_motd(guild_name)
                    if guild_id:
                        self._cache_motd(guild_id, motd_text)
                else:
                    logger.info(f"[📅] Retrieved cached MOTD for guild {guild_id}")
                
                embed = discord.Embed(
                    title="📅 Message of the Day",
                    description=motd_text,
                    color=discord.Color.purple()
                )
                embed.set_footer(text="Preview - use send_to_channel=True to post publicly")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"[📅] Error in MOTD command: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while generating MOTD.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Load the MOTD cog."""
    await bot.add_cog(MOTD(bot))

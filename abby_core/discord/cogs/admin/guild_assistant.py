"""
Guild Assistant with Scheduled Maintenance and Mod Engagement

Features:
- Daily memory maintenance (called by centralized scheduler)
- Weekly summary report to mod channel with conversational insights
- Conditional open-ended questions for mod engagement
- Thread spawning for threaded mod conversations

The Guild Assistant is Abby's proactive component, keeping the guild healthy
and engaged while providing admins with actionable insights.

NOTE: Maintenance is now triggered by the canonical SchedulerService
"""

import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from abby_core.database.collections.guild_configuration import (
    get_guild_config,
    get_guild_setting,
    get_memory_settings,
)
from abby_core.database.mongodb import get_db
from tdos_intelligence.observability import logging
from abby_core.discord.core.mod_notifications import send_mod_notification

logger = logging.getLogger(__name__)


class GuildAssistant(commands.Cog):
    """Scheduled maintenance and guild assistant features."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_weekly_run = {}  # Track last weekly run per guild
        
        if logger:
            logger.debug("[🤖] Guild Assistant loaded")
    
    async def run_guild_maintenance(self, guild_id: int) -> Dict[str, Any]:
        """
        Run memory maintenance for a specific guild.
        
        Called by centralized scheduler for each guild at configured time (default 20:00).
        
        Args:
            guild_id: Guild ID to run maintenance for
            
        Returns:
            Maintenance statistics dict
        """
        try:
            try:
                guild_id = int(guild_id)
            except (TypeError, ValueError):
                if logger:
                    logger.warning(f"[🤖] Invalid guild id for maintenance: {guild_id}")
                return {}
            if guild_id <= 0:
                if logger:
                    logger.warning(f"[🤖] Skipping maintenance for invalid guild id {guild_id}")
                return {}
            # Check MongoDB availability
            from abby_core.database.mongodb import is_mongodb_available
            if not is_mongodb_available():
                if logger:
                    logger.warning(f"[🤖] Skipping maintenance for guild {guild_id}: MongoDB unavailable")
                return {}
            
            # Get guild
            guild = self.bot.get_guild(guild_id)
            if not guild:
                if logger:
                    logger.warning(f"[🤖] Guild {guild_id} not found")
                return {}
            
            # Check if maintenance is enabled
            if not get_memory_settings:
                if logger:
                    logger.warning(f"[🤖] get_memory_settings unavailable")
                return {}
            
            loop = asyncio.get_event_loop()
            settings = await loop.run_in_executor(None, get_memory_settings, guild_id)
            if not settings.get("enabled", True):
                if logger:
                    logger.debug(f"[🤖] Maintenance disabled for guild {guild_id}")
                return {}
            
            if not settings.get("decay_enabled", True):
                if logger:
                    logger.debug(f"[🤖] Decay disabled for guild {guild_id}")
                return {}
            
            if logger:
                logger.info(f"[🤖] Starting memory maintenance for guild {guild_id}")
            
            # Run maintenance
            if not get_db or not run_maintenance:
                if logger:
                    logger.warning(f"[🤖] Database or maintenance functions unavailable")
                return {}
            
            db = get_db()
            decay_threshold = settings.get("retention_days", 90) // 7  # Weekly decay
            prune_threshold = settings.get("confidence_threshold", 0.3)
            
            stats = run_maintenance(
                storage_client=db.client,
                db_name=db.name,  # Use configured database name (respects dev/prod)
                decay_days_threshold=decay_threshold,
                confidence_prune_threshold=prune_threshold,
                logger=logger
            )
            
            # Determine if this is weekly run
            today = datetime.utcnow().date()
            last_run_date = self.last_weekly_run.get(guild_id, None)
            is_weekly_run = (last_run_date is None or (today - last_run_date).days >= 7)
            
            if is_weekly_run:
                # Send comprehensive weekly report with potential question
                await self._send_weekly_report(guild, stats)
                self.last_weekly_run[guild_id] = today
            else:
                # Send minimal daily notification
                await self._send_daily_notification(guild, stats)
            
            if logger:
                logger.info(
                    f"[🤖] Maintenance complete for {guild.name}",
                    extra={
                        "guild_id": guild_id,
                        "profiles_processed": stats.get("profiles_processed"),
                        "facts_decayed": stats.get("facts_decayed"),
                        "is_weekly": is_weekly_run
                    }
                )
            
            return stats
        
        except Exception as e:
            if logger:
                logger.error(f"[🤖] Maintenance failed for guild {guild_id}: {e}", exc_info=True)
            
            # Optionally alert mods of maintenance failure
            if send_mod_notification:
                try:
                    await send_mod_notification(
                        self.bot,
                        guild_id,
                        level="ERROR",
                        title="Maintenance Error",
                        description=f"Memory maintenance failed: {str(e)[:200]}",
                        color=discord.Color.red()
                    )
                except:
                    pass
            
            return {}
    
    async def _send_daily_notification(self, guild: discord.Guild, stats: dict):
        """Send minimal daily maintenance notification."""
        try:
            if not get_memory_settings:
                return
            
            guild_id = guild.id
            settings = get_memory_settings(guild_id)
            mod_channel_id = settings.get("mod_channel_id")
            
            if not mod_channel_id:
                return
            
            # Handle MongoDB NumberLong format
            try:
                if isinstance(mod_channel_id, dict) and "$numberLong" in mod_channel_id:
                    channel_id_value = mod_channel_id["$numberLong"]
                    mod_channel_id = int(channel_id_value)
                elif isinstance(mod_channel_id, (int, str)):
                    mod_channel_id = int(mod_channel_id)
                else:
                    return
            except (TypeError, ValueError):
                return
            
            channel = self.bot.get_channel(mod_channel_id)
            if not channel:
                return
            
            # Create minimal embed
            embed = discord.Embed(
                title="✅ Daily Maintenance Complete",
                description="Memory system maintenance finished",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="Facts Decayed", value=str(stats.get("facts_decayed", 0)), inline=True)
            embed.add_field(name="Facts Pruned", value=str(stats.get("facts_pruned", 0)), inline=True)
            embed.set_footer(text="Guild Assistant 🤖")
            
            if isinstance(channel, discord.TextChannel):
                await channel.send(embed=embed)
        
        except Exception as e:
            if logger:
                logger.error(f"[🤖] Failed to send daily notification: {e}")
    
    async def _send_weekly_report(self, guild: discord.Guild, stats: dict):
        """Send comprehensive weekly report with optional mod engagement."""
        try:
            if not get_memory_settings:
                return
            
            guild_id = guild.id
            settings = get_memory_settings(guild_id)
            mod_channel_id = settings.get("mod_channel_id")
            
            if not mod_channel_id:
                return
            
            channel = self.bot.get_channel(int(mod_channel_id))
            if not channel:
                return
            
            # Create comprehensive embed
            embed = discord.Embed(
                title="📊 Weekly Memory Maintenance Report",
                description=f"Memory system update for {guild.name}",
                color=discord.Color.purple(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="📝 Maintenance Operations",
                value=f"**Profiles Processed:** {stats.get('profiles_processed', 0)}\n"
                      f"**Facts Decayed:** {stats.get('facts_decayed', 0)}\n"
                      f"**Facts Pruned:** {stats.get('facts_pruned', 0)}",
                inline=False
            )
            
            embed.add_field(
                name="💾 Storage",
                value=f"**Sessions Archived:** {stats.get('sessions_archived', 0)}\n"
                      f"**Caches Invalidated:** {stats.get('caches_invalidated', 0)}",
                inline=False
            )
            
            if stats.get("errors"):
                embed.add_field(
                    name="⚠️ Errors",
                    value=f"{len(stats['errors'])} error(s) encountered",
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ Status",
                    value="All systems healthy",
                    inline=False
                )
            
            # Determine if we should ask a question (conditional engagement)
            should_ask_question = await self._should_ask_mod_question(guild, stats)
            
            # Send initial report
            if not isinstance(channel, discord.TextChannel):
                return
            report_message = await channel.send(embed=embed)
            
            if should_ask_question:
                # Generate contextual question
                question = await self._generate_mod_question(guild, stats)
                
                # Create thread for mod responses
                thread = await report_message.create_thread(
                    name="Guild Assistant Discussion",
                    auto_archive_duration=4320  # 3 days
                )
                
                # Post question in thread
                await thread.send(f"💭 {question}")
                
                if logger:
                    logger.info(f"[🤖] Posted question in thread for {guild.name}")
            
            if logger:
                logger.info(f"[🤖] Weekly report sent to {guild.name}")
        
        except Exception as e:
            if logger:
                logger.error(f"[🤖] Failed to send weekly report: {e}", exc_info=True)
    
    async def _should_ask_mod_question(self, guild: discord.Guild, stats: dict) -> bool:
        """Determine if a question should be asked (conditional logic)."""
        try:
            facts_decayed = stats.get("facts_decayed", 0)
            profiles_processed = stats.get("profiles_processed", 0)
            facts_pruned = stats.get("facts_pruned", 0)
            
            # Heuristic: ask if decayed facts > 100 or profiles_processed == 0
            if facts_decayed > 100 or profiles_processed == 0:
                return True
            
            # Ask if pruning ratio is high (>30%)
            if facts_decayed > 0 and (facts_pruned / max(facts_decayed, 1)) > 0.3:
                return True
            
            return False
        
        except:
            return False
    
    async def _generate_mod_question(self, guild: discord.Guild, stats: dict) -> str:
        """Generate a contextual question for mods."""
        try:
            if not get_db:
                return "How can I improve the memory system?"
            
            facts_decayed = stats.get("facts_decayed", 0)
            profiles_processed = stats.get("profiles_processed", 0)
            facts_pruned = stats.get("facts_pruned", 0)
            
            from abby_core.database.collections.users import get_top_users_by_fact_count

            # Get some profile info
            guild_id = str(guild.id)
            top_users = get_top_users_by_fact_count(guild_id, limit=3)
            
            # Generate contextual questions
            if profiles_processed == 0:
                return "I've noticed memory activity seems quiet. What's happening in the guild? Any topics or activities I should be aware of?"
            
            if facts_decayed > 200:
                question = f"I've processed {facts_decayed} memory facts this week - that's a lot of activity! "
                if top_users:
                    top_user = top_users[0]
                    question += f"I see {top_user['username']} has been quite engaged. "
                question += "What discussions or activities have been most impactful for your community?"
                return question
            
            if facts_pruned > facts_decayed * 0.3:
                return "I've had to prune some low-confidence memories. What topics or conversations are most important to remember for your community?"
            
            if top_users:
                top_user = top_users[0]
                return f"I've been learning a lot about {top_user['username']} and others in the community. What would help me be more valuable to your guild?"
            
            # Default question
            return "How can I better support your community? Are there any specific ways I could improve?"
        
        except Exception as e:
            if logger:
                logger.error(f"[🤖] Failed to generate question: {e}")
            return "How can I better support your community this week?"


async def setup(bot: commands.Bot):
    await bot.add_cog(GuildAssistant(bot))

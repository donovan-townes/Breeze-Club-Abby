"""
Guild Assistant with Scheduled Maintenance and Mod Engagement

Features:
- Daily memory maintenance task (decay, prune, archive)
- Weekly summary report to mod channel with conversational insights
- Conditional open-ended questions for mod engagement
- Thread spawning for threaded mod conversations
- Auto-archive after 3 days of inactivity

The Guild Assistant is Abby's proactive component, keeping the guild healthy
and engaged while providing admins with actionable insights.
"""

import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
from typing import Optional

try:
    from abby_core.database.memory_settings import get_memory_settings, get_guild_setting
    from abby_core.database.mongodb import get_db
    from abby_core.observability.logging import logging
    from abby_adapters.discord.core.mod_notifications import send_mod_notification
    from tdos_memory.maintenance import run_maintenance
except ImportError:
    logging = None

logger = logging.getLogger(__name__) if logging else None


class GuildAssistant(commands.Cog):
    """Scheduled maintenance and guild assistant features."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_weekly_run = {}  # Track last weekly run per guild
        
        if logger:
            logger.info("[🤖] Guild Assistant loaded")
    
    async def cog_load(self):
        """Start maintenance task when cog loads."""
        if not self.daily_maintenance.is_running():
            self.daily_maintenance.start()
            if logger:
                logger.info("[🤖] Daily maintenance task started")
    
    async def cog_unload(self):
        """Stop maintenance task when cog unloads."""
        if self.daily_maintenance.is_running():
            self.daily_maintenance.cancel()
            if logger:
                logger.info("[🤖] Daily maintenance task stopped")
    
    @tasks.loop(hours=24)
    async def daily_maintenance(self):
        """
        Run daily memory maintenance across all guilds.
        
        Sends minimal daily notification and comprehensive weekly summary.
        """
        if logger:
            logger.info("[🤖] Starting daily maintenance cycle")
        
        for guild in self.bot.guilds:
            try:
                guild_id = guild.id
                
                # Check if maintenance is enabled
                settings = get_memory_settings(guild_id)
                if not settings.get("enabled", True):
                    continue
                
                if not settings.get("decay_enabled", True):
                    continue
                
                # Get rate limiting delay
                await asyncio.sleep(5)  # 5 second delay between guilds
                
                # Run maintenance
                db = get_db()
                decay_threshold = settings.get("retention_days", 90) // 7  # Weekly decay
                prune_threshold = settings.get("confidence_threshold", 0.3)
                
                stats = run_maintenance(
                    storage_client=db.client,
                    db_name="Abby_Database",
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
            
            except Exception as e:
                if logger:
                    logger.error(
                        f"[🤖] Maintenance failed for {guild.name}: {e}",
                        exc_info=True
                    )
                
                # Optionally alert mods of maintenance failure
                try:
                    await send_mod_notification(
                        self.bot,
                        guild.id,
                        level="ERROR",
                        title="Maintenance Error",
                        description=f"Memory maintenance failed: {str(e)[:200]}",
                        color=discord.Color.red()
                    )
                except:
                    pass
    
    async def _send_daily_notification(self, guild: discord.Guild, stats: dict):
        """Send minimal daily maintenance notification."""
        try:
            guild_id = guild.id
            settings = get_memory_settings(guild_id)
            mod_channel_id = settings.get("mod_channel_id")
            
            if not mod_channel_id:
                return
            
            channel = self.bot.get_channel(int(mod_channel_id))
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
            
            await channel.send(embed=embed)
        
        except Exception as e:
            if logger:
                logger.error(f"[🤖] Failed to send daily notification: {e}")
    
    async def _send_weekly_report(self, guild: discord.Guild, stats: dict):
        """Send comprehensive weekly report with optional mod engagement."""
        try:
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
            # Ask questions if:
            # 1. High number of facts decayed (indicates active community)
            # 2. Low number of profiles (possible engagement issue)
            # 3. Many facts pruned (possible data quality issue)
            
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
            facts_decayed = stats.get("facts_decayed", 0)
            profiles_processed = stats.get("profiles_processed", 0)
            facts_pruned = stats.get("facts_pruned", 0)
            
            db = get_db()
            profiles_collection = db["discord_profiles"]
            
            # Get some profile info
            guild_id = str(guild.id)
            top_users = list(profiles_collection.aggregate([
                {"$match": {"guild_id": guild_id}},
                {"$addFields": {
                    "fact_count": {"$size": {"$ifNull": ["$creative_profile.memorable_facts", []]}}
                }},
                {"$sort": {"fact_count": -1}},
                {"$limit": 3},
                {"$project": {"username": 1, "fact_count": 1}}
            ]))
            
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
    
    @daily_maintenance.before_loop
    async def before_maintenance(self):
        """Wait for bot to be ready before starting maintenance."""
        await self.bot.wait_until_ready()
        
        if logger:
            logger.info("[🤖] Guild Assistant ready for maintenance")


async def setup(bot: commands.Bot):
    await bot.add_cog(GuildAssistant(bot))

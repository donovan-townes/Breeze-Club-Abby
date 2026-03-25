"""
Slash command synchronization and bot control commands.

Essential admin-only commands for managing slash command registration
and bot state. These are prefix commands (!sync, !reload) for emergency
bot management.

Commands:
- !sync [~|*|^] - Sync slash commands to Discord
- !reload - Reload modified cogs
"""

from typing import Literal, Optional, Any
import discord
from discord.ext import commands
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


class SlashSyncCommands(commands.Cog):
    """Handle slash command synchronization and bot control."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Some bot instances may not expose command_handler; guard for None
        self.commander: Optional[Any] = getattr(self.bot, "command_handler", None)

    async def _sync_tree(self, ctx: commands.Context, *, target_guild: Optional[discord.abc.Snowflake] = None, mode: str = "global") -> tuple[list[discord.app_commands.Command], str]:
        """Perform sync and return (synced_commands, human_readable_message)."""
        tree = ctx.bot.tree
        guild = ctx.guild

        # Modes: global, guild, copy, clear
        if mode == "guild":
            if guild is None:
                raise ValueError("Guild-only sync requires a guild context")
            synced = await tree.sync(guild=guild)
            guild_name = getattr(guild, "name", "this guild")
            msg = f"✅ Synced {len(synced)} commands to {guild_name} (guild-only)"
        elif mode == "copy":
            if guild is None:
                raise ValueError("Copy sync requires a guild context")
            tree.copy_global_to(guild=guild)
            synced = await tree.sync(guild=guild)
            guild_name = getattr(guild, "name", "this guild")
            msg = f"✅ Copied & synced {len(synced)} commands to {guild_name}"
        elif mode == "clear":
            if guild is None:
                raise ValueError("Clear sync requires a guild context")
            tree.clear_commands(guild=guild)
            synced = await tree.sync(guild=guild)
            guild_name = getattr(guild, "name", "this guild")
            msg = f"🧹 Cleared and synced {len(synced)} commands for {guild_name}"
        else:
            synced = await tree.sync()
            msg = f"🌍 Synced {len(synced)} commands globally (may take up to 1 hour)"
        return synced, msg

    @commands.guild_only()
    @commands.is_owner()
    @commands.command(name="sync")
    async def sync(self, ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        """Sync slash commands to Discord.
        
        Usage:
        - !sync          → Sync ALL commands globally (1 hour delay)
        - !sync ~        → Sync commands to THIS GUILD ONLY (instant)
        - !sync *        → Copy global commands to this guild then sync (instant)
        - !sync ^        → CLEAR all commands from this guild (emergency reset)
        """
        if not guilds:
            try:
                if spec == "~":
                    synced, msg = await self._sync_tree(ctx, mode="guild")
                    color = discord.Color.green()
                elif spec == "*":
                    synced, msg = await self._sync_tree(ctx, mode="copy")
                    color = discord.Color.green()
                elif spec == "^":
                    synced, msg = await self._sync_tree(ctx, mode="clear")
                    color = discord.Color.orange()
                else:
                    synced, msg = await self._sync_tree(ctx, mode="global")
                    color = discord.Color.blurple()
            except Exception as exc:  # Surface failure clearly
                logger.error(f"[🔄] Sync failed: {exc}", exc_info=True)
                await ctx.send(f"❌ Sync failed: {exc}")
                return

            embed = discord.Embed(
                title="🔄 Slash Command Sync",
                description=msg,
                color=color
            )
            embed.add_field(
                name="💡 Quick Help",
                value="`!sync ~` - Guild only (fast)\n"
                      "`!sync` - Global (slow)\n"
                      "`!sync *` - Copy global to guild, then sync\n"
                      "`!sync ^` - Clear guild commands",
                inline=False
            )
            await ctx.send(embed=embed)
            logger.info(f"[🔄] Slash command sync: {msg}")
            return

        successes = 0
        failures = []
        for guild in guilds:
            try:
                synced = await ctx.bot.tree.sync(guild=guild)
                successes += 1
                logger.info(f"[🔄] Synced {len(synced)} commands to guild {guild.id}")
            except Exception as exc:
                failures.append((guild.id, str(exc)))
                logger.error(f"[🔄] Sync failed for guild {guild.id}: {exc}")

        summary = f"Synced {successes}/{len(guilds)} guilds."
        if failures:
            failure_lines = "\n".join([f"• {gid}: {err}" for gid, err in failures])
            summary += f"\nFailures:\n{failure_lines}"
        await ctx.send(summary)

    @commands.guild_only()
    @commands.is_owner()
    @commands.command(name="reload")
    async def reload(self, ctx: commands.Context) -> None:
        """Reload modified cogs from disk."""
        try:
            await ctx.send("🔄 Reloading cogs...")
            if not self.commander:
                raise RuntimeError("command_handler not available on bot")
            await self.commander.reload_cogs(ctx=ctx)
            logger.info("[🔄] Cogs reloaded successfully")
        except Exception as e:
            logger.error(f"[❌] Error reloading cogs: {e}")
            await ctx.send(f"❌ Error reloading cogs: {e}")


async def setup(bot: commands.Bot) -> None:
    """Load the SlashSyncCommands cog."""
    await bot.add_cog(SlashSyncCommands(bot))
    logger.debug("[✅] SlashSyncCommands cog loaded")

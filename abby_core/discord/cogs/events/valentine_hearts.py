"""
Valentine's Day Hearts Event Handler

When crush_system_enabled is active, hearts spawn in random channels.
First reactor gets +5 XP (with multipliers applied) and +1 crush score.
"""

import asyncio
import random
from datetime import datetime
from typing import Dict, Any, Optional
from discord.ext import commands
from discord import TextChannel

try:
    from tdos_intelligence.observability import logging
    logger = logging.getLogger(__name__)
except ImportError:
    logger = None


async def spawn_valentine_heart(
    bot: commands.Bot,
    guild_id: int,
    channel_id: Optional[int] = None,
) -> bool:
    """
    Spawn a random heart in a channel.
    
    Args:
        bot: Discord bot instance
        guild_id: Guild ID for XP tracking
        channel_id: Optional specific channel. If None, picks random text channel.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        guild = bot.get_guild(guild_id)
        if not guild:
            if logger:
                logger.warning(f"[💗] Guild {guild_id} not found")
            return False
        
        # Get text channels (skip bot-only, archived, etc.)
        text_channels: list[TextChannel] = [
            ch for ch in guild.text_channels
            if isinstance(ch, TextChannel)
            and ch.permissions_for(guild.me).send_messages
            and ch.permissions_for(guild.me).embed_links
        ]
        
        if not text_channels:
            if logger:
                logger.warning(f"[💗] No accessible text channels in guild {guild_id}")
            return False
        
        # Pick channel
        if channel_id:
            channel: TextChannel = guild.get_channel(channel_id)  # type: ignore
            if not channel:
                channel = random.choice(text_channels)
        else:
            channel: TextChannel = random.choice(text_channels)
        
        # Send heart message
        heart_message = await channel.send("💗 *A wild heart appears!*")
        await heart_message.add_reaction("💗")
        
        if logger:
            logger.debug(f"[💗] Heart spawned in {channel.name} ({guild.name})")
        
        # Listen for reactions (60 second timeout)
        def check(reaction, user):
            return (
                str(reaction.emoji) == "💗"
                and not user.bot
                and reaction.message.id == heart_message.id
            )
        
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=60, check=check)
            
            # Award XP
            from abby_core.economy.xp import increment_xp, get_xp, get_level_from_xp
            
            xp_gain = 5  # Base reward
            increment_xp(user.id, xp_gain, guild_id)
            
            user_data = get_xp(user.id) or {}
            new_xp = user_data.get("points", 0)
            new_level = get_level_from_xp(new_xp)
            
            # Award crush score (shimmed - update metadata)
            # TODO: Implement proper crush system
            crush_shimmed = _increment_crush_shim(user.id, 1)
            
            user_name = getattr(user, "display_name", None) or user.name
            await channel.send(
                f"✨ **{user_name}** caught the heart!\n"
                f"**+{xp_gain} XP** (Total: {new_xp:,} | Level {new_level})\n"
                f"**+1 💗** Crush Score"
            )
            
            if logger:
                logger.info(
                    f"[💗] {user.name}#{user.discriminator} caught heart in "
                    f"{guild.name}/{channel.name} (+{xp_gain} XP, +1 crush)"
                )
            
            # Delete heart message after reaction
            try:
                await heart_message.delete()
            except Exception:
                pass  # Message already deleted or permissions issue
            
            return True
            
        except asyncio.TimeoutError:
            # No one reacted in 60 seconds
            try:
                await heart_message.edit(content="💔 *The heart disappeared...*")
                await asyncio.sleep(5)
                await heart_message.delete()
            except Exception:
                pass
            
            if logger:
                logger.debug(f"[💗] Heart expired in {channel.name} (no reactors)")
            
            return False
            
    except Exception as exc:
        if logger:
            logger.error(f"[💗] Error spawning heart: {exc}", exc_info=True)
        return False


def _increment_crush_shim(user_id: int, amount: int = 1) -> int:
    """
    Temporary crush score tracker (shimmed in config).
    
    TODO: Implement proper crush system with:
    - MongoDB collection for crush state
    - Per-user crush score persistence
    - Leaderboard queries
    - Decay over time (optional)
    """
    # For now, just return the increment amount
    # This will be replaced with real persistence
    return amount


async def handle_valentine_hearts_job(
    bot: commands.Bot,
    guild_id: int,
    job_config: Dict[str, Any],
) -> bool:
    """
    Job handler for spawning valentine hearts.
    
    Called every N minutes by scheduler (with jitter).
    Checks if crush_system_enabled effect is active,
    then randomly decides whether to spawn a heart this tick.
    
    Job config:
        - enabled: bool
        - spawn_chance: float (0-1, default 0.3)
        - max_spawns_per_run: int (default 1)
        - last_executed_at: ISO timestamp
    
    Returns:
        True if job executed, False if skipped
    """
    try:
        # Check if effect is active
        from abby_core.llm.system_state_resolver import resolve_system_state
        from abby_core.system.effect_checker import is_effect_active
        
        if not is_effect_active("crush_system_enabled"):
            if logger:
                logger.debug("[💗] crush_system_enabled not active, skipping hearts")
            return False
        
        # Get spawn parameters
        spawn_chance = job_config.get("spawn_chance", 0.3)
        max_spawns = job_config.get("max_spawns_per_run", 1)
        
        # Random decision: spawn or skip
        if random.random() > spawn_chance:
            return False  # Skip this run (chance didn't trigger)
        
        # Spawn heart(s)
        spawned = 0
        for _ in range(max_spawns):
            if await spawn_valentine_heart(bot, guild_id):
                spawned += 1
                # Small delay between multiple spawns
                if spawned < max_spawns:
                    await asyncio.sleep(2)
        
        return spawned > 0
        
    except Exception as exc:
        if logger:
            logger.error(f"[💗] Hearts job handler failed: {exc}", exc_info=True)
        return False

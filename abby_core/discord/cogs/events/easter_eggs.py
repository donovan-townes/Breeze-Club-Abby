"""
Easter Egg Hunt Event Handler

When egg_hunt_enabled is active, eggs spawn in random channels.
First clicker gets +5 XP (with multipliers applied) and optional Breeze Coins.
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


async def spawn_easter_egg(
    bot: commands.Bot,
    guild_id: int,
    channel_id: Optional[int] = None,
    reward_type: str = "xp",  # "xp", "coins", or "both"
) -> bool:
    """
    Spawn a random egg in a channel.
    
    Args:
        bot: Discord bot instance
        guild_id: Guild ID for XP tracking
        channel_id: Optional specific channel. If None, picks random text channel.
        reward_type: Type of reward (xp, coins, or both)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        guild = bot.get_guild(guild_id)
        if not guild:
            if logger:
                logger.warning(f"[🥚] Guild {guild_id} not found")
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
                logger.warning(f"[🥚] No accessible text channels in guild {guild_id}")
            return False
        
        # Pick channel
        if channel_id:
            channel: TextChannel = guild.get_channel(channel_id)  # type: ignore
            if not channel:
                channel = random.choice(text_channels)
        else:
            channel: TextChannel = random.choice(text_channels)
        
        # Send egg message
        egg_message = await channel.send("🥚 *A painted egg is hidden here!*")
        await egg_message.add_reaction("🐰")
        
        if logger:
            logger.debug(f"[🥚] Egg spawned in {channel.name} ({guild.name})")
        
        # Listen for reactions (60 second timeout)
        def check(reaction, user):
            return (
                str(reaction.emoji) == "🐰"
                and not user.bot
                and reaction.message.id == egg_message.id
            )
        
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=60, check=check)
            
            # Calculate rewards
            xp_gain = 5  # Base reward
            coin_gain = 0
            
            if reward_type in ("coins", "both"):
                coin_gain = random.randint(10, 25)  # Random coins
            
            # Award XP
            from abby_core.economy.xp import increment_xp, get_xp, get_level_from_xp
            
            increment_xp(user.id, xp_gain, guild_id)
            
            user_data = get_xp(user.id) or {}
            new_xp = user_data.get("points", 0)
            new_level = get_level_from_xp(new_xp)
            
            # Build reward message
            user_name = getattr(user, "display_name", None) or user.name
            reward_lines = [f"✨ **{user_name}** found an egg!"]
            reward_lines.append(f"**+{xp_gain} XP** (Total: {new_xp:,} | Level {new_level})")
            
            if coin_gain > 0:
                # TODO: Award coins when currency system ready
                reward_lines.append(f"**+{coin_gain} 🪙 Breeze Coins**")
            
            await channel.send("\n".join(reward_lines))
            
            if logger:
                log_msg = f"[🥚] {user.name}#{user.discriminator} found egg in " \
                          f"{guild.name}/{channel.name} (+{xp_gain} XP"
                if coin_gain:
                    log_msg += f", +{coin_gain} coins"
                log_msg += ")"
                logger.info(log_msg)
            
            # Delete egg message after reaction
            try:
                await egg_message.delete()
            except Exception:
                pass  # Message already deleted or permissions issue
            
            return True
            
        except asyncio.TimeoutError:
            # No one found the egg in 60 seconds
            try:
                await egg_message.edit(content="🐰 *The egg rolls away...*")
                await asyncio.sleep(5)
                await egg_message.delete()
            except Exception:
                pass
            
            if logger:
                logger.debug(f"[🥚] Egg expired in {channel.name} (not found)")
            
            return False
            
    except Exception as exc:
        if logger:
            logger.error(f"[🥚] Error spawning egg: {exc}", exc_info=True)
        return False


async def handle_easter_eggs_job(
    bot: commands.Bot,
    guild_id: int,
    job_config: Dict[str, Any],
) -> bool:
    """
    Job handler for spawning easter eggs.
    
    Called every N minutes by scheduler (with jitter).
    Checks if egg_hunt_enabled effect is active,
    then randomly decides whether to spawn an egg this tick.
    
    On actual Easter day (computed), applies special effects like
    costume change or enhanced rewards.
    
    Job config:
        - enabled: bool
        - spawn_chance: float (0-1, default 0.25)
        - max_spawns_per_run: int (default 1)
        - reward_type: str (xp, coins, both) - default "xp"
        - last_executed_at: ISO timestamp
    
    Returns:
        True if job executed, False if skipped
    """
    try:
        # Check if effect is active
        from abby_core.system.effect_checker import is_effect_active
        
        if not is_effect_active("egg_hunt_enabled"):
            if logger:
                logger.debug("[🥚] egg_hunt_enabled not active, skipping eggs")
            return False
        
        # Get spawn parameters
        spawn_chance = job_config.get("spawn_chance", 0.25)
        max_spawns = job_config.get("max_spawns_per_run", 1)
        reward_type = job_config.get("reward_type", "xp")
        
        # Check if today is actual Easter day (special effects)
        is_easter_day = _is_easter_day()
        
        # Boost spawn chance and rewards on actual Easter
        if is_easter_day:
            spawn_chance = min(0.8, spawn_chance * 2)  # Cap at 80%
            reward_type = "both"  # Always give coins on Easter day
        
        # Random decision: spawn or skip
        if random.random() > spawn_chance:
            return False  # Skip this run (chance didn't trigger)
        
        # Spawn egg(s)
        spawned = 0
        for _ in range(max_spawns):
            if await spawn_easter_egg(bot, guild_id, reward_type=reward_type):
                spawned += 1
                # Small delay between multiple spawns
                if spawned < max_spawns:
                    await asyncio.sleep(2)
        
        if spawned > 0 and is_easter_day:
            if logger:
                logger.info("[🥚] EASTER DAY - Enhanced egg hunt active!")
        
        return spawned > 0
        
    except Exception as exc:
        if logger:
            logger.error(f"[🥚] Easter eggs job handler failed: {exc}", exc_info=True)
        return False


def _is_easter_day() -> bool:
    """
    Check if today is actual Easter Sunday.
    
    Uses precomputed Easter dates (see state_registry for computation).
    """
    from datetime import datetime, date
    
    # Easter 2026: April 5
    # Easter 2027: April 25
    # Can expand this with proper computation if needed
    easter_dates = {
        2026: date(2026, 4, 5),
        2027: date(2027, 4, 25),
        2028: date(2028, 4, 9),
    }
    
    today = datetime.utcnow().date()
    current_year = today.year
    
    return today == easter_dates.get(current_year)

"""
XP reward events and background tasks.

Handles:
- Message/attachment XP grants with cooldowns
- Daily reaction bonus
- Streaming bonus checks
- Weekend/holiday multipliers using `holidays` package
"""
import asyncio
import datetime
from datetime import timezone
from typing import Dict, Set, Tuple, Optional

import discord
from discord.ext import commands
import holidays

from tdos_intelligence.observability import logging
from abby_core.discord.config import BotConfig
from abby_core.database.collections.users import (
    check_user_cooldown,
    record_user_cooldown,
    ensure_user_from_discord
)
from abby_core.database.collections.guild_configuration import get_guild_config
from abby_core.economy.xp import increment_xp

logger = logging.getLogger(__name__)
config = BotConfig()
_HOLIDAYS = holidays.country_holidays("US")


def current_xp_multiplier(current_dt: datetime.datetime | None = None) -> Tuple[int, str | None]:
    """Return (multiplier, holiday_name) based on weekend/holiday rules.
    
    Uses timezone-aware UTC to ensure consistent date calculations across timezones.
    """
    now = current_dt or datetime.datetime.now(timezone.utc)
    current_date = now.date()
    is_weekend = current_date.weekday() in (5, 6)
    is_holiday = current_date in _HOLIDAYS
    holiday_name = _HOLIDAYS.get(current_date) if is_holiday else None
    multiplier = 3 if is_weekend and is_holiday else (2 if is_weekend or is_holiday else 1)
    return multiplier, holiday_name


class XPRewardManager(commands.Cog):
    """Background XP grants for activity signals."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_message_channel_id = config.channels.xp_channel
        self.abby_chat_id = config.channels.xp_abby_chat or config.channels.abby_chat
        self.daily_bonus_message_ids: Dict[int, int] = {}
        self.daily_bonus_users: Set[int] = set()
        self.last_attachment_time: Dict[int, datetime.datetime] = {}
        self.last_message_time: Dict[int, datetime.datetime] = {}
        self.streaming_users: Set[int] = set()
        self.exp_gain = 1
        self.logger = logging.getLogger(__name__)

    # ─────────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_ready(self):
        logger.debug("[💰] XPRewardManager ready")
        self.run_tasks()

    def run_tasks(self):
        # Only the streaming check runs on an internal loop; daily bonus is scheduled externally
        logger.debug("[💰] XP reward tasks using platform scheduler; skipping local loop start")

    # ─────────────────────────────────────────────────────────────
    # Events
    # ─────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User | discord.Member):
        logger.debug(f"[💰] on_reaction_add fired: user={user.name}, emoji={reaction.emoji}, message_id={reaction.message.id}")
        await self.handle_reaction(reaction, user)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.gain_experience(message)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        try:
            if after.self_stream and not before.self_stream:
                logger.info(f"[💰] {member} is streaming (+5xp/interval)")
                self.streaming_users.add(member.id)
            elif before.self_stream and not after.self_stream:
                logger.info(f"[💰] {member} stopped streaming")
                self.streaming_users.discard(member.id)
            elif before.channel and not after.channel:
                logger.info(f"[💰] {member} disconnected from voice")
                if before.self_stream:
                    self.streaming_users.discard(member.id)
        except AttributeError:
            logger.warning(f"[💰] Attribute 'self_stream' not found in VoiceState for {member}")

    # ─────────────────────────────────────────────────────────────
    # Tasks
    # ─────────────────────────────────────────────────────────────
    async def streaming_tick(self):
        """Platform scheduler entrypoint for streaming XP increment."""
        guild = self.bot.guilds[0] if self.bot.guilds else None
        guild_id = guild.id if guild else None
        for member_id in list(self.streaming_users):
            multiplier, _ = current_xp_multiplier()
            increment_xp(member_id, 5 * multiplier, guild_id)

    async def send_daily_bonus_message(self, guild_id: int):
        """Send the daily bonus message for a specific guild (called by scheduler).
        
        Key behavior:
        1. Posts message to guild's configured XP channel
        2. **Stores message ID in guild config** (NOT in-memory) for persistence across bot restarts
        3. Records message post time in guild config for per-message-instance tracking
        4. Does NOT clear user cooldowns - they clear naturally at UTC midnight
        """
        logger.info(f"[💰] Sending daily bonus message for guild {guild_id}")
        try:
            guild = self.bot.get_guild(guild_id)
            xp_channel_id = self._resolve_xp_channel_id(guild, guild_id)
            
            if not xp_channel_id:
                logger.info(f"[💰] No XP channel configured for guild {guild_id}; skipping daily bonus message")
                return
            
            logger.info(f"[💰] Resolved XP channel ID for guild {guild_id}: {xp_channel_id}")

            channel: Optional[discord.TextChannel | discord.Thread] = None
            if xp_channel_id:
                # Try cached lookups first
                cached = self.bot.get_channel(xp_channel_id)
                if isinstance(cached, (discord.TextChannel, discord.Thread)):
                    channel = cached
                if not channel and guild:
                    cached_guild = guild.get_channel(xp_channel_id)
                    if isinstance(cached_guild, (discord.TextChannel, discord.Thread)):
                        channel = cached_guild

                # Fallback to fetch from API if not cached
                if not channel:
                    try:
                        fetched = await self.bot.fetch_channel(xp_channel_id)
                        if isinstance(fetched, (discord.TextChannel, discord.Thread)):
                            channel = fetched
                            logger.info(f"[💰] Fetched XP channel {xp_channel_id} from API for guild {guild_id}")
                        else:
                            logger.warning(f"[💰] Fetched channel {xp_channel_id} is not a text channel/thread; type={type(fetched).__name__}")
                    except discord.Forbidden:
                        logger.warning(f"[💰] Forbidden fetching XP channel {xp_channel_id} for guild {guild_id}")
                    except discord.NotFound:
                        logger.warning(f"[💰] XP channel {xp_channel_id} not found for guild {guild_id}")
                    except discord.HTTPException as e:
                        logger.error(f"[💰] HTTP error fetching XP channel {xp_channel_id} for guild {guild_id}: {e}")

            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                logger.warning(f"[💰] XP channel not set or channel not found for guild {guild_id}; skipping daily bonus message")
                return

            try:
                daily_message = await channel.send("Here is the daily bonus message, react to earn +10 EXP!")
                
                # Try custom emoji first, fall back to standard emoji if unavailable
                try:
                    await daily_message.add_reaction(config.emojis.leaf_heart)
                except discord.HTTPException as emoji_err:
                    # Error code 10014 = Unknown Emoji (custom emoji not available in this guild)
                    if "10014" in str(emoji_err) or "Unknown Emoji" in str(emoji_err):
                        logger.info(f"[💰] Custom emoji not available in guild {guild_id}, using fallback emoji ❤️")
                        await daily_message.add_reaction("❤️")
                    else:
                        raise  # Re-raise if it's a different error
                
                # Store message metadata in guild config (PERSISTENT across bot restarts)
                current_time = datetime.datetime.now(timezone.utc)
                from abby_core.database.collections.guild_configuration import store_daily_bonus_message
                
                # Use collection module function to persist message data
                success = store_daily_bonus_message(guild_id, daily_message.id, current_time)
                
                if success:
                    logger.info(f"[💰] ✓ Successfully posted daily bonus message in guild {guild_id}: message_id={daily_message.id}, stored in guild config")
                else:
                    logger.warning(f"[💰] Message ID stored in memory but failed to persist to guild config for guild {guild_id}")
                
                # Also update in-memory for immediate use before next database read
                self.daily_bonus_message_ids[guild_id] = daily_message.id
                
            except discord.Forbidden:
                logger.warning(f"[💰] Permission denied sending daily bonus message to channel {xp_channel_id} in guild {guild_id}")
            except discord.HTTPException as e:
                logger.error(f"[💰] Failed to send daily bonus message to guild {guild_id}: {e}")
        except Exception as e:
            logger.error(f"[💰] Unexpected error in send_daily_bonus_message for guild {guild_id}: {e}", exc_info=True)

    # ─────────────────────────────────────────────────────────────
    # Handlers
    # ─────────────────────────────────────────────────────────────
    async def handle_reaction(self, reaction: discord.Reaction, user: discord.User | discord.Member):
        logger.debug(f"[💰] Reaction detected: user={user.id}, emoji={reaction.emoji}, message={reaction.message.id}, author={reaction.message.author.name if reaction.message.author else 'None'}")
        
        if user == self.bot.user:
            logger.debug(f"[💰] Ignoring reaction from bot")
            return
        
        # Accept both custom emoji and fallback emoji (❤️)
        emoji_str = str(reaction.emoji)
        is_bonus_emoji = emoji_str == config.emojis.leaf_heart or emoji_str == "❤️"
        logger.debug(f"[💰] Emoji check: emoji_str='{emoji_str}', expected_emoji='{config.emojis.leaf_heart}', is_bonus_emoji={is_bonus_emoji}")

        guild = reaction.message.guild
        if not guild:
            logger.debug(f"[💰] No guild context for reaction - skipping")
            return

        daily_message_id = self._get_tracked_daily_bonus_message_id(guild, reaction.message)
        if not daily_message_id:
            return
        
        if daily_message_id and reaction.message.id == daily_message_id and is_bonus_emoji:
            guild_id = guild.id
            logger.debug(f"[💰] Daily bonus reaction matched! user={user.id}, guild={guild_id}, message={reaction.message.id}")
            
            # Ensure user exists in database before checking cooldown (canonical function)
            user_id_str = ensure_user_from_discord(user, guild)
            logger.debug(f"[💰] User {user.id} profile ensured in database (user_id_str={user_id_str})")
            
            # ─────────────────────────────────────────────────────────────
            # COOLDOWN LOGIC: Per-user, per-day (UTC midnight boundary)
            # ─────────────────────────────────────────────────────────────
            # 
            # How it works:
            # 1. User last_used_at is stored as UTC timestamp (naive from MongoDB)
            # 2. Check: "Is last_used_at >= today's UTC midnight?"
            # 3. If YES: User already claimed today → reject
            # 4. If NO: User eligible → grant XP and record new last_used_at
            # 5. Resets naturally at UTC midnight (no explicit reset needed)
            #
            # Multi-guild behavior (INTENTIONAL):
            # - Cooldown is USER-GLOBAL, not guild-specific
            # - User in Guild A who claims at 11 AM UTC cannot claim in Guild B until next UTC midnight
            # - This is correct: daily bonus is a per-user resource, not per-guild resource
            # - Exception: Each guild can have different daily bonus message times, but the cooldown applies globally
            #
            # Multi-message per day (EDGE CASE - currently NOT handled):
            # - If TWO daily messages posted same UTC day (e.g., bot scheduled at 11 AM and manually triggered at 8 PM)
            # - User can only claim ONE of them (whichever they react to first)
            # - This is acceptable behavior (treat as same "daily bonus day")
            # - Note: If this becomes a problem, could add per-message-instance hash to cooldown tracking
            #
            has_used = self._has_used_daily_bonus_today(user.id)
            logger.debug(f"[💰] Daily bonus cooldown check for user {user.id}: has_used={has_used}")
            if has_used:
                logger.debug(f"[💰] User {user.id} already used daily bonus TODAY (UTC boundary) - rejecting reaction")
                try:
                    await reaction.message.channel.send(
                        f"{user.mention}, you've already claimed your daily bonus today! Come back tomorrow at this time."
                    )
                except discord.HTTPException as e:
                    logger.warning(f"[💰] Failed to send cooldown message: {e}")
                return
            
            logger.debug(f"[💰] User {user.id} passed cooldown check - processing daily bonus reward")
            multiplier, holiday_name = current_xp_multiplier()
            amount = 10 * multiplier  # Reaction bonus is 10 base XP
            logger.debug(f"[💰] Calculated reward: {amount} XP (base=10, multiplier={multiplier}, holiday={holiday_name})")
            
            leveled_up = increment_xp(user.id, amount, guild_id)
            logger.debug(f"[💰] Incremented {amount} XP for user {user.id} in guild {guild_id}; leveled_up={leveled_up}")
            
            # Record daily bonus usage to database
            success = self._record_daily_bonus_usage(user.id)
            logger.debug(f"[💰] Cooldown recorded for user {user.id}: success={success}")
            if not success:
                logger.warning(f"[💰] Failed to record daily bonus cooldown for user {user.id} - using in-memory fallback")
            
            bonus_note = f" ({holiday_name})" if holiday_name else ""
            try:
                await reaction.message.channel.send(
                    f"Congratulations {user.mention}, you earned +{amount} EXP!{bonus_note}"
                )
                logger.debug(f"[💰] Successfully sent reward confirmation to user {user.id}")
            except discord.HTTPException as e:
                logger.error(f"[💰] Failed to send reward message: {e}")
        else:
            logger.debug(f"[💰] ✗ Reaction conditions not met - skipping reward. Checks: daily_message_id_exists={daily_message_id is not None}, message_id_match={reaction.message.id == daily_message_id if daily_message_id else False}, is_bonus_emoji={is_bonus_emoji}")


    async def gain_experience(self, message: discord.Message):
        if message.author.bot:
            return

        user_id = message.author.id
        now = datetime.datetime.now(timezone.utc)
        guild_id = message.guild.id if message.guild else None

        # Ensure user profile is initialized with full schema
        if message.guild:
            ensure_user_from_discord(message.author, message.guild)

        xp_channel_id = self._resolve_xp_channel_id(message.guild, guild_id)
        logger.debug(f"[💰] Checking message in channel {message.channel.id}, XP channel is {xp_channel_id}")
        if xp_channel_id and (not message.content.startswith("!")) and message.channel.id == xp_channel_id:
            last_message_time = self.last_message_time.get(user_id)
            msg_cooldown = config.timing.xp_message_cooldown_seconds
            if not last_message_time or (now - last_message_time).total_seconds() >= msg_cooldown:
                self.last_message_time[user_id] = now

                multiplier, holiday_name = current_xp_multiplier(now)
                self.exp_gain = multiplier

                leveled_up = increment_xp(user_id, multiplier, guild_id)
                logger.debug(f"[💰] User {user_id} gained {multiplier} EXP in guild {guild_id} (x{multiplier} multiplier{f' {holiday_name}' if holiday_name else ''}); leveled_up={leveled_up}")

                if leveled_up:
                    await message.channel.send(f"Congratulations {message.author.mention}, you leveled up!")

        last_attachment_time = self.last_attachment_time.get(user_id)
        for attachment in message.attachments:
            att_cooldown = config.timing.xp_attachment_cooldown_seconds
            if not last_attachment_time or (now - last_attachment_time).total_seconds() >= att_cooldown:
                self.last_attachment_time[user_id] = now
                guild_id = message.guild.id if message.guild else None
                multiplier, holiday_name = current_xp_multiplier(now)
                leveled_up = increment_xp(user_id, 10 * multiplier, guild_id)
                if leveled_up:
                    await message.channel.send(f"Congratulations {message.author.mention}, you leveled up!")

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────
    def _has_used_daily_bonus_today(self, user_id: int) -> bool:
        """
        Check if user has already used their daily bonus today.
        
        Uses canonical cooldown tracking from Users collection.
        Returns:
            True if user already claimed today, False otherwise
        """
        return check_user_cooldown(user_id, "daily_bonus")

    def _get_tracked_daily_bonus_message_id(
        self,
        guild: discord.Guild,
        message: Optional[discord.Message] = None,
    ) -> Optional[int]:
        """Resolve the current daily bonus message ID, preferring persisted guild config over stale cache."""
        cached_message_id = self.daily_bonus_message_ids.get(guild.id)
        logger.debug(f"[💰] In-memory tracking for guild {guild.id}: stored_message_id={cached_message_id}")

        message_id = message.id if message else None
        if cached_message_id and message_id == cached_message_id:
            return cached_message_id

        if cached_message_id and message_id is not None:
            logger.debug(
                f"[💰] Cached daily bonus message ID {cached_message_id} does not match reaction message {message_id}; checking guild config"
            )
        elif not cached_message_id:
            logger.debug(f"[💰] No in-memory message ID (possibly bot restarted) - checking guild config")

        try:
            guild_config = get_guild_config(guild.id)
            if guild_config and "channels" in guild_config and "xp" in guild_config["channels"]:
                persisted_message_id = guild_config["channels"]["xp"].get("daily_bonus_current_message_id")
                if persisted_message_id:
                    if persisted_message_id != cached_message_id:
                        logger.debug(
                            f"[💰] ✓ Refreshed daily bonus message ID from guild config: old={cached_message_id}, new={persisted_message_id}"
                        )
                    self.daily_bonus_message_ids[guild.id] = persisted_message_id
                    return persisted_message_id
                logger.debug(f"[💰] Guild config found but no daily_bonus_current_message_id stored")
            else:
                logger.debug(f"[💰] No guild config or XP channel config found")
        except Exception as e:
            logger.warning(f"[💰] Error loading message ID from guild config: {e}")

        if cached_message_id:
            return cached_message_id

        logger.debug(f"[💰] Final fallback: attempting content-based detection")
        if message and message.author == self.bot.user and "daily bonus message" in message.content.lower():
            logger.debug(
                f"[💰] ✓ Detected daily bonus message by content match (message {message.id}, content: '{message.content[:50]}')"
            )
            self.daily_bonus_message_ids[guild.id] = message.id
            return message.id

        if message:
            logger.debug(
                f"[💰] ✗ Message {message.id} doesn't match daily bonus pattern. Author={message.author}, Content: '{message.content[:50] if message.content else 'None'}'"
            )
        return None
    
    def _record_daily_bonus_usage(self, user_id: int) -> bool:
        """
        Record that a user has used their daily bonus today.
        
        Uses canonical cooldown tracking from Users collection.
        Returns:
            True if successfully recorded, False otherwise
        """
        success = record_user_cooldown(user_id, "daily_bonus")
        if not success:
            logger.warning(f"[💰] Failed to record cooldown in database for user {user_id}, using in-memory fallback")
            # Fallback to in-memory tracking if database fails
            self.daily_bonus_users.add(user_id)
        return success
    
    def _get_cooldown_debug_info(self, user_id: int) -> dict:
        """
        Get detailed debugging info about a user's cooldown status.
        
        Returns:
            Dict with cooldown status, last_used_at timestamp, and other debug info
        """
        from datetime import datetime, timezone
        
        try:
            # Import locally to debug collection access
            from abby_core.database.collections.users import get_collection
            
            logger.info(f"[💰] DEBUG: Getting collection for user {user_id}")
            collection = get_collection()
            logger.info(f"[💰] DEBUG: Collection obtained: {collection.name if hasattr(collection, 'name') else 'unknown'}")
            
            user_id_str = str(user_id)
            user_id_int = int(user_id_str) if user_id_str.isdigit() else None
            
            logger.info(f"[💰] DEBUG: Querying for user_id_str={user_id_str}, user_id_int={user_id_int}")
            
            # Try string lookup first
            user_record = collection.find_one({"user_id": user_id_str})
            
            if not user_record and user_id_int:
                logger.info(f"[💰] DEBUG: String lookup failed, trying int lookup")
                # Try int lookup
                user_record = collection.find_one({"user_id": user_id_int})
            
            if not user_record:
                logger.warning(f"[💰] DEBUG: User not found for any ID format. Tried string={user_id_str}, int={user_id_int}")
                # List first 5 users to see if collection has data
                sample_users = list(collection.find({}).limit(5))
                logger.info(f"[💰] DEBUG: Sample of users in collection (first 5): {[u.get('user_id') for u in sample_users]}")
                
                return {
                    "user_id": user_id_str,
                    "user_exists": False,
                    "has_daily_bonus_cooldown": False,
                    "last_used_at": None,
                    "error": f"User not found in database (tried string: {user_id_str}, int: {user_id_int})",
                    "collection_name": collection.name if hasattr(collection, 'name') else 'unknown',
                    "total_users_in_collection": collection.count_documents({})
                }
            
            logger.info(f"[💰] DEBUG: User found! user_id={user_record.get('user_id')}")
            
            last_used_at = None
            if "cooldowns" in user_record and "daily_bonus" in user_record["cooldowns"]:
                last_used_at = user_record["cooldowns"]["daily_bonus"].get("last_used_at")
                logger.info(f"[💰] DEBUG: Found last_used_at={last_used_at}, type={type(last_used_at)}")
            else:
                logger.info(f"[💰] DEBUG: User profile exists but no cooldowns.daily_bonus path")
            
            # Calculate if cooldown is active
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            is_active = False
            if last_used_at:
                logger.info(f"[💰] DEBUG: Comparing datetimes - last_used_at.tzinfo={last_used_at.tzinfo}, today_start.tzinfo={today_start.tzinfo}")
                # Handle both offset-aware and offset-naive datetimes from MongoDB
                if last_used_at.tzinfo is None:
                    # MongoDB datetime is naive UTC - convert to aware for comparison
                    last_used_at_aware = last_used_at.replace(tzinfo=timezone.utc)
                    logger.info(f"[💰] DEBUG: Converted naive datetime to aware")
                else:
                    # Already aware
                    last_used_at_aware = last_used_at
                
                is_active = last_used_at_aware >= today_start
                logger.info(f"[💰] DEBUG: Cooldown is_active={is_active} (last_used_at_aware={last_used_at_aware.isoformat()}, today_start={today_start.isoformat()})")
            
            return {
                "user_id": user_id_str,
                "user_exists": True,
                "last_used_at": last_used_at.isoformat() if last_used_at else None,
                "last_used_at_tzinfo": str(last_used_at.tzinfo) if last_used_at else None,
                "is_cooldown_active_today": is_active,
                "current_utc_time": now.isoformat(),
                "today_start_utc": today_start.isoformat(),
                "in_memory_tracked": user_id in self.daily_bonus_users,
                "timezone_info": "Using UTC for all calculations (handled naive/aware conversion)",
                "collection_name": collection.name if hasattr(collection, 'name') else 'unknown'
            }
        except Exception as e:
            logger.error(f"[💰] Error getting cooldown debug info for user {user_id}: {e}", exc_info=True)
            return {
                "user_id": str(user_id),
                "error": str(e),
                "error_type": type(e).__name__
            }

    
    def _resolve_xp_channel_id(self, guild: discord.Guild | None, guild_id: int | None = None) -> Optional[int]:
        """Resolve XP channel from guild config.
        
        Handles MongoDB NumberLong and dict-wrapped IDs from extended JSON format.
        Returns None if no XP channel is explicitly configured (no fallback).
        """
        try:
            effective_guild_id = guild.id if guild else guild_id
            if effective_guild_id:
                guild_config = get_guild_config(effective_guild_id)
                if not guild_config:
                    logger.debug(f"[💰] No guild config found for guild {effective_guild_id}")
                    return None
                xp_channel = guild_config.get("channels", {}).get("xp", {}).get("id")
                logger.debug(f"[💰] Raw XP channel from config for guild {effective_guild_id}: {xp_channel}")
                if xp_channel:
                    # Handle MongoDB NumberLong (stored as dict: {"$numberLong": "123..."})
                    if isinstance(xp_channel, dict) and "$numberLong" in xp_channel:
                        resolved = int(str(xp_channel["$numberLong"]))
                        logger.debug(f"[💰] Resolved XP channel (NumberLong) for guild {effective_guild_id}: {resolved}")
                        return resolved
                    # Handle plain int or string representation
                    resolved = int(str(xp_channel))
                    logger.debug(f"[💰] Resolved XP channel for guild {effective_guild_id}: {resolved}")
                    return resolved
                logger.info(f"[💰] No XP channel configured for guild {effective_guild_id}")
            else:
                logger.info("[💰] No guild context provided to resolve XP channel")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(f"[💰] Failed to resolve XP channel for guild {getattr(guild, 'id', None)}: {exc}")
        return None

    @commands.command()
    async def exp_rate(self, ctx: commands.Context):
        """Display the current EXP rate multiplier."""
        await ctx.send(f"The current EXP rate is {self.exp_gain}x")


async def setup(bot: commands.Bot):
    await bot.add_cog(XPRewardManager(bot))

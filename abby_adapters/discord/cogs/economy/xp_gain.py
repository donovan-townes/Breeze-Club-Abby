import datetime
import os
from abby_core.economy.xp import increment_xp
from abby_core.observability.logging import logging, log_startup_phase, STARTUP_PHASES
from abby_adapters.discord.config import BotConfig
import asyncio
from discord.ext import tasks,commands

logger = logging.getLogger(__name__)
config = BotConfig()

class ExperienceGainManager(commands.Cog):
    def __init__(self, bot):
        # Rest of your initialisation here
        self.bot = bot
        self.daily_message_channel_id = config.channels.xp_channel or config.channels.breeze_lounge
        self.abby_chat_id = config.channels.xp_abby_chat or config.channels.abby_chat
        self.daily_message = None
        self.daily_bonus_users = set()  # keep track of users who got the bonus
        self.last_attachment_time = {}
        self.last_message_time = {}
        self.streaming_users = set()
        self.exp_gain = 1
        self.logger = logging.getLogger(__name__) # Get the logger for this file
    

    @commands.Cog.listener()
    async def on_ready(self):
        logger.debug(f"[💰] Experience Gain Manager ready")
        self.run_tasks()

    def run_tasks(self):
        if not self.daily_task.is_running():    
            self.daily_task.start()
        if not self.check_streaming.is_running():
            self.check_streaming.start()
        logger.debug(f"[💰] Experience tasks started")   



    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        await self.handle_reaction(reaction, user)

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.gain_experience(message)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:    
            if after.self_stream and not before.self_stream:
                logger.info(f"[💰] {member} is streaming (+1exp/min)")
                self.streaming_users.add(member.id)
            elif before.self_stream and not after.self_stream:
                logger.info(f"[💰] {member} stopped streaming")
                self.streaming_users.discard(member.id)
            elif before.channel and not after.channel:
                logger.info(f"[💰] {member} disconnected from voice")
                if before.self_stream:
                    logger.info(f"[💰] {member} stopped streaming")
                    self.streaming_users.discard(member.id)
        except AttributeError:
            logger.warning(f"[💰] Attribute 'self_stream' not found in VoiceState object for {member}")
   
    @tasks.loop(minutes=config.timing.xp_stream_interval_minutes)
    async def check_streaming(self):
        # logger.info(f"[💰] Checking streaming users")
        for member in list(self.streaming_users):
            # Get guild_id from member (need to fetch member object from bot)
            guild = self.bot.guilds[0] if self.bot.guilds else None
            guild_id = guild.id if guild else None
            increment_xp(member.id if hasattr(member, 'id') else member, 5, guild_id)

    @tasks.loop(hours=24)
    async def daily_task(self):
        logger.info(f"[💰] Sending daily bonus message")
        channel = self.bot.get_channel(self.daily_message_channel_id)
        if not channel:
            logger.warning("[💰] XP_CHANNEL_ID not set or channel not found; skipping daily bonus message")
            return

        self.daily_message = await channel.send("Here is the daily bonus message, react to earn +5 EXP!")
        await self.daily_message.add_reaction(config.emojis.leaf_heart)
        self.daily_bonus_users = set()  # clear the list for the new message

    @daily_task.before_loop
    async def before_daily_task(self):
        await self.bot.wait_until_ready()  # wait until the bot logs in

        now = datetime.datetime.now()
        daily_start_hour = config.timing.xp_daily_start_hour
        if now.hour < daily_start_hour:
            wait_time = daily_start_hour - now.hour
        else:
            wait_time = 24 - (now.hour - daily_start_hour)

        log_startup_phase(logger, STARTUP_PHASES["BACKGROUND_TASKS"],
            f"[💰] Experience system scheduled (bonus: {wait_time}h, stream check: {config.timing.xp_stream_interval_minutes}m)")

        await asyncio.sleep(wait_time * 60 * 60)  # sleep until 5AM

    async def handle_reaction(self, reaction, user):
        # Check if the user is the bot
        if user == self.bot.user:
            return
        # Check if the reaction is on the daily message and is the custom emoji
        if self.daily_message and reaction.message.id == self.daily_message.id and str(reaction.emoji) == config.emojis.leaf_heart:
            logger.info("Handling Reaction")
            # Check if the user has already received the bonus
            if user.id not in self.daily_bonus_users:
                guild_id = reaction.message.guild.id if reaction.message.guild else None
                increment_xp(user.id, 5, guild_id)  # increment the user's xp
                await reaction.message.channel.send(f"Congratulations {user.mention}, you earned +5 EXP!")
                # mark the user as having received the bonus
                self.daily_bonus_users.add(user.id)

    async def gain_experience(self, message):
        # logger.info("Checking if user is gaining EXP")
        user_id = message.author.id
        now = datetime.datetime.now()

        # Check if the message is not a command and is in a certain channel
        # Ignore commands
        if message.author.bot:
            return
        
        breeze_lounge_id = config.channels.xp_channel or config.channels.breeze_lounge
        if breeze_lounge_id and (not message.content.startswith('!')) and message.channel.id == breeze_lounge_id:
            # logger.info("[💰] USER typed in correct channel")
            # Check if the user has sent a message in the last minute
            last_message_time = self.last_message_time.get(user_id)
            msg_cooldown = config.timing.xp_message_cooldown_seconds
            if not last_message_time or (now - last_message_time).total_seconds() >= msg_cooldown:
                # Update the last message time and increment the user's experience
                self.last_message_time[user_id] = now
                
                # Check if it's a weekend (Saturday or Sunday)
                is_weekend = now.weekday() in [5, 6]  # Saturday is 5, Sunday is 6
                # logger.info(f"[💰] Is weekend: {is_weekend}")
                

                # List of major US holidays with date and name
                holidays = [
                    (datetime.date(now.year, 1, 1), "New Year's Day"),
                    (datetime.date(now.year, 1, 18), "Martin Luther King Jr. Day"),
                    (datetime.date(now.year, 2, 20), "Presidents' Day"),
                    (datetime.date(now.year, 5, 30), "Memorial Day"),
                    (datetime.date(now.year, 7, 4), "Independence Day"),
                    (datetime.date(now.year, 9, 4), "Labor Day"),
                    (datetime.date(now.year, 10, 10), "Columbus Day"),
                    (datetime.date(now.year, 11, 11), "Veterans Day"),
                    (datetime.date(now.year, 11, 24), "Thanksgiving Day"),
                    (datetime.date(now.year, 12, 25), "Christmas Day"),
                    # Add more holidays here if needed...
                ]

                is_holiday = now.date() in [date for date, name in holidays]

                # logger.info(f"[💰] Is holiday: {is_holiday}")

                # Apply double experience gains on weekends and holidays
                # Apply triple experience gains on weekends and holiday (same time)
                xp_gain = 3 if is_weekend and is_holiday else (2 if is_weekend or is_holiday else 1)
                # logger.info(f"[💰] XP Gain: {xp_gain}")
                self.exp_gain = xp_gain

                guild_id = message.guild.id if message.guild else None
                leveled_up = increment_xp(user_id, xp_gain, guild_id)
                # logger.info(f"Leveled up variable: {leveled_up}")
                logger.info(f"[💰] User gained {xp_gain} EXP")

                # Print the name of the holiday if it is detected
                if is_holiday:
                    holiday_name = next(name for date, name in holidays if date == now.date())
                    # logger.info(f"[💰] It's {holiday_name}!")

                if leveled_up:
                    # logger.info("SEND MESSAGE IN DISCORD USER LEVELED UP!")
                    await message.channel.send(
                        f"Congratulations {message.author.mention}, you leveled up!")

        # Check for attachments independently of messages
        last_attachment_time = self.last_attachment_time.get(user_id)
        for attachment in message.attachments:
            att_cooldown = config.timing.xp_attachment_cooldown_seconds
            if not last_attachment_time or (now - last_attachment_time).total_seconds() >= att_cooldown:
                # Check if the attachment is an MP3 file
                if attachment.content_type == 'audio/mpeg':
                    logger.info("[💰] User sent an MP3 file")
                # Check if the attachment is an image file
                elif 'image' in attachment.content_type:
                    logger.info("[💰] User sent an image file")
                self.last_attachment_time[user_id] = now
                guild_id = message.guild.id if message.guild else None
                leveled_up = increment_xp(user_id, 10, guild_id)
                if leveled_up:
                    await message.channel.send(
                        f"Congratulations {message.author.mention}, you leveled up!")



    @commands.command()
    async def exp_rate(self, ctx):
        """Displays the current EXP rate"""
        await ctx.send(f"The current EXP rate is {self.exp_gain}x")


async def setup(bot):
    await bot.add_cog(ExperienceGainManager(bot))
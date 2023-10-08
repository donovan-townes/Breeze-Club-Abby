import datetime
from Exp.xp_handler import increment_xp
from utils.log_config import setup_logging, logging
import asyncio
from discord.ext import tasks,commands


setup_logging()
logger = logging.getLogger(__name__)

ABBY_CHAT = 1103490012500201632
BREEZE_LOUNGE = 802512963519905852

class ExperienceGainManager(commands.Cog):
    def __init__(self, bot):
        # Rest of your initialisation here
        self.bot = bot
        self.daily_message_channel_id = BREEZE_LOUNGE
        self.daily_message = None
        self.daily_bonus_users = set()  # keep track of users who got the bonus
        self.last_attachment_time = {}
        self.last_message_time = {}
        self.streaming_users = set()
        self.exp_gain = 1
        self.logger = logging.getLogger(__name__) # Get the logger for this file
    

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"[💰] Experience Gain Manager ready")
        self.run_tasks()

    def run_tasks(self):    
        self.daily_task.start()
        self.check_streaming.start()
        logger.info(f"[💰] Experence Tasks Started")   



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
   
    @tasks.loop(minutes=5)
    async def check_streaming(self):
        # logger.info(f"[💰] Checking streaming users")
        for user_id in self.streaming_users:
            increment_xp(user_id, 5)

    @tasks.loop(hours=24)
    async def daily_task(self):
        logger.info(f"[💰] Sending daily bonus message")
        channel = self.bot.get_channel(self.daily_message_channel_id)
        self.daily_message = await channel.send("Here is the daily bonus message, react to earn +5 EXP!")
        await self.daily_message.add_reaction('<a:z8_leafheart_excited:806057904431693824>')
        self.daily_bonus_users = set()  # clear the list for the new message

    @daily_task.before_loop
    async def before_daily_task(self):
        await self.bot.wait_until_ready()  # wait until the bot logs in

        now = datetime.datetime.now()
        if now.hour < 5:  # if it's before 5AM
            wait_time = 5 - now.hour
        else:  # if it's past 5AM
            wait_time = 24 - (now.hour - 5)

        logger.info(
            f"[💰] ExperienceGainManager initialized. Next bonus message in {wait_time} hours.")
        logger.info(
            f"[💰] Stream Check initialized. Check is every [5] Minutes")

        await asyncio.sleep(wait_time * 60 * 60)  # sleep until 5AM

    async def handle_reaction(self, reaction, user):
        # Check if the user is the bot
        if user == self.bot.user:
            return
        # Check if the reaction is on the daily message and is the custom emoji
        if self.daily_message and reaction.message.id == self.daily_message.id and str(reaction.emoji) == '<a:z8_leafheart_excited:806057904431693824>':
            logger.info("Handling Reaction")
            # Check if the user has already received the bonus
            if user.id not in self.daily_bonus_users:
                increment_xp(user.id, 5)  # increment the user's xp
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
        
        if not message.content.startswith('!') and message.channel.id == BREEZE_LOUNGE:
            # logger.info("[💰] USER typed in correct channel")
            # Check if the user has sent a message in the last minute
            last_message_time = self.last_message_time.get(user_id)
            if not last_message_time or (now - last_message_time).total_seconds() >= 60:
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

                leveled_up = increment_xp(user_id, xp_gain)
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
            if not last_attachment_time or (now - last_attachment_time).total_seconds() >= 10 * 60:
                # Check if the attachment is an MP3 file
                if attachment.content_type == 'audio/mpeg':
                    logger.info("[💰] User sent an MP3 file")
                # Check if the attachment is an image file
                elif 'image' in attachment.content_type:
                    logger.info("[💰] User sent an image file")
                self.last_attachment_time[user_id] = now
                leveled_up = increment_xp(user_id, 10)
                if leveled_up:
                    await message.channel.send(
                        f"Congratulations {message.author.mention}, you leveled up!")



    @commands.command()
    async def exp_rate(self, ctx):
        """Displays the current EXP rate"""
        await ctx.send(f"The current EXP rate is {self.exp_gain}x")


async def setup(bot):
    await bot.add_cog(ExperienceGainManager(bot))
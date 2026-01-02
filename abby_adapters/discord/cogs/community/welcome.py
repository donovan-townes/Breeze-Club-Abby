import discord
from discord import Embed
from discord.ext import commands
import openai
import random
import asyncio

from abby_core.observability.logging import logging, log_startup_phase, STARTUP_PHASES
from abby_adapters.discord.config import BotConfig

logger = logging.getLogger(__name__)

# Load configuration
config = BotConfig()
openai.api_key = config.api.openai_key

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.phrases = config.load_welcome_phrases()
        logger.debug(f"[👋] Loaded {len(self.phrases)} welcome phrases")

    # GPT Call
    def generate_message(self, prompt):
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"{prompt}"},
            ],
            max_tokens=300
        )
        return response.choices[0].message['content']
    

    @commands.Cog.listener()
    async def on_ready(self):
        log_startup_phase(logger, STARTUP_PHASES["BACKGROUND_TASKS"], f"[👋] Welcome scheduler ready")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        await asyncio.sleep(60) # Wait for 60 sec
        await self.welcome_new_member(member)


    async def welcome_new_member(self, member):
        logger.info("[👋] Welcoming new member!")
        guild = member.guild
        channel = guild.get_channel(config.channels.gust_channel)

        heart = config.emojis.leaf_heart
        breeze_lounge = f"<#{config.channels.breeze_lounge}>"
        welcome_leaf = f"<#{config.channels.welcome_leaf}>"

        prompt = f"""
        I'm Abby, virtual assistant for the Breeze Club Discord, I will generate a welcome message for a new member in the server on the behalf of Z8phyR, our server owner and musician. I'll make sure to include a warm creative welcome, a reminder to check the leaf of rules in {welcome_leaf} channel and introduce themselves at the {breeze_lounge}, and an encouragement to join in the conversations. I won't forget to add some bunny charm! 🐰🥕🌳
        They have selected these roles:
        """

        # Check roles using config
        role_ids = [role.id for role in member.roles]
        logger.info(f"[👋] Role IDs for new member: {role_ids}")
        user_roles = []

        if config.roles.musician in role_ids:
            user_roles.append('musician')
        if config.roles.streamer in role_ids:
            user_roles.append('streamer')
        if config.roles.gamer in role_ids:
            user_roles.append('gamer')
        if config.roles.developer in role_ids:
            user_roles.append('developer')
        if config.roles.artist in role_ids:
            user_roles.append('artist')
        if config.roles.nft_artist in role_ids:
            user_roles.append('NFT artist')
        if config.roles.writer in role_ids:
            user_roles.append('writer')
        if config.roles.z8phyr_fan in role_ids:
            user_roles.append(' a big fan of Z8phyR!')

        if user_roles:
            prompt += ' ' + ' '.join(user_roles)
        logger.info(f"[👋] User roles selected: {user_roles}")

        message_content = self.generate_message(prompt)
        await channel.send(f"**Attention <@&{config.channels.breeze_fam_role}>**")
        embed = Embed(
            title=f"{heart} **Welcome our newest member!** {heart}",
            description=f"Kind greetings, {member.mention}! {heart} \n{message_content}",
            color=0x00ff00
        )
        # Add a line above the description
        embed.set_author(name="The Winds brings another to the Breeze Club!")

        # Add a line below the description
        random_phrase = random.choice(self.phrases)
        embed.set_footer(text=f"🍃 {random_phrase}")

        message = await channel.send(embed=embed)
        await message.add_reaction(heart)

async def setup(bot):
    await bot.add_cog(Welcome(bot))



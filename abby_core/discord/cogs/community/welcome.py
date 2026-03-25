import discord
from discord import Embed
from discord.ext import commands
import random
import asyncio

from tdos_intelligence.observability import logging
from tdos_intelligence.llm import LLMClient
from abby_core.observability.logging import log_startup_phase, STARTUP_PHASES
from abby_core.discord.config import BotConfig
from abby_core.llm.context_factory import build_conversation_context
from abby_core.personality.manager import get_personality_manager

logger = logging.getLogger(__name__)

# Load configuration
config = BotConfig()

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.phrases = config.load_welcome_phrases()
        self.llm_client = LLMClient()
        self.personality_manager = get_personality_manager()
        logger.debug(f"[👋] Loaded {len(self.phrases)} welcome phrases")

    # Generate welcome message using Abby's persona and LLM context
    async def generate_message(self, guild, member_roles: list[str]):
        """
        Generate a personalized welcome message using Abby's persona.
        
        Args:
            guild: Discord guild object
            member_roles: List of roles the member selected
        """
        try:
            # Build conversation context with Abby's persona
            context = build_conversation_context(
                user_id="0",  # Welcoming a new member, no specific user context needed
                guild_id=guild.id,
                guild_name=guild.name,
                user_name=None,
                user_level="guest",
                is_owner=False
            )
            
            # Construct the welcome prompt using Abby's system prompt
            roles_text = ', '.join(member_roles) if member_roles else "haven't selected any specific roles yet"
            
            # Prepare messages for LLM
            messages = [
                {"role": "system", "content": context.persona.system_message},
                {"role": "user", "content": f"Generate a warm, creative welcome message for a new member to the {guild.name} Discord.\nThey have selected these roles: {roles_text}\n\nYour message should:\n1. Include a warm creative welcome with personality\n2. Remind them to check the rules channel\n3. Encourage them to introduce themselves\n4. Invite them to join conversations\n5. Keep a friendly, welcoming tone with your characteristic charm\n\nKeep the message under 150 words."}
            ]

            # Call LLM with Abby's system prompt and context (run in executor to avoid blocking)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.llm_client.chat(
                    messages=messages,
                    temperature=context.temperature,
                    max_tokens=300
                )
            )
            
            return response
        except Exception as e:
            logger.error(f"[👋] Error generating welcome message: {e}")
            # Fallback message
            return f"Welcome to {guild.name}! We're excited to have you here. Check the rules and introduce yourself!"
    

    @commands.Cog.listener()
    async def on_ready(self):
        logger.debug("[👋] Welcome scheduler ready")

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

        if not channel:
            logger.warning(f"[👋] Guest channel not found for guild {guild.id}")
            return

        heart = config.emojis.leaf_heart

        # Extract member roles
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
            user_roles.append('a big fan of Z8phyR!')

        logger.info(f"[👋] User roles selected: {user_roles}")

        # Generate welcome message using Abby's persona and LLM
        message_content = await self.generate_message(guild, user_roles)
        
        await channel.send(f"**Attention <@&{config.channels.breeze_fam_role}>**")
        embed = Embed(
            title=f"{heart} **Welcome our newest member!** {heart}",
            description=f"Kind greetings, {member.mention}! {heart} \n{message_content}",
            color=0x00ff00
        )
        # Add a line above the description
        embed.set_author(name=f"Welcome to {guild.name}!")

        # Add a line below the description
        random_phrase = random.choice(self.phrases)
        embed.set_footer(text=f"🍃 {random_phrase}")

        message = await channel.send(embed=embed)
        await message.add_reaction(heart)

async def setup(bot):
    await bot.add_cog(Welcome(bot))



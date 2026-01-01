from discord.ext import commands
from abby_core.observability.logging import setup_logging,logging
import discord
from abby_core.economy.xp import increment_xp, get_xp, initialize_xp, decrement_xp, reset_exp, get_level, get_level_from_xp, get_xp_required

setup_logging()
logger = logging.getLogger(__name__)

def exp_embed(message,progress,level,xp,xp_required):
    # Create a progress bar emoji based on the progress percentage
    progress_bar = ""
    for i in range(10):
        if progress >= (i+1) * 10:
            progress_bar += "🍃"  # Filled square
        else:
            progress_bar += "⬛"  # Empty square

    # Create a more modern and user-friendly embed
    embed = discord.Embed(
        title=f"{message.author}'s XP", 
        color=0x00ff00)
    
    # add embed "Current Level"
    embed.add_field(
        name="Current Level",
        value=f"Lvl. {level}",
        inline=True
    )

    # add embed "Current XP"
    embed.add_field(
        name="Current XP",
        value=f"{xp}/{xp_required} XP",
        inline=True
    )

    # add progress bar on the bottom
    embed.add_field(
        name="Progress",
        value=f"{progress_bar} {progress:.2f}%",
        inline=False
    )

    # # add thumbnail for the embed
    embed.set_thumbnail(
        url=message.author.avatar
    )

    # set footer
    embed.set_footer(
        text=f"Only {  get_xp_required(level+1)['xp_required'] - xp} XP more to level up to level {level+1}!",
        icon_url=message.author.avatar
    )
    return embed

class ExperienceManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"[➕] Experience Manager ready")

    @commands.command(name="exp", description="Check or handle experience related funcitons")
    async def exp(self, interaction: discord.Interaction):
        user = interaction.user
        user_exp = get_xp(user.id)
        user_level = get_level_from_xp(user)
        exp_required = get_xp_required(user_level + 1)['xp_required']
        try:
            prev_exp_required = get_xp_required(user_level)['xp_required']
        except:
            prev_exp_required = 0
        user_progress = ((user_exp - prev_exp_required) / (exp_required - prev_exp_required))
        embed = exp_embed(user, user_progress, user_level, user_exp, exp_required)
        await interaction.channel.send(embed=embed)


# async def setup(bot):
    # await bot.add_cog(ExperienceManager)
    pass

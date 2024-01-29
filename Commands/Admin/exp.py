from tqdm import tqdm
from pymongo import MongoClient
from Exp.xp_handler import increment_xp, get_xp, initialize_xp, decrement_xp, reset_exp, get_user_level, get_level_from_xp,get_xp_required
import discord
from discord.ext import commands
from discord.ext.commands import Group

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

# Set invoke_without_command to True
@commands.group(invoke_without_command=True)
@commands.cooldown(1, 5, commands.BucketType.user)
async def exp(message):
    xp = get_xp(message.author.id)
    level = get_level_from_xp(xp)
    xp_required = get_xp_required(level+1)['xp_required']
    try:
        prev_xp_required = get_xp_required(level)['xp_required']
    except:
        prev_xp_required = 0
    progress = ((xp-prev_xp_required) / (xp_required-prev_xp_required)) * 100
    embed = exp_embed(message,progress,level,xp,xp_required)
    await message.send(embed=embed)
  


@exp.command()
@commands.has_permissions(administrator=True)
async def init_xp_all(ctx):
    for member in ctx.guild.members:
        initialize_xp(member.id)

@commands.has_permissions(administrator=True)
@exp.command()
async def add(message, points: int, user: discord.Member = None):
    if user is None:
        user = message.author

    increment_xp(user.id, points)
    await message.send(f"You've incremented xp by {points} for {user.mention}")

@commands.has_permissions(administrator=True)
@exp.command()
async def sub(message, points: int):
    user = message.author.id
    decrement_xp(user, points)
    await message.send(f"You've decreased your xp by {points}")

@commands.has_permissions(administrator=True)
@exp.command()
async def reset(message, user: discord.Member = None):
    if user is None:
        user = message.author.id
    else:
        user = message.mention.id
    reset_exp(user)
    await message.send(f"You've reset your experience to 0 - congrats")

@exp.command()
async def level(message):
    user = message.author.id
    xp = get_xp(user)
    level = get_level_from_xp(xp)
    await message.send(f"Your level is {level}!")

@exp.error
async def exp_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f'Cooldown still active, please wait {error.retry_after:.0f} seconds.')


def setup(bot):
    bot.add_command(exp)

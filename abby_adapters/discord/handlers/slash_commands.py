from typing import Literal, Optional

import discord
from discord.ext import commands
# from handlers.command_loader import CommandHandler

BREEZE_CLUB = 547471286801268777

class SlashCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.commander = self.bot.command_handler


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
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
                msg = f"✅ **Guild Sync**: Synced {len(synced)} commands to **{ctx.guild.name}** (instant)"
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
                msg = f"✅ **Copy & Sync**: Synced {len(synced)} commands to **{ctx.guild.name}** (copied from global)"
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                msg = f"🧹 **Cleared**: Removed all commands from **{ctx.guild.name}** (use !sync ~ to restore)"
                synced = []
            else:
                synced = await ctx.bot.tree.sync()
                msg = f"🌍 **Global Sync**: Synced {len(synced)} commands globally (takes up to 1 hour)"

            embed = discord.Embed(
                title="🔄 Slash Command Sync",
                description=msg,
                color=discord.Color.green() if spec != "^" else discord.Color.orange()
            )
            embed.add_field(name="💡 Quick Help", value=
                "`!sync ~` - Guild only (fast)\n"
                "`!sync` - Global (slow)\n"
                "`!sync ^` - Clear commands", inline=False)
            await ctx.send(embed=embed)
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @commands.guild_only()
    @commands.is_owner()
    @commands.command(name="reload")
    async def reload(self,ctx):
        await ctx.send("Reloading cogs...")
        await self.commander.reload_cogs(ctx=ctx)

async def setup(bot : commands.Bot) -> None:
    await bot.add_cog(SlashCommands(bot))
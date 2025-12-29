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
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
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
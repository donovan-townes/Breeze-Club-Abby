import discord
from discord.ext import commands
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


class ReloadCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='reloadcog', aliases=['rc', 'reload_cog'])
    @commands.is_owner()
    async def reload_cog(self, ctx, *, cog_name: str = None):
        """Reload a specific cog or all cogs without restarting the bot
        
        Usage:
        !reloadcog chatbot          - Reload the chatbot cog
        !reloadcog Fun.giveaway     - Reload the giveaway cog
        !reloadcog all              - Reload all cogs
        """
        if not cog_name:
            await ctx.send("❌ Please specify a cog name or 'all'")
            return

        if cog_name.lower() == 'all':
            reloaded = []
            failed = []
            
            # Get list of all loaded extensions
            extensions = list(self.bot.extensions.keys())
            
            for ext in extensions:
                try:
                    await self.bot.reload_extension(ext)
                    reloaded.append(ext.split('.')[-1])
                except Exception as e:
                    failed.append(f"{ext.split('.')[-1]}: {str(e)[:50]}")
            
            embed = discord.Embed(
                title="🔄 Reload All Cogs",
                color=discord.Color.green() if not failed else discord.Color.orange()
            )
            
            if reloaded:
                embed.add_field(
                    name=f"✅ Reloaded ({len(reloaded)})",
                    value=", ".join(reloaded[:10]) + ("..." if len(reloaded) > 10 else ""),
                    inline=False
                )
            
            if failed:
                embed.add_field(
                    name=f"❌ Failed ({len(failed)})",
                    value="\n".join(failed[:5]),
                    inline=False
                )
            
            await ctx.send(embed=embed)
            logger.info(f"[🔄] Bulk reload: {len(reloaded)} success, {len(failed)} failed")
            
        else:
            # Try to find the cog in loaded extensions
            found = False
            for ext_name in self.bot.extensions.keys():
                if cog_name.lower() in ext_name.lower():
                    try:
                        await self.bot.reload_extension(ext_name)
                        embed = discord.Embed(
                            title="✅ Cog Reloaded",
                            description=f"Successfully reloaded `{ext_name.split('.')[-1]}`",
                            color=discord.Color.green()
                        )
                        await ctx.send(embed=embed)
                        logger.info(f"[🔄] Reloaded: {ext_name}")
                        found = True
                        break
                    except Exception as e:
                        embed = discord.Embed(
                            title="❌ Reload Failed",
                            description=f"Failed to reload `{ext_name}`\n```{str(e)[:200]}```",
                            color=discord.Color.red()
                        )
                        await ctx.send(embed=embed)
                        logger.error(f"[❌] Failed to reload {ext_name}: {e}")
                        found = True
                        break
            
            if not found:
                await ctx.send(f"❌ Cog `{cog_name}` not found in loaded extensions")

    @commands.command(name='loaded', aliases=['cogs', 'extensions'])
    @commands.is_owner()
    async def list_loaded(self, ctx):
        """List all currently loaded cogs/extensions"""
        extensions = [ext.split('.')[-1] for ext in self.bot.extensions.keys()]
        extensions.sort()
        
        # Split into chunks for better display
        chunk_size = 20
        chunks = [extensions[i:i + chunk_size] for i in range(0, len(extensions), chunk_size)]
        
        embed = discord.Embed(
            title=f"📦 Loaded Extensions ({len(extensions)})",
            color=discord.Color.blue()
        )
        
        for i, chunk in enumerate(chunks[:3]):  # Limit to 3 fields
            embed.add_field(
                name=f"Page {i+1}",
                value=", ".join(chunk),
                inline=False
            )
        
        if len(chunks) > 3:
            embed.set_footer(text=f"... and {len(extensions) - (chunk_size * 3)} more")
        
        await ctx.send(embed=embed)

    @reload_cog.error
    async def reload_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("❌ Only the bot owner can reload cogs!")


async def setup(bot):
    await bot.add_cog(ReloadCommands(bot))
    logger.info("[🔄] Reload commands loaded")

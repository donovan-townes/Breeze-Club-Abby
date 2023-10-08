from discord.ext import commands
import discord
from discord import app_commands



class ServerInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(name="info", description="Get information about the server",)
    async def info(self, interaction: discord.Interaction):
        guild = interaction.guild
        guild_id = guild.id
        guild_name = guild.name
        member_count = guild.member_count

        owner_id = guild.owner_id
        dev_id = 268871091550814209
        guild_owner = await guild.fetch_member(owner_id)

        # server icon
        icon_url = str(guild.icon.url) if guild.icon else None

        # server creation date (the "created_at" attribute gives a datetime object)
        creation_date = guild.created_at.strftime("%B %d, %Y")

        # create an Embed object
        embed = discord.Embed(
            title=guild_name,
            description="Server Information",
            color=0x00ff00
        )

        # add fields to the embed
        embed.add_field(name="Server ID", value=guild_id)
        embed.add_field(name="Member Count", value=member_count)
        embed.add_field(name="Server Owner", value=guild_owner.display_name)
        embed.add_field(name="Creation Date", value=creation_date)
        embed.add_field(name="Developed By", value=f"<@{owner_id}> & <@{dev_id}>")

        # set the server icon as the embed's thumbnail
        if icon_url:
            embed.set_thumbnail(url=icon_url)

        # send the embed to the channel where the command was used
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(ServerInfo(bot))

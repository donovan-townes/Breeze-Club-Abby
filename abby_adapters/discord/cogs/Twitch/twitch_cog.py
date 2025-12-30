import os
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from abby_core.utils.mongo_db import connect_to_mongodb
from abby_core.utils.log_config import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)

def _guild_settings_collection(db):
    return db["twitch_settings"]

class TwitchSettings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_db(self):
        client = connect_to_mongodb()
        return client[os.getenv("MONGODB_DB", "Abby")]  # unified DB default

    def _get_settings(self, guild_id: int) -> dict:
        db = self._get_db()
        col = _guild_settings_collection(db)
        doc = col.find_one({"guild_id": guild_id})
        return doc or {"guild_id": guild_id, "notify_enabled": False, "channel_id": None}

    def _set_settings(self, guild_id: int, updates: dict):
        db = self._get_db()
        col = _guild_settings_collection(db)
        col.update_one({"guild_id": guild_id}, {"$set": updates}, upsert=True)

    @app_commands.command(name="twitch_notify", description="Enable or disable Twitch live notifications for this server")
    @app_commands.describe(enable="Enable notifications (true/false)", channel="Channel to post notifications")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def twitch_notify(self, interaction: discord.Interaction, enable: bool, channel: Optional[discord.TextChannel] = None):
        guild_id = interaction.guild_id
        settings = self._get_settings(guild_id)
        channel_id = channel.id if channel else settings.get("channel_id")
        if enable and not channel_id:
            await interaction.response.send_message("Please specify a channel to post notifications.", ephemeral=True)
            return
        self._set_settings(guild_id, {"notify_enabled": enable, "channel_id": channel_id})
        await interaction.response.send_message(f"Twitch notifications {'enabled' if enable else 'disabled'}" + (f" in {channel.mention}" if channel else ""), ephemeral=True)

    @app_commands.command(name="twitch_link", description="Link a user's Discord to a Twitch handle")
    @app_commands.describe(user="Discord user", twitch_handle="Twitch username")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def twitch_link(self, interaction: discord.Interaction, user: discord.User, twitch_handle: str):
        db = self._get_db()
        col = db["user_links"]
        col.update_one({"user_id": str(user.id)}, {"$set": {"twitch_handle": twitch_handle}}, upsert=True)
        await interaction.response.send_message(f"Linked {user.mention} to Twitch handle '{twitch_handle}'.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TwitchSettings(bot))

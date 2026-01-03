import discord
from discord.ext import commands
from abby_core.observability.logging import logging
from abby_adapters.discord.config import BotConfig

logger = logging.getLogger(__name__)
config = BotConfig()

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Use centralized config for all settings
        self.enabled = config.features.image_auto_move_enabled if hasattr(config.features, 'image_auto_move_enabled') else False
        self.general_channel_id = config.channels.breeze_club_general
        self.memes_channel_id = config.channels.breeze_memes

    @commands.Cog.listener()
    async def on_ready(self):
        logger.debug("[🪪] Moderation cog ready (image auto-move=%s)" % ("on" if self.enabled else "off"))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not self.enabled:
            return

        # Only act if posted in configured general channel (optional)
        if self.general_channel_id and message.channel.id != self.general_channel_id:
            return

        if not message.attachments:
            return

        # Check for image attachments
        image_attachments = [a for a in message.attachments if (a.content_type or "").startswith("image/")]
        if not image_attachments:
            return

        if not self.memes_channel_id:
            logger.warning("[🪪] MEMES_CHANNEL_ID not set; cannot move images.")
            return

        memes_channel = self.bot.get_channel(self.memes_channel_id)
        if memes_channel is None:
            logger.warning("[🪪] Memes channel not found by ID: %s" % self.memes_channel_id)
            return

        try:
            files = [await a.to_file() for a in image_attachments]
            content = f"Moving image(s) from {message.channel.mention} by {message.author.mention}."
            await memes_channel.send(content=content, files=files)
            await message.reply("Heads up! Image posts belong in memes — moved it for you this time.")
            await message.delete()
            logger.info("[🪪] Moved %d image(s) from #%s to memes." % (len(files), message.channel.id))
        except Exception as e:
            logger.error(f"[🪪] Failed to move image: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))

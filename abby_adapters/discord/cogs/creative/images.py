import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from pathlib import Path
from typing import Optional, Tuple
from abby_core.observability.logging import logging
from abby_core.economy.xp import get_level
from abby_adapters.discord.config import BotConfig
import sys

# Ensure abby_core is in path
ABBY_ROOT = Path(__file__).parent.parent.parent.parent.parent
if str(ABBY_ROOT) not in sys.path:
    sys.path.insert(0, str(ABBY_ROOT))

config = BotConfig()

# Constants
DAY_SECONDS = 86400  # Clearer constant name for seconds in a day

# Create a mapping of style presets to their corresponding variables
style_presets = {
    "3d-model": "3d-model",
    "analog-film": "analog-film",
    "anime": "anime",
    "cinematic": "cinematic",
    "comic-book": "comic-book",
    "digital-art": "digital-art",
    "enhance": "enhance",
    "fantasy-art": "fantasy-art",
    "isometric": "isometric",
    "line-art": "line-art",
    "low-poly": "low-poly",
    "modeling-compound": "modeling-compound",
    "neon-punk": "neon-punk",
    "origami": "origami",
    "photographic": "photographic",
    "pixel-art": "pixel-art",
    "tile-texture": "tile-texture"
}

class ImageGenerate(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.message_id = None
        
        # Get references to shared services
        self.storage = bot.storage if hasattr(bot, 'storage') else None
        self.generator = bot.generator if hasattr(bot, 'generator') else None
        
        if not self.storage or not self.generator:
            self.logger.error("Storage or Generator services not available on bot instance")

    def _quota_context(self, interaction: discord.Interaction) -> Tuple[str, Optional[str], list[str], int]:
        """Extract quota-related context from interaction.
        
        Returns:
            Tuple of (user_id, guild_id, user_roles, user_level)
        """
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id) if interaction.guild else None
        user_roles = [str(role.id) for role in getattr(interaction.user, "roles", [])]
        try:
            user_level = get_level(user_id, guild_id)
        except Exception as e:
            self.logger.warning(f"Failed to get user level for {user_id}: {e}")
            user_level = 1
        return user_id, guild_id, user_roles, user_level



    async def generate_image(self, interaction: discord.Interaction, text: str, style_preset: str = "enhance"):
        """Generate an image from text using ImageGenerator and save with StorageManager."""
        if not self.storage or not self.generator:
            await interaction.followup.send("Image generation services are not available. Please try again later.", ephemeral=True)
            return
        
        user_id, guild_id, user_roles, user_level = self._quota_context(interaction)
        style_preset = style_preset.lower()
        if style_preset not in style_presets:
            style_preset = "enhance"
        
        # Check quota before generation
        has_quota, error_embed = await self._check_quota(interaction, user_id, guild_id, user_roles, user_level)
        if not has_quota:
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return
        
        # Generate image using service
        success, image_bytes, gen_msg = await self.generator.text_to_image(text, style_preset)
        if not success:
            embed = discord.Embed(
                title="Generation Failed",
                description=gen_msg,
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Save image with quota tracking
        saved, save_msg, image_path = self.storage.save_image(
            image_data=image_bytes,
            user_id=user_id,
            image_name=f"text_to_image_{interaction.id}.png",
            user_roles=user_roles,
            user_level=user_level,
            guild_id=guild_id,
        )
        
        if not saved:
            embed = discord.Embed(
                title="Storage Error",
                description=save_msg,
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Get updated quota status for display
        updated_quota = self.storage.get_quota_status(
            user_id,
            user_roles=user_roles,
            user_level=user_level,
            guild_id=guild_id,
        )
        daily_used = updated_quota['daily']['limit'] - updated_quota['daily']['remaining']
        storage_used = updated_quota['user']['used_mb']
        storage_limit = updated_quota['user']['limit_mb']
        
        # Create response with quota info
        file = discord.File(str(image_path), filename="image.png")
        view = ImageOptions(self, interaction, text, style_preset)
        
        embed = discord.Embed(
            title=f"Image Generated",
            description=f"Prompt: **{text}**\nStyle: **{style_preset}**",
            color=discord.Color.blurple()
        )
        embed.set_image(url="attachment://image.png")
        embed.add_field(
            name="Quota Status",
            value=f"Daily: {daily_used}/{updated_quota['daily']['limit']} | Storage: {storage_used:.1f}/{storage_limit}MB",
            inline=False
        )
        
        await interaction.followup.send(content="Your image has been generated!", embed=embed, file=file, view=view)

    async def imgimg(self, interaction: discord.Interaction, text: str = "", style_preset: str = "enhance"):
        """Generate image from image using ImageGenerator."""
        if not self.storage or not self.generator:
            await interaction.followup.send("Image generation services are not available. Please try again later.", ephemeral=True)
            return
        
        user_id, guild_id, user_roles, user_level = self._quota_context(interaction)
        
        # Find the last image in channel history
        last_image = None
        async for message in interaction.channel.history(limit=30):
            if message.author.bot and message.attachments:
                last_image = message.attachments[0].url
                break
        
        if not last_image:
            await interaction.followup.send(content="No image found in recent messages!", ephemeral=True)
            return
        
        style_preset = style_preset.lower()
        if style_preset not in style_presets:
            style_preset = "enhance"
        
        # Check quota before generation
        has_quota, error_embed = await self._check_quota(interaction, user_id, guild_id, user_roles, user_level)
        if not has_quota:
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return
        
        try:
            # Generate image-to-image
            success, image_bytes, gen_msg = await self.generator.image_to_image(last_image, text, style_preset)
            if not success:
                embed = discord.Embed(
                    title="Image-to-Image Generation Failed",
                    description=gen_msg,
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Save image
            saved, save_msg, image_path = self.storage.save_image(
                image_data=image_bytes,
                user_id=user_id,
                image_name=f"image_to_image_{interaction.id}.png",
                user_roles=user_roles,
                user_level=user_level,
                guild_id=guild_id,
            )
            
            if not saved:
                embed = discord.Embed(
                    title="Storage Error",
                    description=save_msg,
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Get updated quota status
            updated_quota = self.storage.get_quota_status(
                user_id,
                user_roles=user_roles,
                user_level=user_level,
                guild_id=guild_id,
            )
            daily_used = updated_quota['daily']['limit'] - updated_quota['daily']['remaining']
            storage_used = updated_quota['user']['used_mb']
            storage_limit = updated_quota['user']['limit_mb']
            
            file = discord.File(str(image_path), filename="image.png")
            view = ImageOptions(self, interaction, text, style_preset)
            
            embed = discord.Embed(
                title="Image-to-Image Generated",
                description=f"Prompt: **{text}**\nStyle: **{style_preset}**",
                color=discord.Color.blurple()
            )
            embed.set_image(url="attachment://image.png")
            embed.add_field(
                name="Quota Status",
                value=f"Daily: {daily_used}/{updated_quota['daily']['limit']} | Storage: {storage_used:.1f}/{storage_limit}MB",
                inline=False
            )
            
            await interaction.followup.send(content="Your image has been transformed!", embed=embed, file=file, view=view)
            
        except Exception as e:
            self.logger.error(f"Error in image-to-image generation: {str(e)}", exc_info=True)
            embed = discord.Embed(
                title="Generation Error",
                description="An unexpected error occurred. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def upscale(self, interaction: discord.Interaction, text: str = "", style_preset: str = "enhance"):
        """Upscale the last image using ImageGenerator."""
        if not self.storage or not self.generator:
            await interaction.followup.send("Image generation services are not available. Please try again later.", ephemeral=True)
            return
        
        user_id, guild_id, user_roles, user_level = self._quota_context(interaction)
        
        # Find the last image in channel history
        last_image = None
        async for message in interaction.channel.history(limit=30):
            if message.author.bot and message.attachments:
                last_image = message.attachments[0].url
                break
        
        if not last_image:
            await interaction.followup.send(content="No image found in recent messages.", ephemeral=True)
            return
        
        # Check quota before generation
        has_quota, error_embed = await self._check_quota(interaction, user_id, guild_id, user_roles, user_level)
        if not has_quota:
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return
        
        try:
            # Upscale image using generator
            success, image_bytes, gen_msg = await self.generator.upscale_image(last_image)
            if not success:
                embed = discord.Embed(
                    title="Upscale Failed",
                    description=gen_msg,
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Save upscaled image
            saved, save_msg, image_path = self.storage.save_image(
                image_data=image_bytes,
                user_id=user_id,
                image_name=f"upscale_{interaction.id}.png",
                user_roles=user_roles,
                user_level=user_level,
                guild_id=guild_id,
            )
            
            if not saved:
                embed = discord.Embed(
                    title="Storage Error",
                    description=save_msg,
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Get updated quota status
            updated_quota = self.storage.get_quota_status(
                user_id,
                user_roles=user_roles,
                user_level=user_level,
                guild_id=guild_id,
            )
            daily_used = updated_quota['daily']['limit'] - updated_quota['daily']['remaining']
            storage_used = updated_quota['user']['used_mb']
            storage_limit = updated_quota['user']['limit_mb']
            
            file = discord.File(str(image_path), filename="image.png")
            view = ImageOptions(self, interaction, text, style_preset)
            # Disable upscale button since already upscaled
            view.children[2].disabled = True
            
            embed = discord.Embed(
                title="Image Upscaled (2x)",
                description="Your image has been upscaled successfully!",
                color=discord.Color.blurple()
            )
            embed.set_image(url="attachment://image.png")
            embed.add_field(
                name="Quota Status",
                value=f"Daily: {daily_used}/{updated_quota['daily']['limit']} | Storage: {storage_used:.1f}/{storage_limit}MB",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, file=file, view=view)
            
        except Exception as e:
            self.logger.error(f"Error in upscale: {str(e)}", exc_info=True)
            embed = discord.Embed(
                title="Upscale Error",
                description="Your image could not be upscaled. Ensure it's a valid image format and 1024x1024px or smaller.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


    # group.command(name="imagine", description="Generate an image from text", guild_ids=[547471286801268777], cooldown_after_parsing=True, cooldown=1, bucket=BucketType.user)
    @app_commands.command(name="imagine", description="Generate an image from text")
    @app_commands.choices(
    style_preset=[app_commands.Choice(name=key, value=key) for key in style_presets.keys()])
    async def imagine(self, interaction: discord.Interaction, 
                      text: str, 
                      style_preset: str = "enhance"):
        await interaction.response.defer()
        await self.generate_image(interaction, text, style_preset)


            
    @imagine.error
    async def imagine_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors from the imagine command."""
        if isinstance(error, commands.MissingRequiredArgument):
            await interaction.followup.send("Please provide some text to generate an image.", ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            # Command cooldown handled by Discord
            pass
        elif hasattr(error, 'original') and isinstance(error.original, aiohttp.ClientResponseError):
            if 'text_prompts' in str(error.original):
                await interaction.edit_original_response(content="The text prompt cannot be blank. Please provide some text to generate an image.")
            else:
                self.logger.error(f"API error in imagine command: {error.original}", exc_info=True)
                await interaction.edit_original_response(content="An error occurred while contacting the image generation service. Please try again later.")
        else:
            self.logger.error(f"Unexpected error in imagine command: {error}", exc_info=True)
            try:
                await interaction.edit_original_response(content="An unexpected error occurred. Please try again later.")
            except discord.NotFound:
                # Interaction expired
                pass


class ImageOptions(discord.ui.View):
    def __init__(self, cog: ImageGenerate, interaction: discord.Interaction, text: str, style_preset: str):
        super().__init__()
        self.cog = cog
        self.interaction = interaction
        self.text = text
        self.style_preset = style_preset
        self.value = None

    @discord.ui.button(style=discord.ButtonStyle.blurple,emoji="❤️")
    async def like(self,  interaction: discord.Interaction, button: discord.ui.Button):
        self.value = "like"
        user = interaction.user
        await interaction.channel.send (f"{config.emojis.abby_run} {user.mention} likes the image!.. {config.emojis.abby_idle}")
        await interaction.response.send_message("Thank you for liking the image! This will later be added to a database of your liked images", ephemeral=True)


    @discord.ui.button(style=discord.ButtonStyle.blurple,emoji="➡️")
    async def next(self,  interaction: discord.Interaction, button: discord.ui.Button):
        self.value = "next"
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send("Generating next image...")
        await self.cog.generate_image(self.interaction, self.text, self.style_preset)
                                    
    
    @discord.ui.button(style=discord.ButtonStyle.blurple,emoji="⬆️")
    async def upscale(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = "upscale"
        await interaction.channel.send("Upscaling image...")
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await self.cog.upscale(self.interaction, self.text, self.style_preset)
    

    @discord.ui.button(style=discord.ButtonStyle.blurple,emoji="📷")
    async def image_prompt(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = "image"
        modal = ImagetoImageModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.text_prompt.value:
            await interaction.followup.send("Generating new image using image...")
            await self.cog.imgimg(self.interaction, modal.text_prompt.value, self.style_preset)
        else:
            await interaction.followup.send("No prompt provided. Cancelling...", ephemeral=True)
            self.stop()

class ImagetoImageModal(discord.ui.Modal, title="Image to Image"):

    text_prompt = discord.ui.TextInput(label="Prompt", placeholder="Enter a prompt")


    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.stop()

    async def on_cancel(self, interaction: discord.Interaction):
        self.text_prompt = None
        await interaction.response.defer()
        self.stop()


async def setup(bot):
    await bot.add_cog(ImageGenerate(bot))
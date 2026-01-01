import discord
from discord.ext import commands
from discord.ext.commands import BucketType
from discord import app_commands
import base64
# import requests
from dotenv import load_dotenv
import os
import math
from abby_core.observability.logging import setup_logging, logging
import aiohttp

ABBY_RUN = "<a:Abby_run:1135375927589748899>"
ABBY_IDLE = "<a:Abby_idle:1135376647495884820>"
UP_ARROW = "\U00002B06"
NEXT = "\U000027A1"


load_dotenv()
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")
DAY = 86400

url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {STABILITY_API_KEY}",
}


# Create a mapping of style presets to th eir corresponding variables
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
        setup_logging()
        self.logger = logging.getLogger(__name__)
        self.message_id = None


    async def generate_image(self, interaction: discord.Interaction, text: str, style_preset: str = "enhance"):
        style_preset = style_preset.lower()
        if style_preset not in style_presets:
            style_preset = "enhance"

        body = {
            "width": 1024,
            "height": 1024,
            "steps": 50,
            "seed": 0,
            "cfg_scale": 7,
            "samples": 1,
            "style_preset": style_presets[style_preset],
            "text_prompts": [
                {
                    "text": text,

                    "weight": 1
                },
                {
                    "text": "blurry, bad, watermark, low quality, low resolution, low res, low resolution, low, signiature, deformed, misshapen ",
                    "weight": -1
                }
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body) as response:
                if response.status != 200:
                    raise aiohttp.ClientError(f"Non-200 response: {response.text}")
                data = await response.json()

        for i, image in enumerate(data["artifacts"]):
            with open(f"/home/Discord/Images/generate_image.png", "wb") as f:
                f.write(base64.b64decode(image["base64"]))
        file = discord.File(f"/home/Discord/Images/generate_image.png")
        view = ImageOptions(self, interaction, text, style_preset)

        await interaction.followup.send(content=f"Your prompt **{text}**  (Style: {style_preset}) generated this:",file=file, view=view)

    async def imgimg(self, interaction: discord.Interaction, text = str, style_preset: str = "enhance"):
        last_image = None
        async for message in interaction.channel.history(limit=30):
            if message.author.bot and message.attachments:
                last_image = message.attachments[0].url
                break
        if not last_image:
            await interaction.followup.send(content="No image found!", ephemeral=True)
            return
        
        style_preset = style_preset.lower()
        if style_preset not in style_presets:
            style_preset = "enhance"

        try:
            engine_id = "stable-diffusion-xl-1024-v1-0"
            api_host = os.getenv("API_HOST", "https://api.stability.ai")
            api_key = os.getenv("STABILITY_API_KEY")

            if api_key is None:
                raise Exception("Missing Stability API key.")
                

            async with aiohttp.ClientSession() as session:
                # Get the image content
                async with session.get(last_image) as get_response:
                    init_image_content = await get_response.read()

                # Create a FormData object
                form_data = aiohttp.FormData()
                form_data.add_field("init_image", init_image_content, filename="init_image.png", content_type="image/png")
                form_data.add_field("image_strength", "0.35")
                form_data.add_field("init_image_mode", "IMAGE_STRENGTH")
                form_data.add_field("text_prompts[0][text]", f"{text}")
                form_data.add_field("cfg_scale", "7")
                form_data.add_field("samples", "1")
                form_data.add_field("steps", "30")
                form_data.add_field("style_preset", style_presets[style_preset])

                # Post the request with the FormData object
                async with session.post(
                    f"{api_host}/v1/generation/{engine_id}/image-to-image",
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {api_key}"
                    },
                    data=form_data
                ) as response:

                    if response.status != 200:
                        raise Exception("Non-200 response: " + str(await response.text()))
                    data = await response.json()

    
            for i, image in enumerate(data["artifacts"]):
                with open(f"/home/Discord/Images/edited_image.png", "wb") as f:
                    f.write(base64.b64decode(image["base64"]))

            file = discord.File(f"/home/Discord/Images/edited_image.png")
            view = ImageOptions(self, interaction, text, style_preset)
            
            await interaction.followup.send(content=f"Your image to image with prompt: **{text}** generated this:",file=file, view=view)

        except Exception as e:
                error_message = f"Sorry, an error occured. Please try again later."
                self.logger.info(f"Error occured (img_img): {str(e)}")
                return await interaction.channel.send(error_message)

    async def upscale(self, interaction: discord.Interaction, text = str, style_preset: str = "enhance"):
        last_image = None
        async for message in interaction.channel.history(limit=30):
            if message.author.bot and message.attachments:
                last_image = message.attachments[0].url
                break
        if not last_image:
            await interaction.followup.send(content="No image found in the last 30 messages.", ephemeral=True)
            return

        try:
            engine_id = "esrgan-v1-x2plus"
            api_host = os.getenv("API_HOST", "https://api.stability.ai")
            api_key = os.getenv("STABILITY_API_KEY")

            if api_key is None:
                raise Exception("Missing Stability API key.")
            
            async with aiohttp.ClientSession() as session:
                # Get the image content
                async with session.get(last_image) as get_response:
                    image_content = await get_response.content.read() # Read the content as bytes

                # Create a FormData object
                form_data = aiohttp.FormData()
                form_data.add_field("image", image_content, filename="image.png", content_type="image/png")
                form_data.add_field("width", "2048")

                # Post the request with the FormData object
                async with session.post(
                    f"{api_host}/v1/generation/{engine_id}/image-to-image/upscale",
                    headers={
                        "Accept": "image/png",
                        "Authorization": f"Bearer {api_key}"
                    },
                    data=form_data
                ) as response:

                    if response.status != 200:
                        raise Exception("Non-200 response: " + str(await response.text()))

                    response_content = await response.content.read() # Read the response content as bytes

                    with open(f"/home/Discord/Images/upscaled_image.png", "wb") as f:
                        f.write(response_content)
            
            file = discord.File(f"/home/Discord/Images/upscaled_image.png")
            view = ImageOptions(self, interaction, text, style_preset)
            
            # Disable the Upscale button
            view.children[2].disabled = True
            await interaction.followup.send(content="Your image is upscaled 2x",file=file, view=view)    
        except Exception as e:
                error_message = f"Your image is improper size - Your image should be 1024x1024px or smaller and be a square. - Please upload a new image."
                self.logger.info(str(e))
                return await interaction.channel.send(error_message)


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
    async def imagine_error(self,interaction, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await interaction.followup.send("Please provide some text to generate an image.")
        elif isinstance(error, commands.CommandOnCooldown):
            pass
            # Handle command cooldown
        elif isinstance(error.original, aiohttp.ClientResponseError) and 'text_prompts' in str(error.original):
            # Handle the specific text prompts error
            await interaction.edit_original_response(content=f"The text prompt cannot be blank. Please provide some text to generate an image.")
        else:
            # If you're unable to handle the error here, you might want to log it and notify the user
            await interaction.edit_original_response(content=f"An unexpected error occurred. Please try again later.")
            self.logger.exception(error)


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
        await interaction.channel.send (f"{ABBY_RUN} {user.mention} likes the image!.. {ABBY_IDLE}")
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
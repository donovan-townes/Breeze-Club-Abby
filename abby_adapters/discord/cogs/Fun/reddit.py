from abby_core.utils.log_config import setup_logging, logging
from discord.ext import commands
from discord import app_commands
import discord
import requests


setup_logging
logger = logging.getLogger(__name__)

BREEZE_LOUNGE = "802512963519905852"
BREEZE_MEMES = "1111136459072753664"

class RedditMeme(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="reddit")
    async def reddit(self, interaction: discord.Interaction) -> None:
        ''' Get a random meme from Reddit'''
        meme = self.fetch_random_meme()
        if meme is not None:
            title, url = meme
            embed = discord.Embed(title=title, color=discord.Color.green())
            embed.set_image(url=url)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message('Failed to fetch a meme. Try again later.', ephemeral=True)
        return


    def fetch_random_meme(self):
        try:
            reddit_api_url = 'https://www.reddit.com/r/memes/random.json'
            response = requests.get(reddit_api_url, headers={'User-agent': 'Meme Bot'})
            response.raise_for_status()
            data = response.json()

            if not data or 'error' in data:
                return None

            meme_data = data[0]['data']['children'][0]['data']
            title = meme_data['title']
            url = meme_data['url']

            return title, url
        except requests.exceptions.RequestException:
            return None

    def extract_media_link(self,message):
        if message.attachments:
            return message.attachments[0].url
        else:
            return None
    
async def setup(bot: commands.Bot):
    await bot.add_cog(RedditMeme(bot))

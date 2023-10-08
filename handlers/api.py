# Disabled until further notice

from flask import Flask, request, jsonify
import requests
from discord.ext import commands
import discord
from utils.log_config import setup_logging, logging
import aiohttp.web


setup_logging()
logger = logging.getLogger(__name__)


class APICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.app = Flask(__name__)
        self.api_app = aiohttp.web.Application()
        self.api_app.router.add_post('/send_message', self.send_message)
        self.runner = aiohttp.web.AppRunner(self.api_app)
         

    async def send_message(self, request):
        data = await request.json()
        channel_id = data.get('channel_id')
        message = data.get('message')
        logger.info(f'[📨] Sending message to channel {channel_id}: {message}')
        # Use Discord.py to send the message
        channel = self.bot.get_channel(int(channel_id))
        await channel.send(message)
        return aiohttp.web.json_response({'message': 'Message sent'})

    @commands.Cog.listener()
    async def on_ready(self):
        await self.runner.setup()
        site = aiohttp.web.TCPSite(self.runner, '127.0.0.1', 5001)
        await site.start()
        logger.info('[🔌] API Cog ready')

    @commands.command()
    async def api_ping(self, ctx, *, message):
        channel_id = ctx.channel.id  # Get the ID of the channel where the command was invoked

        # Make an API request to your send_message endpoint
        api_url = 'http://127.0.0.1:5001/send_message'
        data = {'channel_id': str(channel_id), 'message': message}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=data) as response:
                if response.status == 200:
                    await ctx.send('Message sent via API')
                else:
                    await ctx.send('Failed to send message via API')



# async def setup(bot):
#     await bot.add_cog(APICog(bot))


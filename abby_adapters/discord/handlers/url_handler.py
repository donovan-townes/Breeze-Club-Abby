from abby_core.observability.logging import setup_logging, logging
from abby_core.database.mongodb import connect_to_mongodb
from urllib.parse import urlparse
from googleapiclient.discovery import build
from urllib.parse import parse_qs, urlparse
from dotenv import load_dotenv
import os
from abby_adapters.discord.cogs.Twitch.twitch import get_oauth_token
import requests
from discord.ext import commands, tasks
import asyncio


class UrlHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_dotenv
        setup_logging()
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        self.client_id = os.getenv("TWITCH_CLIENT_ID")
        self.client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        self.oauth_token = get_oauth_token(self.client_id, self.client_secret)
        self.logger = logging.getLogger(__name__)
   
    # Event On Ready
    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f"[🔗] URL Handler is ready!")
   
    # Event On Message
    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages from self
        if message.author == self.bot.user:
            return
        # Ignore messages without a URL
        if not message.content.startswith('http'):
            return
        elif message.content.startswith('http://') or message.content.startswith('https://'): 
            user_id, url = self.process_message_content(message.content, message.author.id, message.mentions)
            await self.handle_url(self.bot, user_id, url)

    # Helpers
    def get_url_type(self,url):
        parsed_url = urlparse(url)
        if 'youtube.com' in parsed_url.netloc:
            return 'youtube'
        elif 'twitch.tv' in parsed_url.netloc:
            return 'twitch'
        elif 'tiktok.com' in parsed_url.netloc:
            return 'tiktok'
        elif 'soundcloud.com' in parsed_url.netloc:
            return 'soundcloud'
        elif 'threads.com' in parsed_url.netloc:
            return 'threads'
        elif 'twitter.com' in parsed_url.netloc:
            return 'tweet'
        else:
            return None

    def process_message_content(self, content, author_id, mentions):
        words = content.split(' ')
        url = words[0]
        if len(words) > 1 and words[1].startswith('<@') and mentions:
            user_id = mentions[0].id
        else:
            user_id = author_id
        return user_id, url

    def retrieve_social_handles(self, user_id):
        try:
            # Specify the database
            client = connect_to_mongodb()
            db = client[f"User_{user_id}"]


            # Specify the collection
            profiles_collection = db["Discord Profile"]

            # Retrieve user's document
            user_document = profiles_collection.find_one()

            # If user_document is None, return empty strings for handles
            if user_document is None:
                return '', '', ''

            # Extract social handles
            twitter_handle = user_document.get('twitter_handle', '')
            youtube_handle = user_document.get('youtube_handle', '')
            twitch_handle = user_document.get('twitch_handle', '')

            return twitter_handle, youtube_handle, twitch_handle

        except Exception as e:
            self.logger.warning("retrieve_social_handles error")
            self.logger.warning(str(e))
            return None

    # Handler Function
    async def handle_url(self, client, user_id, url):
        url_type = self.get_url_type(url)
        if url_type is None:
            # logger.warning("Unknown URL type")
            return
        else:
            self.logger.info(f"[🔗] URL is of type {url_type}")
            if url_type == 'youtube':
                self.logger.info("[🔗] Handling the YouTube Link")
                # video_id = self.get_youtube_video_id(url)
                # self.logger.info(video_id)
                # if video_id is not None:
                #     self.add_youtube_url_to_db(user_id, url, self.api_key)
                #     self.logger.info(f"[🔗] URL has been added to the database")
            elif url_type == 'twitch':
                self.logger.info("[🔗] Handling the Twitch Link")
                clip_id = self.get_twitch_clip_id(url)
                if clip_id is not None:
                    clip_info = self.get_twitch_clip_info(self.client_id, self.oauth_token, clip_id)
                    if clip_info is not None:
                        self.handle_twitch_clip(self.client_id, self.oauth_token, user_id, url)
                        self.logger.info(f"[🔗] Twitch clip info has been added to the database") 
            elif url_type == 'soundcloud':
                self.logger.info("[🔗] Handling the Soundcloud Link")
            elif url_type == 'tiktok':
                self.logger.info("[🔗] Handling the TikTok Link")
            elif url_type == 'threads':
                self.logger.info("[🔗] Handling the Threads Link")
            elif url_type == 'tweet':
                self.logger.info("[🔗] Handling the Twitter Link")
                                            
        return

    # YouTube Logic
    def get_youtube_video_id(self, url):
        parsed_url = urlparse(url)
        if 'youtube.com' in parsed_url.netloc:
            if 'watch' in parsed_url.path:
                # For URLs like: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                return parse_qs(parsed_url.query).get('v')
            elif 'shorts' in parsed_url.path:
                # For URLs like: "https://www.youtube.com/shorts/ilRAq9_LhQ4"
                return parsed_url.path.split('/')[-1]
        return None

    def get_youtube_video_info(self, api_key, video_id):
        # Use the YouTube Data API to get information about the video
        youtube = build('youtube', 'v3', developerKey=api_key)

        # First request to get the video's details
        video_request = youtube.videos().list(
            part="snippet",
            id=video_id
        )
        video_response = video_request.execute()

        # Get the video's title, description, channel title, and category ID
        items = video_response.get('items')
        if not items:
            return None

        snippet = items[0].get('snippet')
        if not snippet:
            return None

        title = snippet.get('title')
        description = snippet.get('description')
        channel_title = snippet.get('channelTitle')
        category_id = snippet.get('categoryId')

        # Second request to get the category's details
        category_request = youtube.videoCategories().list(
            part="snippet",
            id=category_id
        )
        category_response = category_request.execute()

        # Get the category name
        category_items = category_response.get('items')
        if not category_items:
            return None

        category_name = category_items[0].get('snippet', {}).get('title')

        return title, description, channel_title, category_name

    def add_youtube_url_to_db(self, user_id, url, api_key):
        twitter_handle, youtube_handle, twitch_handle = self.retrieve_social_handles(
            user_id)

        video_id = self.get_youtube_video_id(url)
        if video_id is not None:
            title, description, channel_title, category_name = self.get_youtube_video_info(
                api_key, video_id)

        # Connect to your MongoDB server
        client = connect_to_mongodb()

        # Select your database
        db = client["Abby_Database"]

        # Select your collection
        collection = db["urls"]

        # Insert a document
        collection.insert_one({
            "url": url,
            "twitter_handle": f"@{twitter_handle}",
            "youtube_handle": f"@{youtube_handle}",
            "twitch_handle": twitch_handle,
            "title": title,
            "description": description,
            "channel_title": channel_title,
            "category": category_name
        })

        self.logger.info(f"✅ Youtube URL added to Database: {url}")


    # Twitch Logic
    def get_twitch_clip_id(self, url):
        parsed_url = urlparse(url)
        if 'clips.twitch.tv' in parsed_url.netloc or 'twitch.tv' in parsed_url.netloc:
            return parsed_url.path.split('/')[-1]
        return None

    def get_twitch_clip_info(self, client_id, oauth_token, clip_id):
        headers = {
            'Client-ID': client_id,
            'Authorization': f"Bearer {oauth_token}"
        }
        response = requests.get(f'https://api.twitch.tv/helix/clips?id={clip_id}', headers=headers)
        if response.status_code != 200:
            return None
        return response.json()

    def handle_twitch_clip(self, client_id, oauth_token, user_id, url):
        clip_id = self.get_twitch_clip_id(url)
        if clip_id is not None:
            clip_info = self.get_twitch_clip_info(client_id, oauth_token, clip_id)
            if clip_info is not None:
                data = clip_info.get('data')
                if data:
                    clip = data[0]
                    title = clip.get('title')
                    broadcaster_name = clip.get('broadcaster_name')
                    url = clip.get('url')
                    self.add_twitch_clip_to_db(user_id, url, title, broadcaster_name)

    def add_twitch_clip_to_db(self, user_id, url, title, broadcaster_name):
        twitter_handle, youtube_handle, twitch_handle = self.retrieve_social_handles(
            user_id)

        video_id = self.get_youtube_video_id(url)
        if video_id is not None:
            title, description, channel_title, category_name = self.get_youtube_video_info(
                self.api_key, video_id)

        # Connect to your MongoDB server
        client = connect_to_mongodb()

        # Select your database
        db = client["Abby_Database"]

        # Select your collection
        collection = db["urls"]

        # Insert a document
        collection.insert_one({
            "url": url,
            "twitter_handle": f"@{twitter_handle}",
            "youtube_handle": f"@{youtube_handle}",
            "twitch_handle": twitch_handle,
            "title": title,
            "broadcaster_name": broadcaster_name
        })

        self.logger.info(f"✅ Twitch Clip added to Database: {url}")
        

async def setup(bot):
    await bot.add_cog(UrlHandler(bot))

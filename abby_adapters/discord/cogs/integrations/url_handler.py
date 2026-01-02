"""
URL detection and processing cog.

Automatically detects URLs posted in messages and handles them based on type:
- YouTube: Video metadata extraction
- Twitch: Clip information tracking
- TikTok: Placeholder for TikTok handling
- Threads: Placeholder for Threads handling
- Twitter/X: Tweet archiving

Integrates with user social profiles and stores URL metadata in database.
"""

from abby_core.observability.logging import setup_logging, logging
from abby_core.database.mongodb import connect_to_mongodb
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build
import requests
from discord.ext import commands
from abby_adapters.discord.config import BotConfig

setup_logging()
logger = logging.getLogger(__name__)


class UrlHandler(commands.Cog):
    """Handle URL detection and processing from message content."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            self.config = BotConfig.from_env()
            self.api_key = self.config.apis.youtube_key
            self.client_id = self.config.apis.twitch_client_id
            self.client_secret = self.config.apis.twitch_client_secret
            # Get OAuth token from Twitch integration
            try:
                from abby_adapters.discord.cogs.integrations.twitch import get_oauth_token
                self.oauth_token = get_oauth_token(self.client_id, self.client_secret)
            except ImportError:
                self.oauth_token = None
                logger.warning("Could not import get_oauth_token from twitch cog")
        except Exception as e:
            logger.error(f"Error loading URL handler config: {e}")
            self.api_key = None
            self.client_id = None
            self.client_secret = None
            self.oauth_token = None
        
        logger.info("[🔗] URL Handler initialized")
   
    @commands.Cog.listener()
    async def on_ready(self):
        """Cog ready event."""
        logger.info("[🔗] URL Handler is ready!")
   
    @commands.Cog.listener()
    async def on_message(self, message):
        """Process messages containing URLs."""
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
    def get_url_type(self, url: str) -> str:
        """Determine the type of URL (youtube, twitch, etc)."""
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
        elif 'twitter.com' in parsed_url.netloc or 'x.com' in parsed_url.netloc:
            return 'tweet'
        else:
            return None

    def process_message_content(self, content: str, author_id: int, mentions: list) -> tuple:
        """Extract URL and target user ID from message."""
        words = content.split(' ')
        url = words[0]
        if len(words) > 1 and words[1].startswith('<@') and mentions:
            user_id = mentions[0].id
        else:
            user_id = author_id
        return user_id, url

    def retrieve_social_handles(self, user_id: int) -> tuple:
        """Retrieve user's social media handles from database."""
        try:
            client = connect_to_mongodb()
            db = client[f"User_{user_id}"]
            profiles_collection = db["Discord Profile"]
            user_document = profiles_collection.find_one()

            if user_document is None:
                return '', '', ''

            twitter_handle = user_document.get('twitter_handle', '')
            youtube_handle = user_document.get('youtube_handle', '')
            twitch_handle = user_document.get('twitch_handle', '')

            return twitter_handle, youtube_handle, twitch_handle

        except Exception as e:
            logger.warning(f"Error retrieving social handles: {e}")
            return None

    # Handler Function
    async def handle_url(self, client, user_id: int, url: str):
        """Route URL handling based on type."""
        url_type = self.get_url_type(url)
        if url_type is None:
            return
        else:
            logger.info(f"[🔗] URL is of type {url_type}")
            if url_type == 'youtube' and self.api_key:
                logger.info("[🔗] Handling the YouTube Link")
                # TODO: Implement YouTube URL handling
            elif url_type == 'twitch' and self.oauth_token:
                logger.info("[🔗] Handling the Twitch Link")
                clip_id = self.get_twitch_clip_id(url)
                if clip_id is not None:
                    clip_info = self.get_twitch_clip_info(self.client_id, self.oauth_token, clip_id)
                    if clip_info is not None:
                        self.handle_twitch_clip(self.client_id, self.oauth_token, user_id, url)
                        logger.info(f"[🔗] Twitch clip info has been added to the database") 
            elif url_type == 'soundcloud':
                logger.info("[🔗] Handling the Soundcloud Link")
            elif url_type == 'tiktok':
                logger.info("[🔗] Handling the TikTok Link")
            elif url_type == 'threads':
                logger.info("[🔗] Handling the Threads Link")
            elif url_type == 'tweet':
                logger.info("[🔗] Handling the Twitter Link")
                                            
        return

    # YouTube Logic
    def get_youtube_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL."""
        parsed_url = urlparse(url)
        if 'youtube.com' in parsed_url.netloc:
            if 'watch' in parsed_url.path:
                return parse_qs(parsed_url.query).get('v')
            elif 'shorts' in parsed_url.path:
                return parsed_url.path.split('/')[-1]
        return None

    def get_youtube_video_info(self, api_key: str, video_id: str) -> tuple:
        """Get metadata for a YouTube video."""
        try:
            youtube = build('youtube', 'v3', developerKey=api_key)

            video_request = youtube.videos().list(
                part="snippet",
                id=video_id
            )
            video_response = video_request.execute()

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

            category_request = youtube.videoCategories().list(
                part="snippet",
                id=category_id
            )
            category_response = category_request.execute()

            category_items = category_response.get('items')
            if not category_items:
                return None

            category_name = category_items[0].get('snippet', {}).get('title')

            return title, description, channel_title, category_name
        except Exception as e:
            logger.error(f"Error getting YouTube video info: {e}")
            return None

    def add_youtube_url_to_db(self, user_id: int, url: str, api_key: str):
        """Store YouTube URL and metadata in database."""
        twitter_handle, youtube_handle, twitch_handle = self.retrieve_social_handles(user_id)

        video_id = self.get_youtube_video_id(url)
        if video_id is not None:
            title, description, channel_title, category_name = self.get_youtube_video_info(api_key, video_id)

        client = connect_to_mongodb()
        db = client["Abby_Database"]
        collection = db["urls"]

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

        logger.info(f"✅ YouTube URL added to database: {url}")


    # Twitch Logic
    def get_twitch_clip_id(self, url: str) -> str:
        """Extract clip ID from Twitch URL."""
        parsed_url = urlparse(url)
        if 'clips.twitch.tv' in parsed_url.netloc or 'twitch.tv' in parsed_url.netloc:
            return parsed_url.path.split('/')[-1]
        return None

    def get_twitch_clip_info(self, client_id: str, oauth_token: str, clip_id: str) -> dict:
        """Get metadata for a Twitch clip."""
        headers = {
            'Client-ID': client_id,
            'Authorization': f"Bearer {oauth_token}"
        }
        try:
            response = requests.get(f'https://api.twitch.tv/helix/clips?id={clip_id}', headers=headers)
            if response.status_code != 200:
                return None
            return response.json()
        except Exception as e:
            logger.error(f"Error getting Twitch clip info: {e}")
            return None

    def handle_twitch_clip(self, client_id: str, oauth_token: str, user_id: int, url: str):
        """Process Twitch clip and store metadata."""
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

    def add_twitch_clip_to_db(self, user_id: int, url: str, title: str, broadcaster_name: str):
        """Store Twitch clip and metadata in database."""
        twitter_handle, youtube_handle, twitch_handle = self.retrieve_social_handles(user_id)

        client = connect_to_mongodb()
        db = client["Abby_Database"]
        collection = db["urls"]

        collection.insert_one({
            "url": url,
            "twitter_handle": f"@{twitter_handle}",
            "youtube_handle": f"@{youtube_handle}",
            "twitch_handle": twitch_handle,
            "title": title,
            "broadcaster_name": broadcaster_name
        })

        logger.info(f"✅ Twitch clip added to database: {url}")
        

async def setup(bot: commands.Bot) -> None:
    """Load the UrlHandler cog."""
    await bot.add_cog(UrlHandler(bot))
    logger.info("[✅] UrlHandler cog loaded")

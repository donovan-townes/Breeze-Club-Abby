import tweepy
from dotenv import load_dotenv
import os
from abby_core.observability.logging import setup_logging, logging
import time
from discord.ext import commands,tasks 

# Load environment variables
load_dotenv()
setup_logging()

class TwitterClient(commands.Cog):
    def __init__(self):
        self.client = None
        self.key = os.getenv("TWITTER_API_KEY")
        self.keySecret = os.getenv("TWITTER_API_SECRET")
        self.accessToken = os.getenv("TWITTER_ACCESS_TOKEN")
        self.accessTokenSecret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        self.bearer_token = None
        self.logger = logging.getLogger(__name__)

    # Connect to Twitter
    def connect(self,return_api=False):
        client = tweepy.Client(self.bearer_token, self.key, self.keySecret,
                               self.accessToken, self.accessTokenSecret)
        self.logger.info(f" [🐦] Logged in as {client.get_me().data.username}")
        
        if return_api:
            # Authenticate to Twitter
            auth = tweepy.OAuthHandler(self.key, self.keySecret)
            auth.set_access_token(self.accessToken, self.accessTokenSecret)
            api = tweepy.API(auth)
            return api
        else:
            return client        
   
    # Post a tweet with media
    def post_tweet_with_media(self,text,media):
        self.client = self.connect()
        self.client.create_tweet(text=text,media_ids=[media])
        self.logger.info(f" [🐦] Posted tweet: {text}")

    # Get user information (profile, tweets, timeline
    def get_user_info(self,handle):
        self.client = self.connect()
        if self.client.get_user(handle) == None:
            return None
        user_profile = self.client.get_user(handle)
        user_tweets = self.client.get_user_tweets(handle)
        user_timeline = self.client.get_user_timeline(handle)
        return user_profile, user_tweets, user_timeline
    
    def get_latest_tweet(self, handle):
        self.client = self.connect()
        try:
            user_tweets = self.client.user_timeline(screen_name = handle, count = 1) # count sets the number of tweets to retrieve
            if not user_tweets: # if the list is empty
                return None
            return user_tweets[0].text
        except Exception as e:
            self.logger.error(f" [🐦] Failed to retrieve latest tweet: {e}")
            return None

    # Post a tweet and return the twitter link
    def post_tweet(self, tweet):
        self.client = self.connect()
        tweet_text = tweet
        self.logger.info(f"[🐦] Posting tweet: {tweet_text}")
        try:
            response = self.client.create_tweet(text=tweet_text)
            # print(response.data)
            tweet_id = response.data['id']
            user = self.client.get_me()
            user_name = user.data.username
            tweet_link = (f"https://twitter.com/{user_name}/status/{tweet_id}")
            self.logger.info(f" [🐦] Posted Tweet: {tweet_link}")
            return tweet_link
        
        except Exception as e:
            self.logger.error(f"[🐦] Failed to post tweet: {e}")
            return None 
    
    # Like and retweet    
    def like_and_retweet(self):
        self.logger.info(f"[🐦] Liking and retweeting...")
        api = self.connect(return_api=True)
        for tweet in tweepy.Cursor(api.search, q='#BreezeClub', tweet_mode='extended', lang='en').items(10):
            try:
                self.logger.info('\nTweet by: @' + tweet.user.screen_name)
                tweet.favorite()
                tweet.retweet()
                time.sleep(5)
            except tweepy.TweepError as e:
                self.logger.warning(e)
            except StopIteration:
                break

async def setup(bot):
    await bot.add_cog(TwitterClient())
    

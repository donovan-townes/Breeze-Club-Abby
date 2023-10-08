from Twitter.Client import TwitterClient
from datetime import datetime
import discord
from discord.ext import commands
from utils.log_config import setup_logging, logging
from discord.ext.commands import Group

setup_logging()
logger = logging.getLogger(__name__)
from discord.ext import commands


@commands.group(alias=['tw', 'twit'])
async def twitter(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send('Please specify a subcommand: tweet, latest, or timeline')

@twitter.command()
async def tweet(ctx):
    # Ask the user what they want to tweet
    await ctx.send("What would you like to tweet?")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    msg = await ctx.bot.wait_for('message', check=check)
    tweet_text = msg.content

    # Check if the user entered a tweet
    if not tweet_text:
        await ctx.send("Please provide a tweet.")
        return

    # Confirm with user
    await ctx.send(f"Are you sure you want to tweet '{tweet_text}'? (y/n)")
    msg = await ctx.bot.wait_for('message', check=check)
    confirm = msg.content

    # Check if the user confirmed
    if confirm.lower() != 'y':
        logger.info(" [🐦] Tweet cancelled.")
        return

    # Post the tweet
    try:
        twitter_client = TwitterClient()
        twitter_url = twitter_client.post_tweet(tweet_text)
        await ctx.send(f"Tweet posted: {tweet_text}\n {twitter_url}")
    except Exception as e:
        logger.error(f"Failed to post tweet: {e}")
        await ctx.send(f"Failed to post tweet: {e}")

# @commands.command()
# async def latest(ctx):
#     twitter_client = TwitterClient()
#     handle = ctx.message.content.split()[1]
#     logger.info(f"Getting latest tweet from {handle}")
#     tweet = twitter_client.get_latest_tweet(handle)
#     await ctx.send(f"Latest tweet from {handle}: {tweet}")



twitter.description = """
Twitter commands:
- tweet: Post a tweet
- latest: Get the latest tweet from a user
- timeline: Get the timeline of a user
- profile: Get the profile of a user
- schedule: Schedule a tweet
- random: Schedule a random tweet
- share: Share a tweet
"""

# def setup(bot):
#     bot.add_command(twitter)



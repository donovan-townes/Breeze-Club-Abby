from discord.ext import commands
import re
from discord import Embed
import abby_core.database.mongodb as mongo_db
from abby_core.observability.logging import setup_logging, logging

PROFILE_LINK = "https://brndndiaz.dev/abby"

def get_site_from_link(link):
    # Extract the site from the link using regular expressions
    pattern = r'(?:https?://)?(?:www\.)?([^/]+)'
    match = re.match(pattern, link)
    if match:
        site = match.group(1)
        return site.lower()  # Convert to lowercase for consistency
    return None

@commands.command()
async def profile(message):
    user_id = message.author.id
    profile = mongo_db.get_profile(f"{user_id}")
    if profile is None:
        await message.send(f"Sorry <@{user_id}> you don't have a profile! Create one at {PROFILE_LINK}")
    else:
        # Get creative profile data (where name, description, genre, influences are stored)
        creative_profile = profile.get('creative_profile', {})
        
        # Check if creative profile has required fields
        if not all(key in creative_profile for key in ['name', 'description', 'genre', 'influences']):
            await message.send(f"Sorry <@{user_id}> your profile is incomplete! Visit {PROFILE_LINK} to complete it.")
            return
        
        profile_url = f"https://brndndiaz.dev/abby/profile/{profile.get('username', 'profile')}"
        embed = Embed(
            title=creative_profile['name'],
            description=creative_profile['description'],
            color=0x00ff00,  # You can choose your own color
            url=profile_url,
        )
        embed.set_thumbnail(url=profile.get('avatar_url'))
        embed.add_field(name="Genre", value=creative_profile['genre'], inline=True)
        embed.add_field(name="Influences",
                        value=creative_profile['influences'], inline=True)

        # Add social media links as hyperlinks within the description
        if 'socialmedia' in creative_profile and isinstance(creative_profile['socialmedia'], list):
            social_media_links = '\n'.join(
                f"[{get_site_from_link(link)}]({link})" for link in creative_profile['socialmedia'])
            embed.description += f"\n\nSocial Media:\n{social_media_links}"

        await message.send(embed=embed)

def setup(bot):
    bot.add_command(profile)

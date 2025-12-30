import openai
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import time
import re
import os
from dotenv import load_dotenv
from discord.ext import commands
from abby_core.utils.log_config import setup_logging, logging
from abby_core.utils.mongo_db import get_genres, get_promo_session


setup_logging
logger = logging.getLogger(__name__)

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

start_day = 1
end_day = 3
platforms = ["YouTube", "Facebook", "Instagram", "Twitter"]
counter = 1

post_types = {
    1: "Initial Announcement of track: {song}",
    2: "Teaser of track: {song}",
    3: "Sneak Peek of track: {song}",
    4: "{song} Pre Order Announcement!",
    5: "{song} Pre Order Reminder",
    6: "How {song} by {artist} will improve your day!",
    7: "Pre Order {song} on Beatport",
    8: "Pre Save {song} on Spotify",
    9: "Pre Save {song} on Apple",
    10: "Interactive Poll about {song}",
    11: "{artist} - {song} Music Breakdown",
    12: "Support the artist - {artist}",
    13: "Inspiration behind the song {song}",
    14: "Upcoming Release Day Reminder for {song}",
    15: "{song} Release Day Celebration",
    16: "Listen to song {song} on Spotify and Apple Music",
    17: "Thank You For Listening: {song}",
    18: "Upcoming Music and More Ways To Support {artist}",
    19: "Checking in on the release: {song}",
    20: "{artist} Thank You Note",
    21: "{song} Post Release Reflection",
}

platform_max_tokens = {
    "YouTube": 2000,
    "Facebook": 1500,
    "Instagram": 1200,
    "Twitter": 150,
}


def calculate_calendar_date(release_date, day):
    release_date_obj = datetime.strptime(release_date, "%m/%d/%y")
    calendar_date = (release_date_obj - timedelta(days=14)) + \
        timedelta(days=day-1)
    return calendar_date.strftime("%B %d")


def ai_generate(artist_name, artist_song, release_date, platforms, day, genre):
    max_tokens = 1000  # Default max tokens

    message_list = []
    for platform in platforms:
        post_type = post_types.get(day, "Unknown")
        post_type = post_type.format(song=artist_song, artist=artist_name)

        calendar_date = calculate_calendar_date(release_date, day)

        messages = [
            {"role": "system", "content": "You are the music label Cool Breeze social media assistant in charge of creating social media posts."},
            {"role": "system",
                "content": f"The release date is {release_date} (MM/DD/YY)."},
            {"role": "system", "content": f"This is day: {day} of promotion"},
            {"role": "system", "content": f"The genre is {genre}."},
            {"role": "user", "content": f"Create a {platform} social media {post_type} post for {artist_name} - {artist_song}."},
            {"role": "assistant", "content": "Sure I can do that for you:"}
        ]
        message_list.extend(messages)
    logger.info(message_list)
    try:
        generated_posts = []
        for i, platform in enumerate(platforms):
            max_tokens = platform_max_tokens.get(platform, 1000)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=message_list,
                temperature=1.1,
                n=len(platforms),
                stop=None,
                stream=False,
                max_tokens=max_tokens,
                presence_penalty=0.6,
                frequency_penalty=0.6
            )

            platform_response = response["choices"][i]
            post = platform_response["message"]["content"]
            generated_posts.append((platform, post))

        return generated_posts

    except openai.error.RateLimitError as e:
        # print(f"RateLimitError: {e}")
        logger.warning("❗ ERROR! Retrying the run...")
        time.sleep(0.3)
        return ai_generate(artist_name, artist_song, release_date, platforms, day, genre)


@commands.command()
async def generate(message):
    client = message.bot
    counter = 1

    # Get the artist name
    await message.channel.send("Enter the artist name: ")
    response = await client.wait_for('message', check=lambda m: m.author == message.author)
    artist = response.content

    # Get the song name
    await message.channel.send("Enter the song: ")
    response = await client.wait_for('message', check=lambda m: m.author == message.author)
    song = response.content

    # Get the release date
    await message.channel.send("Enter the release date (MM/DD/YY): ")
    response = await client.wait_for('message', check=lambda m: m.author == message.author)
    release_date = response.content

    # Get the total promotion days needed
    await message.channel.send("How many days will this run? ")
    response = await client.wait_for('message', check=lambda m: m.author == message.author)
    end_day = int(response.content)

    # Get the desired platforms
    await message.channel.send(f"Enter the desired platforms (Available platforms: {', '.join(platforms)}): ")
    response = await client.wait_for('message', check=lambda m: m.author == message.author)

    # Create a dictionary where keys are lower case platform names and values are the original platform names.
    platform_dict = {platform.lower(): platform for platform in platforms}

    # Parse the platforms from the user's message.
    # This assumes the user is entering platforms as comma-separated values.
    selected_platforms = [p.strip().lower()
                          for p in response.content.split(',')]

    # Filter out any platforms that are not in the dictionary of valid platforms and map to the correct case.
    valid_selected_platforms = [platform_dict[p]
                                for p in selected_platforms if p in platform_dict]

    if not valid_selected_platforms:
        await message.channel.send("❌ You did not specify any valid platforms. Please try again.")
        return
    # Get the genre
    # replace this with your function that gets genres from mongodb
    genre_dict = get_genres()

    # Create a dictionary where keys are lower case genre names and values are the original genre names.
    genre_dict_lower = {genre.lower(): genre for genre in genre_dict.keys()}

    # Get the genre
    await message.channel.send(f"Enter the desired genre (Available genres: {', '.join(genre_dict.keys())}): ")
    response = await client.wait_for('message', check=lambda m: m.author == message.author)

    # Parse the genre from the user's message.
    selected_genre = response.content.strip().lower()

    # Validate if entered genre is in the dictionary of valid genres.
    if selected_genre not in genre_dict_lower:
        await message.channel.send("❌ You did not specify a valid genre. Please try again.")
        return

    # If genre is valid, update the system message content to include genre information
    genre_key = genre_dict_lower[selected_genre]
    genre_desc = genre_dict[genre_key]
    genre = genre_desc

    await message.channel.send("\nSocial media posts will be generated with the following details:")
    await message.channel.send(f"Artist Name: {artist}")
    await message.channel.send(f"Song: {song}")
    await message.channel.send(f"Release Date: {release_date}")
    await message.channel.send(f"Platforms selected: {valid_selected_platforms}")
    await message.channel.send(f"Genre: {genre}")
    await message.channel.send(f"Total Promotion Days Needed: {end_day} days")

    # Confirm before proceeding
    await message.channel.send("\n 🟡 Do you want to proceed? `yes` or `no`: ")
    response = await client.wait_for('message', check=lambda m: m.author == message.author)
    confirm = response.content.lower()
    await message.channel.send("Generating Posts... Please be patient...")

    if confirm == 'yes':
        # If confirmation is 'y', then start generating posts
        with ThreadPoolExecutor() as executor:
            for day in range(start_day, end_day + 1):
                futures = []
                generated_posts = []
                for platform in valid_selected_platforms:
                    if day >= counter:
                        future = executor.submit(
                            ai_generate, artist, song, release_date, [platform], day, genre)
                        futures.append(future)
                counter += 1
                for future in futures:
                    generated_posts.extend(future.result())

                if generated_posts:
                    for platform, post in generated_posts:
                        post = re.sub("\033\[\d+m", "", post)
                        await message.channel.send(f"**POST {day}** for {platform}: \n---\n{post}")
    else:
        await message.channel.send("❌Program canceled.")

generate.description = '''
**Usage:** `!generate`

Starts a GPT generation session for the user for their music content. It will ask for more information before it generates the content.
Any "incorrect" info will cause the program to end and you'll have to restart.

This command is experimental and may produce unwanted results, and as such is still under
development. However you are welcome to use it for your creative art.

'''


def setup(bot):
    bot.add_command(generate)

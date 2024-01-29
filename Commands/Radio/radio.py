import datetime
from discord.ext import commands
import discord
from utils.log_config import logging, setup_logging
import os
import random
import asyncio
from discord.ext.commands import Group
import re
from discord.errors import ClientException
from main import Abby
from mutagen.mp3 import MP3

play_next_lock = asyncio.Lock()

setup_logging()
logger = logging.getLogger(__name__)
# discord_logger = logging.getLogger('discord')

RADIO_CHANNEL = 839379779790438430

skip_flag = False

@commands.group(invoke_without_command=True, aliases=['rad', 'r'])  # Set invoke_without_command to True and add aliases
async def radio(message):
    if message.invoked_subcommand is None:  # If no subcommand was invoked
        await message.send(" Invalid Command or No Argument was given! \nUse commands after !radio to operate [play, stop, pause, resume]")

@radio.command(aliases=['p', 'start', 'begin','join','connect'])
async def play(message):
    logger.info("[📻] Playing Radio")
    try:
        voice_channel = message.author.voice.channel
    except AttributeError:    
        await message.send("You need to be connected to a voice channel!")
        return
    await message.channel.send("Now playing the Radio 📻")
    await play_next(message)
    # logger.info("Finished Play Command")

async def play_next(message):
    # get the current unix time
    initial_playtime = datetime.datetime.now().timestamp()

    Abby.initial_playtime = initial_playtime
    async with play_next_lock:
        logger.info("[📻] Playing Next Song")
    try:
        voice_channel = message.author.voice.channel
        if voice_channel:
            # Directory where your music files are stored
            music_dir = "/home/Discrd/songs/"
            # List all files in the directory
            music_files = os.listdir(music_dir)
            # Select a random file
            file = random.choice(music_files)
            # Create a full path to the file
            path = os.path.join(music_dir, file)
            # Split the file name and extension
            file_name, file_extension = os.path.splitext(file)
            # Remove anything within brackets, including the brackets themselves
            file_name = re.sub(r'\[.*?\]', '', file_name)

            # Replace this with the ID of your custom emoji
            Abby.your_custom_emoji = "<:breeze_music_headphones:806034888201338950>"
            Abby.your_custom_emoji_2 = "<:breeze_musicnote:806034886044942336>"

            embed = discord.Embed(
                # title=f"{Abby.your_custom_emoji} **Now Playing** \n  {Abby.your_custom_emoji_2}: {file_name.strip()}",
                title = f"{Abby.your_custom_emoji} Breeze Radio 88.8 FM ",
                color=0x00ff00)
            Abby.current_song = file_name.strip()
            Abby.current_song_path = path
            Abby.song_length = getSongLengthInSeconds(path)
            embed.add_field(
                name="Now Playing",
                value=f"{Abby.your_custom_emoji_2}: {file_name.strip()}",
                inline=True
            )

            
            # get bot avatar
            embed.set_thumbnail(
                url=message.bot.user.avatar
            )

            send_message = await voice_channel.send(embed=embed)
            # Add a reaction to the message
            await send_message.add_reaction("<a:z8_leafheart_excited:806057904431693824>")
            await start_playing(message, path)
            # logger.info("Finished Play Next Function")
    except AttributeError as e:
        logger.error(f"Attribute Error: {e}")
        await message.send("You need to be connected to a voice channel!")
        return
    
async def start_playing(message,path):
    bot = message.bot
    # logger.info("[📻] Starting to play music")
    try:
        voice_channel = message.author.voice.channel
    except AttributeError:
        logger.error("Attribute Error: You need to be connected to a voice channel!")   
        await message.send("You need to be connected to a voice channel!")
        return
    
    # try to connect to voice channel if you are not already connected
    if voice_channel in [vc.channel for vc in bot.voice_clients]:
        vc = [vc for vc in bot.voice_clients if vc.channel == voice_channel][0]
    else:
        vc = await voice_channel.connect()

    def after_callback(error):
        global skip_flag
        # logger.info("[📻] After Callback Called")

        if skip_flag:
            skip_flag = False
        
        elif message.bot.voice_clients:
            if not message.bot.voice_clients[0].is_playing() and message.bot.voice_clients[0].is_connected():
                coro = play_next(message)
                fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
                try:
                    fut.result()
                except:
                    # an error was raised.
                    logger.exception("Error in play_next")
    try:
        # Check if the bot is already playing something, if so, stop it
        if vc.is_playing():
            vc.stop()
        vc.play(discord.FFmpegPCMAudio(path), after=after_callback)
    except ClientException as e:
        logger.error(f'Error starting playback: {e}')
        await message.send('There was an error starting playback. Please try again.')



@radio.command(aliases=['dc', 'leave', 'disconnect', 'quit','cancel'])
async def stop(message):
    # stop the music if it is playing and disconnect from the voice channel, do not join the channel after disconnecting
    if message.bot.voice_clients:
        vc = message.bot.voice_clients[0]
        if vc.is_paused():
            vc.resume()
            vc.stop()
            await vc.disconnect()
            await message.send("Stopped playing music")
            return
        
        if vc.is_playing():
            vc.stop()
            await vc.disconnect()
            await message.send("Stopped playing music")
        else:
            await message.send("Not playing music")
    return

@radio.command(aliases=['np', 'now'])
async def nowplaying(message):
    # check the current song that is playing
    if message.bot.voice_clients:
        vc = message.bot.voice_clients[0]
        if vc.is_playing():
            # await message.send(Abby.current_song)

            
            
            # get current unix time
            current_time = datetime.datetime.now().timestamp()

            # get time elapsed like this 0:34/3:45
            # get minutes elapsed
            minutes_elapsed = int((current_time - Abby.initial_playtime) / 60)
            # get seconds elapsed
            seconds_elapsed = int((current_time - Abby.initial_playtime) % 60)
            # get minutes total
            minutes_total = int(Abby.song_length / 60)
            # get seconds total
            seconds_total = int(Abby.song_length % 60)

            # format time elapsed
            if seconds_elapsed < 10:
                seconds_elapsed = f"0{seconds_elapsed}"
            if seconds_total < 10:
                seconds_total = f"0{seconds_total}"
            if minutes_elapsed < 10:
                minutes_elapsed = f"0{minutes_elapsed}"
            if minutes_total < 10:
                minutes_total = f"0{minutes_total}"

            # Calculate the progress percentage
            progress = ((current_time - Abby.initial_playtime) / Abby.song_length) * 100

            # Create a line with the song progress
            progress_line_length = 10  # Adjust this value to set the length of the line
            progress_line_position = int(progress_line_length * (progress / 100))
            progress_line = "—" * progress_line_position + "●" + "—" * (progress_line_length - progress_line_position - 1)

            progress_bar = f'~~{progress_line}~~'

            # Calculate time remaining
            minutes_remaining = int((Abby.song_length - (current_time - Abby.initial_playtime)) // 60)
            seconds_remaining = int((Abby.song_length - (current_time - Abby.initial_playtime)) % 60)

            # Handle negative time remaining
            if minutes_remaining < 0 or seconds_remaining < 0:
                minutes_remaining, seconds_remaining = 0, 0

            # Format time remaining
            if seconds_remaining < 10:
                seconds_remaining = f"0{seconds_remaining}"
            if minutes_remaining < 10:
                minutes_remaining = f"0{minutes_remaining}"

           


            embed = discord.Embed(
                title = f"{Abby.your_custom_emoji} Breeze Radio 88.8 FM 📻",
                color=0x00ff00,
                description = f'[{minutes_elapsed}:{seconds_elapsed}] {progress_bar} [-{minutes_remaining}:{seconds_remaining}]'
                )
            embed.add_field(
                name="Now Playing",
                value=f"{Abby.your_custom_emoji_2}: {Abby.current_song}",
                inline=True
            )
            


            # get bot avatar
            embed.set_thumbnail(
                url=message.bot.user.avatar
            )
            await message.channel.send(embed=embed)

            # playtime = f'{Abby.current_time_elapsed}'

            return

        else:
            await message.send("Not playing music")
    return

def getSongLengthInSeconds(path):
    audio = MP3(path)
    return int(audio.info.length)


@radio.command()
async def next(message):
    global skip_flag
    # play the next song in the queue
    if message.bot.voice_clients:
        vc = message.bot.voice_clients[0]
        if vc.is_playing() or vc.is_paused():
            vc.stop()
            skip_flag = True
            await play_next(message)
        else:
            await message.send("Not playing music")

@radio.command()
async def pause(message):
    # pause the music if it is playing
    if message.bot.voice_clients:
        vc = message.bot.voice_clients[0]
        if vc.is_playing():
            vc.pause()
            await message.send("Paused music")
        else:
            await message.send("Not playing music")
    return

@radio.command()
async def resume(message):
    # resume the music if it is paused
    if message.bot.voice_clients:
        vc = message.bot.voice_clients[0]
        if vc.is_paused():
            vc.resume()
            await message.send("Resumed music")
        else:
            await message.send("Not playing music")
    return


def setup(bot):
    bot.add_command(radio)



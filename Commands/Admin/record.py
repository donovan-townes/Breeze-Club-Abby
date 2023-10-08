from datetime import datetime
import subprocess
import discord
from discord.ext import commands
from discord.ext.commands import Group

from utils.log_config import logging, setup_logging
import os
from utils import audio_layer

setup_logging()
logger = logging.getLogger(__name__)

connections = {}
async def once_done(sink, channel, *args):
    """This function is called when the audio recording is finished."""
    recorded_users = [
        f"<@{user_id}>"
        for user_id in sink.audio_data.keys()
    ]

    # Check if the bot is playing audio in the channel
    if sink.vc.is_playing():
        # Do nothing, let the audio finish playing
        pass
    else:
        # Disconnect from the voice channel
        await sink.vc.disconnect()

    # Get the date and time as a string like this 2021-08-01_12-00pm
    date_time = datetime.now().strftime("%Y-%m-%d_%I-%M%p")

    # Create a directory to save the audio files if it doesn't exist
    save_directory = f"/home/Abby_BreezeClub/Audio_Recordings/{date_time}"
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)

    # Save individual user files
    saved_files = []
    for user_id, audio in sink.audio_data.items():
        # Generate a file path where the audio file will be saved
        file_path = os.path.join(save_directory, f"{user_id}.{sink.encoding}")
        with open(file_path, "wb") as file:
            file.write(audio.file.read())  # Save the audio file locally
        saved_files.append(file_path)

        #     # Send the actual audio file to the Discord channel
        # with open(file_path, 'rb') as fp:
        #     await channel.send("Here is an audio file:", file=discord.File(fp, f"{user_id}.{sink.encoding}"))

    await channel.send(f"Finished recording audio for: {', '.join(recorded_users)}.")
    # After saving the files, call the audio_layer function to combine them
    output_path = f"/home/Abby_BreezeClub/Audio_Recordings/{date_time}_COMBINED.wav"
    audio_layer.layer_wav_files(output_path, save_directory)
    logger.info(f"Finished combining audio files. Output path: {output_path}")

    # Send the combined audio file to the Discord channel
    with open(output_path, 'rb') as fp:
        await channel.send(f"Here is the combined audio file:", file=discord.File(fp, f"{date_time}_COMBINED.wav"))

async def backup_audio(channel):    
    """Backup the audio files to the backup server. Not Yet Implemented."""

    try:
        process = subprocess.Popen(["/bin/bash", "/home/Abby_BreezeClub/Backup/audio_recording.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            logger.error(f"Error executing backup.sh: {stderr.decode()}")
            await channel.send("Error backing up audio files.")
        else:
            logger.info("Backup script executed successfully!")
            await channel.send("Audio files have been backed up.")

    except Exception as e:
        logger.error(f"Error executing backup.sh: {e}")


def is_recording(guild_id):
    return guild_id in connections

@commands.group(invoke_without_command=True, aliases=["rec"])
@commands.has_permissions(administrator=True)
async def record(message):
    if is_recording(message.guild.id):
        await message.send("I am already recording in this guild. If you want to stop recording, use `!record stop`.")
        return
    
    voice = message.author.voice

    if not voice:
        await message.send("You aren't in a voice channel!")
        return

    vc = await voice.channel.connect()
    connections.update({message.guild.id: vc})

    vc.start_recording(
        discord.sinks.WaveSink(),
        once_done,
        message.channel
    )

    # create an embed to display whos recording and what channel and whos in the channel
    embed = discord.Embed(
        title=f"🔴 Recording in {voice.channel.name} 🎙️",
        color=0x00ff00
    )

    # add who's in the channel
    embed.add_field(
        name="Users in the channel",
        value=", ".join([f"<@{member.id}>" for member in voice.channel.members]),
        inline=False
    )

    # add thumbnail for the embed
    embed.set_thumbnail(
        url=message.bot.user.avatar
    )

    # set footer
    embed.set_footer(
        text=f"Recording started by {message.author}",
        icon_url=message.author.avatar
    )
    await message.send(embed=embed)

@record.command(aliases=["done"])
async def stop(message):
    if message.guild.id in connections:
        vc = connections[message.guild.id]
        vc.stop_recording()
        del connections[message.guild.id]
    else:
        await message.send("I am currently not recording here.")

# This event will be triggered when the has_any_role check fails.
@record.error
async def record_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send(f"You don't have the required role/permission to use this command.")

def setup(bot):
    bot.add_command(record)
from discord.ext import commands
import os
from datetime import datetime
import asyncio
from discord.ext.commands import BucketType
import re

@commands.command()
@commands.has_role(802692693078573097)  # Admin Only
# @commands.cooldown(1, 60, BucketType.user)  # Cooldown
async def update(message):
    client = message.bot
    channel = message
    author = message.author.display_name
    # ask for update type
    await channel.send('Please provide the update type (major/minor):')
    try:
        msg = await client.wait_for(
            'message',
            timeout=60.0*5,
            check=lambda message: message.author == message.author
        )
        if msg:
            update_type = msg.content.lower()  # this will get the update type from user
            if update_type not in ['major', 'minor']:  # If user enters something other than 'major' or 'minor'
                return await channel.send('Update type should be either "major" or "minor". Update logging cancelled.')
            if update_type == 'cancel':  # If user enters 'cancel'
                return await channel.send('Update logging cancelled by user.')
    except asyncio.TimeoutError:
        return await channel.send('Sorry, you took too long. Update logging cancelled.')

    # ask for version number, if nothing is provided, default to "latest"
    await channel.send('Please provide the version number (e.g. 1.0.0):')
    try:
        msg = await client.wait_for(
            'message',
            timeout=60.0*5,
            check=lambda message: message.author == message.author
        )
        if msg:
            version = msg.content.lower() 
            if version == 'cancel':  # If user enters 'cancel'
                return await channel.send('Update logging cancelled by user.')
            if version == '':  # If user enters nothing
                version = 'latest'
            # Check if version number is valid
            if not re.match(r'^\d+(\.\d+){0,2}$', version):
                return await channel.send('Version number is invalid. Update logging cancelled.')
            
    except asyncio.TimeoutError:
        return await channel.send('Sorry, you took too long. Update logging cancelled.')
    

    # ask for update content
    await channel.send('Please provide the update content:')
    try:
        msg = await client.wait_for(
            'message',
            timeout=60.0*7,
            check=lambda message: message.author == message.author
        )
        if msg:
            update_content = msg.content  # this will get the update content from user
            if update_content.lower() == 'cancel':  # If user enters 'cancel'
                return await channel.send('Update logging cancelled by user.')
    except asyncio.TimeoutError:
        return await channel.send('📒 Sorry, you took too long. Update logging cancelled.')

    # Here call the function to write update to a file
    write_update_log(update_content, update_type, version ,author)

    await channel.send(f'📒 Update logged successfully!')


def write_update_log(update_content, author, update_type="minor", version="latest",dir_path="logs"):
    # Ensure directory exists
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    # Define file name
    if version == "latest":
        # If New Version, create a new file for the version, if latest - retrieve the latest version
        files = [f for f in os.listdir(dir_path) if f.endswith('.md')]
        files.sort()
        if files:  # If there are existing files
            file_name = files[-1]  # Take the last (most recent) one
            # Check if the latest version is the same as the current version
            if re.search(r'## Version: (.*)', open(os.path.join(dir_path, file_name), 'r').read()).group(1) == version:
                # If the latest version is the same as the current version, append to the latest version
                file_path = os.path.join(dir_path, file_name)
            else:
                # If the latest version is not the same as the current version, create a new file
                file_name = f"Update_Log-Version-{version}" + ".md"
                file_path = os.path.join(dir_path, file_name)
        else:  # If there are no existing files
            file_name = f"Update_Log-Version-{version}" + ".md"
    # Append the update content with timestamp
    with open(file_path, "a") as f:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"---## Version: {version}\n Type: {update_type}\n**Update Log**\n at {now}\n by {author}:\n\n{update_content}\n**END LOG**\n---\n")

@update.error
async def update_log_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("You don't have the required role to use this command!")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f'Cooldown still active, please wait {error.retry_after:.0f} seconds.')

def setup(bot):
    bot.add_command(update)

from discord.ext import commands
from abby_adapters.discord.cogs.Twitch.twitch import handle_live_command, handle_add_twitch_command
from discord.ext import commands

@commands.command()
async def addtwitch(message, *args):
    await handle_add_twitch_command(message, args)
    return

addtwitch.description = '''
**Usage** `!addtwitch @<user> (Twitch Handle)`

Adds a user's twitch handle to their user database

(Authorized users only!)
'''

@commands.command()
async def addlive(message, user_id):
    user_id = user_id
    await message.channel.send("Adding User to Live-Watch Database (NOT IMPLEMENTED YET)")
    # user_database.insert[user_id]
    
    
@commands.command()
async def live(message, *args):
    await handle_live_command(message, args)
    return

live.description = '''
**Usage:** `!live @<user>`

Checks if the user mentioned is live (must have a Profile in database)
If so it will link their twitch channel.


'''


def setup(bot):
    bot.add_command(live)
    bot.add_command(addtwitch)

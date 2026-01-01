from discord.ext import commands, tasks
from abby_core.observability.logging import logging, setup_logging
from abby_core.database.mongodb import *

setup_logging()
logger = logging.getLogger(__name__)

class Calender(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.calender = self.get_calender()
        self.calender.start()

    @tasks.loop(seconds=10.0)
    async def calender(self):
        # Check if there is a new event
        event = self.calender.find_one({"event": True})
        if event:
            # Check if the event is already announced
            if not event["announced"]:
                # Announce the event
                channel = self.bot.get_channel(event["channel_id"])
                await channel.send(f"Event: {event['title']} is happening on {event['date']} at {event['time']}")
                # Update the event to be announced
                self.calender.update_one({"_id": event["_id"]}, {"$set": {"announced": True}})
                logger.info(f"[📅] Announced event {event['title']}")
            else:
                logger.info(f"[📅] Event {event['title']} already announced")

    @commands.group(name="calender", aliases=["calendar"], invoke_without_command=True)
    async def calender_group(self, ctx):
        """Calender commands"""
        await ctx.send_help(ctx.command)

    @calender_group.command(name="add")
    async def add_event(self, ctx, title, date, time):
        """Add an event to the calender"""
        # Check if the user has the manage_guild permission
        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send("You do not have the manage_guild permission")
            return

        # Check if the date is valid
        try:
            datetime.strptime(date, "%d/%m/%Y")
        except ValueError:
            await ctx.send("Invalid date format. Please use dd/mm/yyyy")
            return

        # Check if the time is valid
        try:
            datetime.strptime(time, "%H:%M")
        except ValueError:
            await ctx.send("Invalid time format. Please use hh:mm")
            return

        # Check if the event already exists
        event = self.calender.find_one({"title": title})
        if event:
            await ctx.send("Event already exists")
            return

        # Add the event
        self.calender.insert_one({"title": title, "date": date, "time": time, "event": True, "announced": False, "channel_id": ctx.channel.id})
        await ctx.send(f"Added event {title} on {date} at {time}")
        logger.info(f"[📅] Added event {title} on {date} at {time}")

    @calender_group.command(name="remove")
    async def remove_event(self, ctx, title):
        """Remove an event from the calender"""
        # Check if the user has the manage_guild permission
        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send("You do not have the manage_guild permission")
            return
        # Check if the event exists
        event = self.calender.find_one({"title": title})
        if event:
            await ctx.send("Event does not exist")
            return
        # Remove the event
        else:
            self.calender.delete_one({"title": title})
            await ctx.send(f"Removed event {title}")
            logger.info(f"[📅] Removed event {title}")
    
    @calender_group.command(name="list")
    async def list_events(self, ctx):
        """List all events"""
        events = self.calender.find({"event": True})
        event_list = []
        for event in events:
            event_list.append(event["title"])
        await ctx.send(f"Events: {', '.join(event_list)}")
       
    def get_calender(self):
        db = connect_to_mongodb()
        return db["Abby_Calender"]
    
    

def setup(bot):
    bot.add_cog(Calender(bot))


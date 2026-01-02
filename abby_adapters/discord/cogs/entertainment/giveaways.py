"""
Modern Giveaway System with Discord Native UI

Replaces the old prefix-based giveaway system with a modern slash command
implementation using Modals for input and Buttons for participation.

Features:
- /giveaway create - Create giveaway with Modal UI
- /giveaway end - Manually end a giveaway
- /giveaway list - View active giveaways
- Button-based participation (no more reactions!)
- Automatic winner selection
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput, View, Button
from abby_core.observability.logging import setup_logging, logging
from abby_core.database.mongodb import connect_to_mongodb
from datetime import datetime, timedelta
from typing import Optional
import random

setup_logging()
logger = logging.getLogger(__name__)


class GiveawayModal(Modal):
    """Modal for creating a giveaway."""
    
    def __init__(self):
        super().__init__(title="Create a Giveaway", timeout=300)
        
        self.prize = TextInput(
            label="Prize",
            placeholder="What are you giving away?",
            style=discord.TextStyle.short,
            max_length=100,
            required=True
        )
        
        self.duration = TextInput(
            label="Duration (in minutes)",
            placeholder="e.g., 60 for 1 hour, 1440 for 1 day",
            style=discord.TextStyle.short,
            max_length=10,
            default="60",
            required=True
        )
        
        self.description = TextInput(
            label="Description (Optional)",
            placeholder="Add details about the giveaway...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        )
        
        self.winner_count = TextInput(
            label="Number of Winners",
            placeholder="How many winners? (default: 1)",
            style=discord.TextStyle.short,
            max_length=2,
            default="1",
            required=False
        )
        
        self.add_item(self.prize)
        self.add_item(self.duration)
        self.add_item(self.description)
        self.add_item(self.winner_count)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        await interaction.response.defer()


class GiveawayView(View):
    """View with Enter button for giveaway participation."""
    
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)  # Persistent view
        self.giveaway_id = giveaway_id
        self.participants = set()
    
    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.green, custom_id="enter_giveaway")
    async def enter_button(self, interaction: discord.Interaction, button: Button):
        """Handle giveaway entry."""
        user_id = str(interaction.user.id)
        
        # Check if already entered
        if user_id in self.participants:
            await interaction.response.send_message(
                "✅ You're already entered in this giveaway!",
                ephemeral=True
            )
            return
        
        # Add participant to database
        try:
            client = connect_to_mongodb()
            db = client["Abby_Database"]
            collection = db["giveaways"]
            
            collection.update_one(
                {"_id": self.giveaway_id},
                {"$addToSet": {"participants": user_id}}
            )
            
            self.participants.add(user_id)
            
            # Update button label with participant count
            button.label = f"🎉 Enter Giveaway ({len(self.participants)} entries)"
            await interaction.message.edit(view=self)
            
            await interaction.response.send_message(
                "🎉 You've been entered into the giveaway! Good luck!",
                ephemeral=True
            )
            
            logger.info(f"[🎁] {interaction.user} entered giveaway {self.giveaway_id}")
            
        except Exception as e:
            logger.error(f"[🎁] Error entering giveaway: {e}")
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.",
                ephemeral=True
            )


class GiveawayCommands(commands.GroupCog, name="giveaway"):
    """Giveaway management system."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_giveaways = {}
        logger.info("[🎁] Modern Giveaway system loaded")
        
        # Start background task to check for ending giveaways
        self.check_giveaways.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.check_giveaways.cancel()
    
    @app_commands.command(name="create", description="Create a new giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create_giveaway(self, interaction: discord.Interaction):
        """Create a giveaway with Modal UI."""
        modal = GiveawayModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        # Parse inputs
        try:
            prize = modal.prize.value
            duration_minutes = int(modal.duration.value)
            description = modal.description.value or ""
            winner_count = int(modal.winner_count.value or "1")
            
            if duration_minutes <= 0:
                await interaction.followup.send("❌ Duration must be greater than 0.", ephemeral=True)
                return
            
            if winner_count <= 0 or winner_count > 20:
                await interaction.followup.send("❌ Winner count must be between 1 and 20.", ephemeral=True)
                return
            
        except ValueError:
            await interaction.followup.send(
                "❌ Invalid input. Please enter valid numbers for duration and winner count.",
                ephemeral=True
            )
            return
        
        # Calculate end time
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        # Create giveaway document
        client = connect_to_mongodb()
        db = client["Abby_Database"]
        collection = db["giveaways"]
        
        giveaway_data = {
            "prize": prize,
            "description": description,
            "channel_id": str(interaction.channel_id),
            "guild_id": str(interaction.guild_id),
            "host_id": str(interaction.user.id),
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": duration_minutes,
            "winner_count": winner_count,
            "participants": [],
            "winners": [],
            "active": True,
            "message_id": None
        }
        
        result = collection.insert_one(giveaway_data)
        giveaway_id = str(result.inserted_id)
        
        # Create embed
        embed = self._create_giveaway_embed(
            prize, description, end_time, winner_count, interaction.user, 0
        )
        
        # Create view with enter button
        view = GiveawayView(giveaway_id)
        
        # Send giveaway message
        channel = interaction.channel
        message = await channel.send("🎉 **GIVEAWAY TIME!** 🎉", embed=embed, view=view)
        
        # Update database with message ID
        collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"message_id": str(message.id)}}
        )
        
        # Store in active giveaways
        self.active_giveaways[giveaway_id] = {
            "message": message,
            "view": view,
            "end_time": end_time
        }
        
        # Confirm to creator
        await interaction.followup.send(
            f"✅ Giveaway created! It will end <t:{int(end_time.timestamp())}:R>",
            ephemeral=True
        )
        
        logger.info(f"[🎁] {interaction.user} created giveaway: {prize} (ID: {giveaway_id})")
    
    def _create_giveaway_embed(self, prize: str, description: str, end_time: datetime, 
                               winner_count: int, host: discord.User, participant_count: int) -> discord.Embed:
        """Create embed for giveaway."""
        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=f"**Prize:** {prize}",
            color=discord.Color.gold(),
            timestamp=end_time
        )
        
        if description:
            embed.add_field(name="Description", value=description, inline=False)
        
        embed.add_field(
            name="📊 Info",
            value=f"**Winners:** {winner_count}\n**Entries:** {participant_count}",
            inline=True
        )
        
        embed.add_field(
            name="⏰ Ends",
            value=f"<t:{int(end_time.timestamp())}:R>",
            inline=True
        )
        
        embed.set_footer(text=f"Hosted by {host.display_name}", icon_url=host.avatar.url if host.avatar else None)
        
        return embed
    
    @app_commands.command(name="end", description="Manually end a giveaway")
    @app_commands.describe(message_id="The message ID of the giveaway to end")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def end_giveaway(self, interaction: discord.Interaction, message_id: str):
        """Manually end a giveaway."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Find giveaway in database
            client = connect_to_mongodb()
            db = client["Abby_Database"]
            collection = db["giveaways"]
            
            giveaway = collection.find_one({
                "message_id": message_id,
                "active": True,
                "guild_id": str(interaction.guild_id)
            })
            
            if not giveaway:
                await interaction.followup.send("❌ Giveaway not found or already ended.", ephemeral=True)
                return
            
            # End the giveaway
            await self._end_giveaway(str(giveaway["_id"]))
            
            await interaction.followup.send("✅ Giveaway ended!", ephemeral=True)
            
        except Exception as e:
            logger.error(f"[🎁] Error ending giveaway: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="list", description="List active giveaways")
    async def list_giveaways(self, interaction: discord.Interaction):
        """List all active giveaways in the server."""
        client = connect_to_mongodb()
        db = client["Abby_Database"]
        collection = db["giveaways"]
        
        giveaways = list(collection.find({
            "guild_id": str(interaction.guild_id),
            "active": True
        }))
        
        if not giveaways:
            await interaction.response.send_message(
                "📭 No active giveaways in this server.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🎉 Active Giveaways",
            color=discord.Color.gold()
        )
        
        for giveaway in giveaways[:10]:  # Limit to 10
            end_time = giveaway["end_time"]
            embed.add_field(
                name=f"🎁 {giveaway['prize']}",
                value=f"Ends <t:{int(end_time.timestamp())}:R>\n"
                      f"Entries: {len(giveaway.get('participants', []))}\n"
                      f"[Jump to Message](https://discord.com/channels/{giveaway['guild_id']}/{giveaway['channel_id']}/{giveaway['message_id']})",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _end_giveaway(self, giveaway_id: str):
        """End a giveaway and select winners."""
        client = connect_to_mongodb()
        db = client["Abby_Database"]
        collection = db["giveaways"]
        
        giveaway = collection.find_one({"_id": giveaway_id})
        if not giveaway or not giveaway.get("active"):
            return
        
        participants = giveaway.get("participants", [])
        winner_count = giveaway.get("winner_count", 1)
        
        # Select winners
        if len(participants) == 0:
            winners = []
        else:
            winners = random.sample(participants, min(len(participants), winner_count))
        
        # Update database
        collection.update_one(
            {"_id": giveaway_id},
            {"$set": {"active": False, "winners": winners}}
        )
        
        # Update message
        try:
            channel = self.bot.get_channel(int(giveaway["channel_id"]))
            if channel:
                message = await channel.fetch_message(int(giveaway["message_id"]))
                
                # Create ended embed
                embed = discord.Embed(
                    title="🎉 GIVEAWAY ENDED 🎉",
                    description=f"**Prize:** {giveaway['prize']}",
                    color=discord.Color.red()
                )
                
                if winners:
                    winner_mentions = [f"<@{winner}>" for winner in winners]
                    embed.add_field(
                        name="🏆 Winners",
                        value="\n".join(winner_mentions),
                        inline=False
                    )
                    
                    # Announce winners
                    await channel.send(
                        f"🎊 Congratulations {', '.join(winner_mentions)}! You won **{giveaway['prize']}**!"
                    )
                else:
                    embed.add_field(
                        name="❌ No Winners",
                        value="Not enough participants!",
                        inline=False
                    )
                
                embed.add_field(
                    name="📊 Participants",
                    value=str(len(participants)),
                    inline=True
                )
                
                # Remove the view (disable button)
                await message.edit(embed=embed, view=None)
                
                logger.info(f"[🎁] Giveaway ended: {giveaway['prize']} - {len(winners)} winners selected")
        
        except Exception as e:
            logger.error(f"[🎁] Error updating ended giveaway message: {e}")
        
        # Remove from active giveaways
        if giveaway_id in self.active_giveaways:
            del self.active_giveaways[giveaway_id]
    
    @tasks.loop(minutes=1)
    async def check_giveaways(self):
        """Check for giveaways that need to be ended."""
        client = connect_to_mongodb()
        db = client["Abby_Database"]
        collection = db["giveaways"]
        
        # Find giveaways that have ended
        now = datetime.utcnow()
        ended_giveaways = collection.find({
            "active": True,
            "end_time": {"$lte": now}
        })
        
        for giveaway in ended_giveaways:
            await self._end_giveaway(str(giveaway["_id"]))
    
    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        """Wait for bot to be ready before starting task."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    """Add cog to bot."""
    await bot.add_cog(GiveawayCommands(bot))
    logger.info("[🎁] Modern Giveaway system loaded successfully")

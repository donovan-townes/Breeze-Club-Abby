"""
Modern Giveaway System with Discord Native UI

Consolidates all giveaway operations under a single `/giveaway` nexus command with
a landing panel that routes to Create, View, and End operations.

Features:
- /giveaway - Main landing panel (shows status, entry points)
- Create Modal (button-triggered)
- View Active Giveaways (button-triggered, linked)
- End Giveaway (button-triggered, permission-gated)
- Button-based participation (no more reactions!)
- Automatic winner selection
"""


import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Button
from tdos_intelligence.observability import logging
from abby_core.database.collections.giveaways import get_collection as get_giveaways_collection
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import random

logger = logging.getLogger(__name__)


class GiveawayLandingPanel(discord.ui.View):
    """Landing panel for giveaway management - shows status and action buttons."""

    def __init__(self, guild_id: int, bot: commands.Bot):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.bot = bot

    @staticmethod
    async def get_giveaway_stats(guild_id: int) -> tuple[int, int, int]:
        """Get active, ending soon, and completed giveaway counts."""
        try:
            collection = get_giveaways_collection()
            now = datetime.utcnow()
            soon = now + timedelta(hours=1)

            active = collection.count_documents({
                "guild_id": str(guild_id),
                "active": True,
                "end_time": {"$gt": soon}
            })

            ending_soon = collection.count_documents({
                "guild_id": str(guild_id),
                "active": True,
                "end_time": {"$lte": soon, "$gte": now}
            })

            completed = collection.count_documents({
                "guild_id": str(guild_id),
                "active": False
            })

            return active, ending_soon, completed
        except Exception as e:
            logger.error(f"[🎁] Error getting giveaway stats: {e}")
            return 0, 0, 0

    async def build_embed(self) -> discord.Embed:
        """Build landing panel embed with current status."""
        active, ending_soon, completed = await self.get_giveaway_stats(self.guild_id)

        embed = discord.Embed(
            title="🎉 Giveaways",
            description="Manage all giveaway operations from here.",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="📊 Status",
            value=f"🟢 **Active:** {active}\n⚠️ **Ending Soon:** {ending_soon}\n✅ **Completed:** {completed}",
            inline=False
        )

        embed.add_field(
            name="🎯 Actions",
            value="Use the buttons below to create, view, or manage giveaways.",
            inline=False
        )

        embed.set_footer(text="Use channel permissions to control who can create giveaways")
        return embed

    @discord.ui.button(label="Create Giveaway", style=discord.ButtonStyle.green, emoji="➕", row=0)
    async def button_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open giveaway creation modal."""
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need manage guild permissions to create giveaways.",
                ephemeral=True
            )
            return

        modal = GiveawayModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="View Active", style=discord.ButtonStyle.primary, emoji="📋", row=0)
    async def button_view(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show active giveaways."""
        try:
            collection = get_giveaways_collection()

            giveaways = list(collection.find({
                "guild_id": str(interaction.guild_id),
                "active": True
            }).sort("end_time", 1).limit(10))

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

            for giveaway in giveaways:
                end_time = giveaway["end_time"]
                embed.add_field(
                    name=f"🎁 {giveaway['prize']}",
                    value=f"Ends <t:{int(end_time.timestamp())}:R>\n"
                          f"Entries: {len(giveaway.get('participants', []))}\n"
                          f"[Jump to Message](https://discord.com/channels/{giveaway['guild_id']}/{giveaway['channel_id']}/{giveaway['message_id']})",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[🎁] Error listing giveaways: {e}")
            await interaction.response.send_message("❌ Error loading giveaways.", ephemeral=True)

    @discord.ui.button(label="End Giveaway", style=discord.ButtonStyle.red, emoji="⏹️", row=0)
    async def button_end(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Trigger end giveaway modal (permission-gated)."""
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need manage guild permissions to end giveaways.",
                ephemeral=True
            )
            return

        modal = EndGiveawayModal()
        await interaction.response.send_modal(modal)


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
        """Handle modal submission - create the giveaway."""
        await interaction.response.defer(ephemeral=True)

        # Parse inputs
        try:
            prize = self.prize.value
            duration_minutes = int(self.duration.value)
            description = self.description.value or ""
            winner_count = int(self.winner_count.value or "1")

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
        collection = get_giveaways_collection()

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
        embed = GiveawayView.create_giveaway_embed(
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

        # Confirm to creator
        await interaction.followup.send(
            f"✅ Giveaway created! It will end <t:{int(end_time.timestamp())}:R>",
            ephemeral=True
        )

        logger.info(f"[🎁] {interaction.user} created giveaway: {prize} (ID: {giveaway_id})")


class EndGiveawayModal(Modal):
    """Modal for ending a giveaway by message ID."""

    def __init__(self):
        super().__init__(title="End a Giveaway", timeout=300)

        self.message_id = TextInput(
            label="Giveaway Message ID",
            placeholder="Paste the message ID of the giveaway to end",
            style=discord.TextStyle.short,
            max_length=20,
            required=True
        )

        self.add_item(self.message_id)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission - end the giveaway."""
        await interaction.response.defer(ephemeral=True)

        try:
            message_id = self.message_id.value

            # Find giveaway in database
            collection = get_giveaways_collection()

            giveaway = collection.find_one({
                "message_id": message_id,
                "active": True,
                "guild_id": str(interaction.guild_id)
            })

            if not giveaway:
                await interaction.followup.send("❌ Giveaway not found or already ended.", ephemeral=True)
                return

            # End the giveaway
            cog = interaction.client.get_cog("GiveawayManager")
            if cog:
                await cog._end_giveaway(str(giveaway["_id"]))
                await interaction.followup.send("✅ Giveaway ended!", ephemeral=True)
            else:
                await interaction.followup.send("❌ Giveaway system unavailable.", ephemeral=True)

        except Exception as e:
            logger.error(f"[🎁] Error ending giveaway: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


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
            collection = get_giveaways_collection()

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

    @staticmethod
    def create_giveaway_embed(prize: str, description: str, end_time: datetime,
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


class GiveawayManager(commands.Cog):
    """Giveaway management system - consolidated under /giveaway."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_giveaways = {}
        logger.debug("[🎁] Giveaway system loaded")

    def cog_unload(self):
        """Clean up when cog is unloaded."""
        pass

    @app_commands.command(name="giveaway", description="Manage giveaways (view status, create, end)")
    async def giveaway_landing(self, interaction: discord.Interaction):
        """Show giveaway landing panel with status and action buttons."""
        view = GiveawayLandingPanel(interaction.guild_id, self.bot)
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    async def _end_giveaway(self, giveaway_id: str):
        """End a giveaway and select winners."""
        collection = get_giveaways_collection()

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

    async def check_giveaways_tick(self):
        """Platform scheduler entrypoint to close giveaways."""
        from abby_core.database.mongodb import is_mongodb_available

        if not is_mongodb_available():
            logger.warning("[🎁] Skipping giveaway check: MongoDB unavailable")
            return

        loop = asyncio.get_event_loop()

        def fetch_ended_giveaways():
            collection = get_giveaways_collection()
            now = datetime.utcnow()
            return list(collection.find({
                "active": True,
                "end_time": {"$lte": now}
            }))

        try:
            ended_giveaways = await loop.run_in_executor(None, fetch_ended_giveaways)
            for giveaway in ended_giveaways:
                await self._end_giveaway(str(giveaway["_id"]))
        except Exception as e:
            logger.error(f"[🎁] Error checking giveaways: {e}")


async def setup(bot: commands.Bot):
    """Add cog to bot."""
    await bot.add_cog(GiveawayManager(bot))


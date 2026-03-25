from discord.ext import commands
from discord import app_commands
import discord
import datetime
import asyncio
from dateutil import parser
from bson import ObjectId
from tdos_intelligence.observability import logging
from abby_core.discord.config import BotConfig
from discord.ui import RoleSelect
from typing import Optional, List, Tuple, Any
from abby_core.database.collections.guild_configuration import get_guild_config
from abby_core.services.content_delivery import (
    create_announcement_for_delivery,
    mark_announcement_generated,
    mark_announcement_generation_failed,
    queue_announcement_for_delivery,
    deliver_announcement_to_discord,
)
from abby_core.services.dlq_service import get_dlq_service
from abby_core.services.conversation_service import get_conversation_service
from abby_core.llm.context_factory import build_conversation_context

logger = logging.getLogger(__name__)
config = BotConfig()


class Announcements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = bot
        self.logger = logger
        self.EMOJI = config.emojis.abby_run

    async def _get_target_channel(self, interaction: discord.Interaction) -> Optional[discord.TextChannel]:
        cfg = get_guild_config(interaction.guild_id) if interaction.guild_id else None
        if not cfg:
            return None
        # Get announcement channel from nested config structure
        channel_id = cfg.get("channels", {}).get("announcements", {}).get("id")
        channel = self.bot.get_channel(channel_id) if channel_id else None
        if channel is None and isinstance(interaction.channel, discord.TextChannel):
            channel = interaction.channel
        if channel and isinstance(channel, discord.TextChannel):
            return channel
        return None

    def _format_datetime_strings(self, dt: datetime.datetime) -> Tuple[str, str]:
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    
    async def _generate_announcement_background(self, announcement_id: str, guild_id: int, title: str, description: str, operator_id: str | None = None) -> None:
        """Generate LLM message for announcement in background (non-blocking)."""
        try:
            if logger:
                logger.debug(f"[📢] Generating LLM message for announcement {announcement_id}")
            
            # Build LLM prompt (broadcast-style)
            prompt = (
                "Take this announcement and enhance it with personality, enthusiasm, and clarity for broadcast. "
                "Keep it concise (under 200 words), avoid chatty back-and-forth tone, and preserve any explicit "
                "calls-to-action or key details. Do NOT invent or add any extra information such as dates, times, or locations.\n\n"
                f"ANNOUNCEMENT:\n{title}: {description}"
            )
            
            # Build conversation context with guild name
            try:
                guild = self.bot.get_guild(guild_id)
                guild_name = guild.name if guild else None
            except Exception:
                guild_name = None
            
            context = build_conversation_context(
                user_id=f"user:{operator_id}" if operator_id else "system:scheduled-announcer",
                guild_id=guild_id,
                guild_name=guild_name,
                user_name="Announcer",
                chat_history=[]
            )
            
            # Generate enhanced message WITH TIMEOUT (30 seconds)
            # Prevents hanging announcements from blocking scheduler
            conversation_service = get_conversation_service()
            try:
                enhanced, error = await asyncio.wait_for(
                    conversation_service.generate_response(prompt, context, max_tokens=300),
                    timeout=30.0  # 30-second timeout for generation
                )
                if error:
                    raise Exception(error)
            except asyncio.TimeoutError:
                # Generation timeout - route to DLQ for manual review
                dlq_service = get_dlq_service()
                
                logger.warning(
                    f"[⏱️ announcement_timeout] GENERATION_TIMEOUT "
                    f"id={announcement_id} "
                    f"guild={guild_id} "
                    f"timeout_seconds=30"
                )
                
                # Mark announcement as failed via unified pipeline
                mark_announcement_generation_failed(
                    item_id=announcement_id,
                    error_message="Generation timeout (exceeded 30s)",
                    operator_id=f"user:{operator_id}" if operator_id else "system:scheduled-announcer"
                )
                
                # Route to DLQ for retry/manual handling (need to get item details)
                from abby_core.services.content_delivery import get_content_delivery_collection
                collection = get_content_delivery_collection()
                item = collection.find_one({"_id": ObjectId(announcement_id)})
                if item:
                    dlq_service.route_error(
                        announcement_id=announcement_id,
                        error_type=asyncio.TimeoutError,
                        error_message="Generation timeout (exceeded 30s)",
                        guild_id=guild_id,
                        operator_id=f"user:{operator_id}" if operator_id else "system:scheduled-announcer",
                        context={
                            "timeout_seconds": 30,
                            "trigger_type": item.get("trigger_type", "unknown"),
                        }
                    )
        
        except asyncio.CancelledError:
            logger.info(f"[📢] Announcement generation cancelled: {announcement_id}")
            raise
        except Exception as e:
            logger.error(f"[📢] Failed to generate LLM message for {announcement_id}: {e}", exc_info=True)
            
            # Route to DLQ on any other error
            try:
                dlq_service = get_dlq_service()
                
                mark_announcement_generation_failed(
                    item_id=announcement_id,
                    error_message=str(e)[:200],
                    operator_id=f"user:{operator_id}" if operator_id else "system:scheduled-announcer"
                )
                
                dlq_service.route_error(
                    announcement_id=announcement_id,
                    error_type=type(e),
                    error_message=str(e)[:200],
                    guild_id=guild_id,
                    operator_id=f"user:{operator_id}" if operator_id else "system:scheduled-announcer",
                    context={
                        "error_type_name": type(e).__name__,
                    }
                )
            except Exception as dlq_error:
                logger.error(f"[📢] Failed to route announcement {announcement_id} to DLQ: {dlq_error}")

    async def post_announcement(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str, roles: Optional[List[discord.Role]] = None, silent: bool = False):
        author = interaction.user
        server_nickname = author.display_name
        author_icon = author.avatar.url if author.avatar else None

        embed = discord.Embed(title=title, description=message, color=0x00ff00)
        embed.set_author(name=server_nickname or author.display_name, icon_url=author_icon)
        
        # Combine mentions with embed send (no double-posting)
        content = None
        if not silent:
            mentions = " ".join(role.mention for role in roles) if roles else "@everyone"
            content = f"Attention {mentions}!"
        
        posted_message = await channel.send(content=content, embed=embed)

        try:
            await posted_message.add_reaction(self.EMOJI)
        except Exception:
            try:
                await posted_message.add_reaction("📣")
            except Exception:
                pass

        return posted_message

    @app_commands.command(name='announce', description='Create an announcement for the server')
    async def announce(self, interaction: discord.Interaction):
        # Step 1: Content modal (title + message)
        modal = StandardMessageModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        title = modal.title_value or 'Announcement'
        message = modal.message_value or ''

        # Step 2: Roles + type + schedule
        options = AnnounceOptions()
        option_msg = await interaction.followup.send('Select roles and timing', view=options, ephemeral=True)
        option_id = getattr(option_msg, "id", None)
        if option_id is None:
            return
        await options.wait()

        roles = options.roles
        schedule_mode = options.schedule
        scheduled_dt = options.scheduled_date
        announcement_type = options.announcement_type
        silent = options.silent

        channel = await self._get_target_channel(interaction)
        if channel is None:
            await interaction.followup.edit_message(
                message_id=option_id,
                content="No announcement channel configured and current channel not suitable. Please set announcement_channel_id in /config.",
                view=None
            )
            return

        if interaction.guild_id is None:
            await interaction.followup.edit_message(
                message_id=option_id,
                content="Guild context required to schedule announcements.",
                view=None
            )
            return

        if schedule_mode == "schedule" and not scheduled_dt:
            await interaction.followup.edit_message(message_id=option_id, content="No schedule time provided.", view=None)
            return

        embed_prev = discord.Embed(title=title, description=message)
        embed_prev.add_field(name='Channel', value=channel.mention)
        if silent:
            embed_prev.add_field(name='Mentions', value='Silent (no tags)')
        elif roles:
            embed_prev.add_field(name='Roles', value=" ".join(role.mention for role in roles))
        else:
            embed_prev.add_field(name='Mentions', value='@everyone')
        embed_prev.add_field(name='Type', value='Abby (LLM)' if announcement_type == 'abby' else 'Standard')
        if scheduled_dt:
            embed_prev.add_field(name='Scheduled Time', value=scheduled_dt.strftime('%B %d at %I:%M%p'))
        author_icon = interaction.user.avatar.url if interaction.user.avatar else None
        embed_prev.set_author(name=interaction.user.display_name, icon_url=author_icon)
        view = AnnouncementView()

        confirm_text = "schedule" if schedule_mode == "schedule" else "post"
        await interaction.followup.edit_message(
            message_id=option_id,
            content=f"Are you sure you want to {confirm_text} this announcement?",
            embed=embed_prev,
            view=view
        )
        await view.wait()

        if not view.value:
            await interaction.followup.edit_message(message_id=option_id, content='Announcement cancelled.', embed=None, view=None)
            return

        if schedule_mode == "schedule" and scheduled_dt:
            # Convert naive scheduled_dt to UTC (assumes user input is in guild's timezone)
            cfg = get_guild_config(interaction.guild_id) if interaction.guild_id else None
            timezone = cfg.get("scheduling", {}).get("timezone", "UTC") if cfg else "UTC"
            
            import pytz
            try:
                tz = pytz.timezone(timezone)
                # If scheduled_dt is naive, localize it to guild timezone, then convert to UTC
                if scheduled_dt.tzinfo is None:
                    scheduled_dt = tz.localize(scheduled_dt).astimezone(pytz.UTC).replace(tzinfo=None)
            except Exception as e:
                logger.warning(f"[📅] Failed to convert timezone for scheduled announcement: {e}")
                # Fallback: treat as UTC
                pass
            
            # Create scheduled announcement (unified pipeline with operator audit trail)
            announcement_id = create_announcement_for_delivery(
                guild_id=int(interaction.guild_id),
                title=title,
                description=message,
                delivery_channel_id=channel.id,
                delivery_roles=[role.id for role in roles] if roles else [],
                scheduled_at=scheduled_dt,
                operator_id=f"user:{interaction.user.id}",
                context={
                    "event_type": "world_announcement",
                    "trigger": "announce_command",
                },
            )
            if announcement_type == "standard":
                # Mark as generated for standard announcements (no LLM needed)
                mark_announcement_generated(
                    item_id=announcement_id,
                    generated_message=message,
                    operator_id=f"user:{interaction.user.id}"
                )
            await interaction.followup.edit_message(
                message_id=option_id,
                content=f"Scheduled for {scheduled_dt.strftime('%Y-%m-%d %H:%M %Z') or scheduled_dt}.",
                embed=None,
                view=None
            )
            return

        # Post now
        if announcement_type == "abby":
            # Queue for next scheduler tick (scheduler runs every minute)
            # Calculate next tick in guild timezone so date/time match scheduler comparisons
            cfg = get_guild_config(interaction.guild_id) if interaction.guild_id else None
            timezone = cfg.get("scheduling", {}).get("timezone", "UTC") if cfg else "UTC"

            import pytz
            try:
                tz = pytz.timezone(timezone)
            except Exception:
                tz = pytz.UTC

            now = datetime.datetime.now(tz)
            next_tick = now + datetime.timedelta(minutes=1)
            date_str, time_str = self._format_datetime_strings(next_tick)
            
            # Convert to UTC naive datetime for MongoDB storage
            next_tick_utc = next_tick.astimezone(pytz.UTC).replace(tzinfo=None)
            
            # Create announcement for next tick delivery (unified pipeline with operator audit trail)
            announcement_id = create_announcement_for_delivery(
                guild_id=int(interaction.guild_id),
                title=title,
                description=message,
                delivery_channel_id=channel.id,
                delivery_roles=[role.id for role in roles] if roles else [],
                scheduled_at=next_tick_utc,
                operator_id=f"user:{interaction.user.id}",
                context={
                    "event_type": "world_announcement",
                    "trigger": "announce_command",
                },
            )

            # Generate LLM message immediately in background (like operator world announcements)
            self.bot.loop.create_task(
                self._generate_announcement_background(announcement_id, int(interaction.guild_id), title, message, operator_id=str(interaction.user.id))
            )

            await interaction.followup.edit_message(
                message_id=option_id,
                content='✨ Generating announcement... Will post within the next 1-2 minutes.',
                embed=None,
                view=None
            )
        else:
            # Standard announcements post immediately (no LLM needed)
            # Use unified pipeline for full audit trail
            # Create announcement (unified pipeline with operator audit trail)
            item_id = create_announcement_for_delivery(
                guild_id=int(interaction.guild_id),
                title=title,
                description=message,
                delivery_channel_id=channel.id,
                delivery_roles=[role.id for role in roles] if roles else [],
                scheduled_at=datetime.datetime.utcnow(),
                operator_id=f"user:{interaction.user.id}",
                context={
                    "event_type": "world_announcement",
                    "trigger": "announce_command",
                },
            )
            operator_id = f"user:{interaction.user.id}"
            
            # Mark as generated
            mark_announcement_generated(
                item_id=item_id,
                generated_message=message,
                operator_id=operator_id
            )
            
            # Queue for delivery (generated -> queued)
            queue_announcement_for_delivery(
                item_id=item_id,
                operator_id=operator_id
            )
            
            # Post to Discord
            posted_message = await self.post_announcement(interaction, channel, title, message, roles, silent)
            
            # Mark as delivered with Discord message info
            if hasattr(interaction, 'guild') and interaction.guild and posted_message:
                deliver_announcement_to_discord(
                    item_id=item_id,
                    message_id=posted_message.id,
                    channel_id=channel.id,
                    operator_id=operator_id
                )
            
            await interaction.followup.edit_message(
                message_id=option_id,
                content='Announcement posted.',
                embed=None,
                view=None
            )


class StandardMessageModal(discord.ui.Modal, title="Create an announcement"):
    title_input = discord.ui.TextInput(label='Title', placeholder="Announcement Title (Optional)", required=False)
    message_input = discord.ui.TextInput(label='Message', placeholder="Message", style=discord.TextStyle.long)

    def __init__(self):
        super().__init__()
        self.title_value: Optional[str] = None
        self.message_value: Optional[str] = None

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.title_value = self.title_input.value
        self.message_value = self.message_input.value
        self.stop()

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
        logger.error(error)
        self.stop()

    async def on_timeout(self) -> None:
        self.stop()

    async def on_cancel(self, interaction: discord.Interaction) -> None:
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        self.title_value = self.title_input.value
        self.message_value = self.message_input.value
        return True


class AbbyMessageModal(discord.ui.Modal, title="Abby announcement"):
    message: Optional[str] = None
    message_input = discord.ui.TextInput(label='What should Abby announce?', placeholder="Details for Abby to announce", style=discord.TextStyle.long)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.message = self.message_input.value
        self.stop()

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
        logger.error(error)
        self.stop()

    async def on_timeout(self) -> None:
        self.stop()

    async def on_cancel(self, interaction: discord.Interaction) -> None:
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        self.message = self.message_input.value
        return True


class AnnounceOptions(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.schedule: str = "now"  # 'now' or 'schedule'
        self.scheduled_date: Optional[datetime.datetime] = None
        self.roles: List[discord.Role] = []
        self.announcement_type: str = "standard"
        self.silent: bool = False

    @discord.ui.select(placeholder='Announcement type', options=[
        discord.SelectOption(label='Standard Announcement', value='standard', description='Send as-is (no LLM)', emoji='📝'),
        discord.SelectOption(label='Abby Announcement', value='abby', description='Persona-injected (LLM)', emoji='🤖'),
    ])
    async def select_type(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.announcement_type = select.values[0]
        await interaction.response.defer()

    @discord.ui.select(cls=RoleSelect, placeholder='Notify roles? (Optional)', min_values=0, max_values=3)
    async def select_roles(self, interaction: discord.Interaction, select: RoleSelect):
        self.roles = list(select.values) if select.values else []
        await interaction.response.defer()

    @discord.ui.button(label='Silent (no tags)', style=discord.ButtonStyle.secondary, emoji='🔇', row=2)
    async def toggle_silent(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.silent = not self.silent
        if self.silent:
            button.style = discord.ButtonStyle.primary
            button.label = 'Silent ✓'
        else:
            button.style = discord.ButtonStyle.secondary
            button.label = 'Silent (no tags)'
        await interaction.response.edit_message(view=self)

    @discord.ui.select(placeholder='When to send?', options=[
        discord.SelectOption(label='Post it now!', value='now', description='Post announcement now', emoji='📣'),
        discord.SelectOption(label='Schedule it!', value='schedule', description='Schedule announcement', emoji='📅'),
    ])
    async def select_schedule(self, interaction: discord.Interaction, select: discord.ui.Select):
        choice = select.values[0]
        if choice == "schedule":
            modal = ScheduleInput()
            await interaction.response.send_modal(modal)
            await modal.wait()
            self.scheduled_date = modal.scheduled_time
        else:
            await interaction.response.defer()
        self.schedule = choice
        self.stop()


class AnnouncementView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value: Optional[bool] = None

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, emoji='☑️')
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red, emoji='✖️')
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()

    async def on_timeout(self) -> None:
        self.value = False
        self.stop()


class ScheduleInput(discord.ui.Modal, title="Schedule the announcement"):
    scheduled_time: Optional[datetime.datetime] = None
    scheduled_date_input = discord.ui.TextInput(label='Date and Time', placeholder="May 6 at 12:00 pm or `12:05am`")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            self.scheduled_time = parser.parse(self.scheduled_date_input.value)
        except Exception:
            self.scheduled_time = None
        self.stop()

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
        logger.error(error)
        self.scheduled_time = None
        self.stop()

    async def on_timeout(self) -> None:
        self.scheduled_time = None
        self.stop()

    async def on_cancel(self, interaction: discord.Interaction) -> None:
        self.scheduled_time = None
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        try:
            self.scheduled_time = parser.parse(self.scheduled_date_input.value)
            return True
        except Exception:
            self.scheduled_time = None
            return False


async def setup(bot):
    await bot.add_cog(Announcements(bot))

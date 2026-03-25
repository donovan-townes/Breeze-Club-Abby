"""
/operator - Bot Operator Control Panel

Consolidates high-power admin tools:
- XP management (add, remove, reset, init-all)
- Memory admin (stats, inspect, maintenance, purge)
- Conversation admin (clear_user, clear_guild, stats, toggle_storage)
- System tools (future: bot status, reload, etc.)

Permission-gated to OPERATOR_IDS from environment.
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from typing import Optional, Any, Dict, List
import os
import asyncio

from abby_core.services.memory_service_factory import create_discord_memory_service

get_db: Any = None
get_guild_setting: Any = None
set_guild_setting: Any = None
increment_xp: Any = None
get_xp: Any = None
get_level_from_xp: Any = None
initialize_xp: Any = None
logging: Any = None
memory: Any = None
run_maintenance: Any = None
create_memory_service: Any = None
ChatSessions: Any = None
backfill_schema_fields: Any = None

try:  # noqa: SIM105
    from abby_core.database.mongodb import get_db as _get_db  # type: ignore[attr-defined]
    from abby_core.database.collections.guild_configuration import get_guild_setting as _get_guild_setting, set_guild_setting as _set_guild_setting  # type: ignore[attr-defined]
    from abby_core.database.collections.chat_sessions import ChatSessions as _ChatSessions  # type: ignore[attr-defined]
    from abby_core.economy.xp import increment_xp as _increment_xp, get_xp as _get_xp, get_level_from_xp as _get_level_from_xp, initialize_xp as _initialize_xp  # type: ignore[attr-defined]
    from tdos_intelligence.observability import logging as _logging  # type: ignore[attr-defined]
    import tdos_intelligence.memory as memory  # type: ignore[attr-defined]
    from tdos_intelligence.maintenance import run_maintenance as _run_maintenance  # type: ignore[attr-defined]
    from tdos_intelligence.service import create_memory_service as _create_memory_service  # type: ignore[attr-defined]
    get_db = _get_db
    get_guild_setting = _get_guild_setting
    set_guild_setting = _set_guild_setting
    increment_xp = _increment_xp
    get_xp = _get_xp
    get_level_from_xp = _get_level_from_xp
    initialize_xp = _initialize_xp
    logging = _logging
    run_maintenance = _run_maintenance
    create_memory_service = _create_memory_service
    ChatSessions = _ChatSessions
except ImportError:
    pass

# Import backfill separately so it's not affected by tdos_intelligence import failures
try:
    from abby_core.database.collections.users import backfill_schema_fields as _backfill_schema_fields  # type: ignore[attr-defined]
    backfill_schema_fields = _backfill_schema_fields
except ImportError:
    pass

def _missing_dep(name: str):
    def _raiser(*args, **kwargs):
        raise RuntimeError(f"{name} not available")
    return _raiser

if get_db is None:
    get_db = _missing_dep("Database driver")
if increment_xp is None:
    increment_xp = _missing_dep("XP system")
if get_xp is None:
    get_xp = _missing_dep("XP system")
if get_level_from_xp is None:
    get_level_from_xp = _missing_dep("XP system")
if create_memory_service is None:
    create_memory_service = _missing_dep("Memory service")
if backfill_schema_fields is None:
    backfill_schema_fields = _missing_dep("User backfill system")
if run_maintenance is None:
    run_maintenance = _missing_dep("Memory maintenance")
if ChatSessions is None:
    ChatSessions = _missing_dep("Chat sessions collection")

logger = logging.getLogger(__name__) if logging else None


def _load_operator_ids() -> list[int]:
    """Load operator IDs from environment variable."""
    operator_ids_str = os.getenv("OPERATOR_IDS", "")
    if not operator_ids_str:
        return []
    try:
        return [int(id.strip()) for id in operator_ids_str.split(",") if id.strip()]
    except ValueError:
        if logger:
            logger.warning("Invalid OPERATOR_IDS format in .env")
        return []


OPERATOR_IDS = _load_operator_ids()


def is_operator(user_id: int) -> bool:
    """Check if user is a bot operator."""
    return user_id in OPERATOR_IDS


def _get_environment() -> str:
    """Detect runtime environment from ABBY_MODE or fallback to implicit local."""
    mode = os.getenv("ABBY_MODE", "").lower()
    if mode == "dev":
        return "dev"
    elif mode == "prod":
        return "prod"
    elif mode:
        return mode  # custom mode
    # No explicit mode set
    return "local (implicit)"


# ════════════════════════════════════════════════════════════════════════════════
# USER PICKERS & MODALS
# ════════════════════════════════════════════════════════════════════════════════

class AdjustXPModal(discord.ui.Modal):
    """Modal for adding or removing XP after selecting a user."""
    amount_input = discord.ui.TextInput(
        label="XP Amount",
        placeholder="Enter XP amount",
        required=True,
        max_length=10
    )

    def __init__(self, cog: "OperatorPanel", guild_id: int, target_user: discord.abc.User, action: str):
        title = "Add XP" if action == "add" else "Remove XP"
        super().__init__(title=title)
        self.cog = cog
        self.guild_id = guild_id
        self.target_user = target_user
        self.action = action

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.services.economy_service import get_economy_service
            
            amount = int(str(self.amount_input))
            if amount <= 0:
                await interaction.followup.send("❌ Amount must be positive.", ephemeral=True)
                return

            economy_service = get_economy_service()
            
            if self.action == "add":
                new_xp, new_level, success = economy_service.grant_xp(
                    self.target_user.id,
                    amount,
                    self.guild_id,
                    reason="operator_adjustment"
                )
                verb = "Added"
                preposition = "to"
            else:
                # For remove, grant negative XP
                new_xp, new_level, success = economy_service.grant_xp(
                    self.target_user.id,
                    -amount,
                    self.guild_id,
                    reason="operator_penalty"
                )
                verb = "Removed"
                preposition = "from"
            
            if not success:
                await interaction.followup.send("❌ Failed to adjust XP.", ephemeral=True)
                return

            user_name = getattr(self.target_user, "display_name", None) or getattr(self.target_user, "name", f"User {self.target_user.id}")

            await interaction.followup.send(
                f"✅ {verb} {amount:,} XP {preposition} {user_name}\n"
                f"New Total: {new_xp:,} XP (Level {new_level})",
                ephemeral=True
            )

            if logger:
                logger.info(f"[🔧] Operator {interaction.user.id} {verb.lower()} {amount} XP {preposition} {self.target_user.id}")

        except ValueError:
            await interaction.followup.send("❌ Please enter a valid number.", ephemeral=True)
        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to adjust XP: {e}")
            await interaction.followup.send(
                f"❌ Failed to update XP. Please try again. ({e})",
                ephemeral=True
            )


class ResetUserLevelModal(discord.ui.Modal):
    """Modal for collecting reason when resetting a user's level."""
    reason_input = discord.ui.TextInput(
        label="Reason for Level Reset",
        placeholder="e.g., Duplicate account, manual adjustment, etc.",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=200
    )

    def __init__(self, cog: "OperatorPanel", target_user: discord.abc.User):
        super().__init__(title="Reset User Level")
        self.cog = cog
        self.target_user = target_user

    async def on_submit(self, interaction: discord.Interaction):
        reason = str(self.reason_input).strip()
        if not reason:
            await interaction.response.send_message("❌ Reason is required.", ephemeral=True)
            return
        
        await self.cog.execute_user_level_reset(interaction, self.target_user, reason)


class ResetAllLevelsModal(discord.ui.Modal):
    """Modal for collecting reason when resetting all levels in a guild."""
    reason_input = discord.ui.TextInput(
        label="Reason for Guild Level Reset",
        placeholder="e.g., Test environment reset, policy change, cleanup",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=200,
    )

    def __init__(self, cog: "OperatorPanel"):
        super().__init__(title="Reset All Levels (Guild)")
        self.cog = cog


class BackfillUsersModal(discord.ui.Modal):
    """Modal for confirming user schema backfill operation."""
    confirm_input = discord.ui.TextInput(
        label="Type 'BACKFILL' to confirm",
        placeholder="BACKFILL",
        required=True,
        max_length=20,
    )

    def __init__(self, cog: "OperatorPanel"):
        super().__init__(title="Confirm User Schema Backfill")
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        confirm_text = str(self.confirm_input).strip().upper()
        if confirm_text != "BACKFILL":
            await interaction.followup.send(
                "❌ Confirmation text did not match. Operation cancelled.",
                ephemeral=True
            )
            return
        
        try:
            # Check if backfill function is actually available
            if not callable(backfill_schema_fields):
                await interaction.followup.send(
                    "❌ Backfill system not available (import failed)",
                    ephemeral=True
                )
                return
            
            # Audit log - who initiated backfill
            if logger:
                logger.warning(
                    f"[🔧 AUDIT] User Schema Backfill initiated by operator {interaction.user.name} "
                    f"(ID: {interaction.user.id}) from guild {interaction.guild_id}"
                )
            
            # Backfill all users - idempotent operation
            result: dict[str, int] = backfill_schema_fields()  # type: ignore[assignment]
            
            # Determine result status
            matched = result.get('matched', 0)
            modified = result.get('modified', 0)
            cooldowns_matched = result.get('cooldowns_matched', 0)
            cooldowns_modified = result.get('cooldowns_modified', 0)
            
            total_updates = modified + cooldowns_modified
            
            embed = discord.Embed(
                title="✅ User Profile Backfill Complete",
                description=(
                    "This operation is idempotent - safe to run multiple times.\n\n"
                    f"**Result:** {total_updates} user(s) updated"
                    + (" (0 means all users already have complete schema ✅)" if total_updates == 0 else "")
                ),
                color=discord.Color.green() if total_updates == 0 else discord.Color.blue()
            )
            embed.add_field(
                name="Schema Fields",
                value=(
                    f"Matched: {matched} | Modified: {modified}\n"
                    f"_(Matched = users missing any schema field)_"
                ),
                inline=False
            )
            embed.add_field(
                name="Cooldowns",
                value=(
                    f"Matched: {cooldowns_matched} | Modified: {cooldowns_modified}\n"
                    f"_(Matched = users missing cooldown fields)_"
                ),
                inline=False
            )
            embed.set_footer(text="Matched count shows users that needed updates. Zero is good!")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Audit log - completion with results
            if logger:
                logger.warning(
                    f"[🔧 AUDIT] User Schema Backfill completed by {interaction.user.name} "
                    f"(ID: {interaction.user.id}): schema={matched}/{modified}, "
                    f"cooldowns={cooldowns_matched}/{cooldowns_modified}"
                )
        
        except Exception as e:
            if logger:
                logger.error(f"[🔧] Backfill failed: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Backfill failed: {str(e)[:200]}",
                ephemeral=True
            )


class DLQActionModal(discord.ui.Modal):
    """Modal for DLQ actions (retry/discard) by ID."""
    dlq_id_input = discord.ui.TextInput(
        label="DLQ Item ID",
        placeholder="Paste the DLQ _id",
        required=True,
        max_length=64,
    )

    def __init__(self, cog: "OperatorPanel", action: str):
        title = "Retry DLQ Item" if action == "retry" else "Discard DLQ Item"
        super().__init__(title=title)
        self.cog = cog
        self.action = action

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        dlq_id = str(self.dlq_id_input).strip()
        if self.action == "retry":
            await self.cog.execute_dlq_retry(interaction, dlq_id)
        else:
            await self.cog.execute_dlq_discard(interaction, dlq_id)


class TargetUserPickerView(discord.ui.View):
    """User select view to drive XP and memory actions."""

    def __init__(self, cog: "OperatorPanel", owner_id: int, guild_id: Optional[int], action: str):
        super().__init__(timeout=120)
        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.action = action

        placeholder_map = {
            "add_xp": "Select a user to add XP",
            "remove_xp": "Select a user to remove XP",
            "reset_xp": "Select a user to reset XP",
            "view_level": "Select a user to view level",
            "reset_level": "Select a user to reset level",
            "inspect_memory": "Select a user to inspect",
        }

        self.add_item(TargetUserSelect(self, placeholder_map.get(action, "Select a user")))

    def disable_all_items(self):
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True  # type: ignore[attr-defined]


class TargetUserSelect(discord.ui.UserSelect):
    """User select that routes actions after a selection."""

    def __init__(self, parent_view: TargetUserPickerView, placeholder: str):
        super().__init__(placeholder=placeholder, min_values=1, max_values=1)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.owner_id:
            await interaction.response.send_message("❌ This selector is tied to a different operator.", ephemeral=True)
            return

        target_user = self.values[0]

        if self.parent_view.action in ("add_xp", "remove_xp"):
            modal = AdjustXPModal(
                self.parent_view.cog,
                self.parent_view.guild_id or 0,
                target_user,
                "add" if self.parent_view.action == "add_xp" else "remove"
            )
            await interaction.response.send_modal(modal)
        elif self.parent_view.action == "reset_xp":
            await self.parent_view.cog.reset_user_xp(interaction, target_user)
        elif self.parent_view.action == "view_level":
            await self.parent_view.cog.view_user_level(interaction, target_user)
        elif self.parent_view.action == "reset_level":
            await self.parent_view.cog.reset_user_level(interaction, target_user)
        elif self.parent_view.action == "inspect_memory":
            await self.parent_view.cog.inspect_user_memory(interaction, target_user)
        else:
            await interaction.response.send_message("❌ Unsupported action.", ephemeral=True)
            return

        self.parent_view.disable_all_items()
        if interaction.message:
            try:
                await interaction.message.edit(view=self.parent_view)
            except Exception:
                pass


# ════════════════════════════════════════════════════════════════════════════════
# VIEW CLASSES
# ════════════════════════════════════════════════════════════════════════════════

class ConfirmInitAllView(discord.ui.View):
    """Confirm view for initialize-all actions."""

    def __init__(self, cog: "OperatorPanel", owner_id: int, guild_id: Optional[int]):
        super().__init__(timeout=30)
        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            if interaction.response.is_done():
                await interaction.followup.send("❌ This confirmation belongs to a different operator.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ This confirmation belongs to a different operator.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm Initialize All", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.initialize_all_xp(interaction, guild_id=self.guild_id)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Initialization cancelled.", view=None)


class XPResetPreviewModal(discord.ui.Modal):
    """Modal for XP reset with dry-run confirmation."""
    confirmation_input = discord.ui.TextInput(
        label="Type to confirm",
        placeholder="Type: RESET XP winter-2026",
        required=True,
        max_length=100
    )

    def __init__(self, cog: "OperatorPanel", new_season_id: str, immediate: bool = False):
        super().__init__(title="Confirm XP Reset")
        self.cog = cog
        self.new_season_id = new_season_id
        self.immediate = immediate

    async def on_submit(self, interaction: discord.Interaction):
        typed = str(self.confirmation_input).strip()
        expected = f"RESET XP {self.new_season_id}"
        
        if typed != expected:
            await interaction.response.send_message(
                f"❌ Incorrect confirmation. You typed: `{typed}`\nExpected: `{expected}`",
                ephemeral=True
            )
            return
        
        # Confirmation matched; proceed with actual reset
        await self.cog.execute_xp_reset_operation(interaction, self.new_season_id, dry_run=False, immediate=self.immediate)


class XPResetConfirmView(discord.ui.View):
    """Confirmation view for XP reset with dry-run and execute options."""

    def __init__(self, cog: "OperatorPanel", owner_id: int, preview: Dict[str, Any], new_season_id: str):
        super().__init__(timeout=120)
        self.cog = cog
        self.owner_id = owner_id
        self.preview = preview
        self.new_season_id = new_season_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            if interaction.response.is_done():
                await interaction.followup.send("❌ This confirmation belongs to a different operator.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ This confirmation belongs to a different operator.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Dry Run", style=discord.ButtonStyle.primary, emoji="🧪")
    async def dry_run(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.execute_xp_reset_operation(interaction, self.new_season_id, dry_run=True, immediate=False)

    @discord.ui.button(label="Execute Reset", style=discord.ButtonStyle.danger, emoji="⚡")
    async def execute(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show timing confirmation
        await self.cog.show_xp_reset_timing_confirmation(interaction, self.new_season_id)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="XP reset cancelled.", view=None)


class XPResetExecuteView(discord.ui.View):
    """Final confirmation view for XP reset with timing options."""

    def __init__(self, cog: "OperatorPanel", owner_id: int, new_season_id: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.owner_id = owner_id
        self.new_season_id = new_season_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            if interaction.response.is_done():
                await interaction.followup.send("❌ This confirmation belongs to a different operator.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ This confirmation belongs to a different operator.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Send Now (All Guilds)", style=discord.ButtonStyle.danger, emoji="🚀")
    async def immediate(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show typed confirmation modal for immediate
        modal = XPResetPreviewModal(self.cog, self.new_season_id, immediate=True)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Queue for Tomorrow", style=discord.ButtonStyle.primary, emoji="📅")
    async def scheduled(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show typed confirmation modal for scheduled
        modal = XPResetPreviewModal(self.cog, self.new_season_id, immediate=False)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="XP reset cancelled.", view=None)


class RollbackOperationView(discord.ui.View):
    """Confirmation view for rolling back an operation."""

    def __init__(self, cog: "OperatorPanel", owner_id: int, operation_id: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.owner_id = owner_id
        self.operation_id = operation_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            if interaction.response.is_done():
                await interaction.followup.send("❌ This confirmation belongs to a different operator.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ This confirmation belongs to a different operator.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm Rollback", style=discord.ButtonStyle.danger, emoji="↩️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.execute_rollback_operation(interaction, self.operation_id)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Rollback cancelled.", view=None)


class SendWorldAnnouncementModal(discord.ui.Modal):
    """Modal for custom world announcement content."""
    content_input = discord.ui.TextInput(
        label="Announcement Content",
        placeholder="e.g., 'A new Valentine's Day event is coming! Abby will have crushes soon!'",
        required=True,
        max_length=500
    )

    def __init__(self, cog: "OperatorPanel"):
        super().__init__(title="Send World Announcement")
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        content = str(self.content_input)
        await self.cog.show_announcement_preview(interaction, content)


class SendAnnouncementConfirmView(discord.ui.View):
    """Confirmation view for world announcements with timing and scope options."""

    def __init__(self, cog: "OperatorPanel", owner_id: int, content: str, enhanced_message: Optional[str]):
        super().__init__(timeout=60)
        self.cog = cog
        self.owner_id = owner_id
        self.content = content
        self.enhanced_message = enhanced_message
        self.scope = "world"  # Default to world-wide
        self._lock = asyncio.Lock()  # Prevent race conditions on update

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            if interaction.response.is_done():
                await interaction.followup.send("❌ This confirmation belongs to a different operator.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ This confirmation belongs to a different operator.", ephemeral=True)
            return False
        return True

    async def update_enhanced_message(self, enhanced_message: str) -> None:
        """Update the enhanced message (called from background task)."""
        async with self._lock:
            self.enhanced_message = enhanced_message

    @discord.ui.select(
        placeholder="Announcement Scope",
        options=[
            discord.SelectOption(
                label="This Guild Only",
                value="guild",
                description="Send to current guild's announcement channel",
                emoji="🏘️"
            ),
            discord.SelectOption(
                label="All Guilds (World)",
                value="world",
                description="Send to all guilds' announcement channels",
                emoji="🌍",
                default=True
            ),
        ],
        row=0
    )
    async def select_scope(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.scope = select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="Send Now", style=discord.ButtonStyle.danger, emoji="🚀", row=1)
    async def send_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Defer immediately to avoid timeout (we don't need interaction after this)
        await interaction.response.defer(ephemeral=True)
        
        # Execute in background (no await - fire and forget)
        asyncio.create_task(self.cog.execute_world_announcement_background(
            interaction, 
            self.enhanced_message or self.content, 
            immediate=True, 
            scope=self.scope
        ))
        
        # Send followup message
        await interaction.followup.send(
            "✅ **Sending announcement now...** Processing in background.",
            ephemeral=True
        )

    @discord.ui.button(label="Queue for Tomorrow", style=discord.ButtonStyle.primary, emoji="📅", row=1)
    async def queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Defer immediately to avoid timeout (we don't need interaction after this)
        await interaction.response.defer(ephemeral=True)
        
        # Execute in background (no await - fire and forget)
        asyncio.create_task(self.cog.execute_world_announcement_background(
            interaction, 
            self.enhanced_message or self.content, 
            immediate=False, 
            scope=self.scope
        ))
        
        # Send followup message
        await interaction.followup.send(
            "✅ **Queued for tomorrow...** Processing in background.",
            ephemeral=True
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Announcement cancelled.", view=None)


# ════════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT VIEWS & MODALS
# ════════════════════════════════════════════════════════════════════════════════

class CreateEventSelectView(discord.ui.View):
    """View to select which event template to create."""

    def __init__(self, cog: "OperatorPanel", owner_id: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.owner_id = owner_id

        from abby_core.system.state_registry import get_available_event_templates, get_event_template

        templates = get_available_event_templates()

        select = discord.ui.Select(
            placeholder="Choose an event template",
            options=[
                discord.SelectOption(
                    label=t["label"],
                    value=t["key"],
                    description=t["description"][:100] if t["description"] else None,
                )
                for t in templates
            ]
        )

        async def on_select(interaction: discord.Interaction):
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("❌ This selector is locked to the operator.", ephemeral=True)
                return

            event_key = select.values[0]
            template = get_event_template(event_key)
            if not template:
                await interaction.response.send_message("❌ Template not found.", ephemeral=True)
                return

            view = CreateEventConfigView(self.cog, self.owner_id, event_key, template)
            embed = self.cog.build_event_template_embed(event_key, template, view.selected_year)
            await interaction.response.send_message(
                "Configure event (year + overrides):",
                embed=embed,
                view=view,
                ephemeral=True,
            )

        select.callback = on_select
        self.add_item(select)


class CreateEventConfigView(discord.ui.View):
    """Configure year and overrides for an event template."""

    def __init__(self, cog: "OperatorPanel", owner_id: int, event_key: str, template: Dict[str, Any]):
        super().__init__(timeout=180)
        from datetime import datetime as dt

        self.cog = cog
        self.owner_id = owner_id
        self.event_key = event_key
        self.template = template
        self.allowed_overrides = template.get("allowed_overrides", [])
        self.template_effects = dict(template.get("effects", {}))
        self.start_at_override: Optional[Any] = None
        self.end_at_override: Optional[Any] = None
        self.date_override_reason: Optional[str] = None

        current_year = dt.utcnow().year
        self.year_options = [current_year + i for i in range(5)]
        self.selected_year = self.year_options[0]

        # Year select (row 0)
        year_select = discord.ui.Select(
            placeholder="Select year",
            options=[discord.SelectOption(label=str(y), value=str(y), default=(y == self.selected_year)) for y in self.year_options],
            row=0,
        )

        async def year_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            self.selected_year = int(year_select.values[0])
            try:
                embed = self.cog.build_event_template_embed(
                    self.event_key,
                    self.template,
                    self.selected_year,
                    start_override=self.start_at_override,
                    end_override=self.end_at_override,
                    date_override_reason=self.date_override_reason,
                )
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception:
                await interaction.response.defer(ephemeral=True)

        year_select.callback = year_cb
        self.add_item(year_select)

        # Action buttons (rows 1-2)
        has_overrides = len(self.allowed_overrides) > 0
        
        if has_overrides:
            effects_button = discord.ui.Button(
                label=f"Configure Effects ({len(self.allowed_overrides)})",
                style=discord.ButtonStyle.primary,
                emoji="⚙️",
                row=1,
            )
            
            async def effects_cb(interaction: discord.Interaction):
                if not await self._ensure_owner(interaction):
                    return
                await interaction.response.send_modal(EventEffectsModal(self))
            
            effects_button.callback = effects_cb
            self.add_item(effects_button)

        date_button = discord.ui.Button(
            label="Set Date Overrides",
            style=discord.ButtonStyle.primary,
            emoji="🗓️",
            row=1,
        )
        
        async def date_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await interaction.response.send_modal(EventDateOverrideModal(self))

        date_button.callback = date_cb
        self.add_item(date_button)

        # Confirm/Cancel (row 2)
        confirm_button = discord.ui.Button(
            label="Create Event",
            style=discord.ButtonStyle.success,
            emoji="✅",
            row=2,
        )
        cancel_button = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            row=2,
        )

        async def confirm_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await interaction.response.defer(ephemeral=True)
            overrides: Dict[str, Any] = {}
            default_effects = self.template.get("effects", {})

            for key in self.allowed_overrides:
                if key in self.template_effects:
                    current_val = self.template_effects[key]
                    if key in default_effects and current_val == default_effects[key]:
                        continue
                    overrides[key] = current_val

            await self.cog.create_event_from_template(
                interaction,
                self.event_key,
                self.selected_year,
                overrides if overrides else None,
                self.start_at_override,
                self.end_at_override,
                self.date_override_reason,
            )
            self.disable_all_items()
            try:
                await interaction.edit_original_response(view=self)
            except Exception:
                pass

        async def cancel_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await interaction.response.edit_message(content="Event creation cancelled.", view=None)

        confirm_button.callback = confirm_cb
        cancel_button.callback = cancel_cb
        self.add_item(confirm_button)
        self.add_item(cancel_button)

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This selector is locked to the operator.", ephemeral=True)
            return False
        return True

    def disable_all_items(self):
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True  # type: ignore[attr-defined]


class EventEffectsModal(discord.ui.Modal):
    """Modal for configuring event effect overrides."""
    
    def __init__(self, view: CreateEventConfigView):
        super().__init__(title="Configure Event Effects")
        self.view = view
        
        # Build text inputs dynamically based on allowed overrides
        from abby_core.system.effects_registry import get_effect_ui_choices
        
        for idx, effect_key in enumerate(self.view.allowed_overrides[:5]):  # Discord limit: 5 inputs max
            current_val = self.view.template_effects.get(effect_key)
            
            if effect_key == "persona_overlay":
                choices = get_effect_ui_choices(effect_key)
                hint = f"Options: {', '.join(choices)}" if choices else ""
                self.add_item(discord.ui.TextInput(
                    label=effect_key.replace("_", " ").title(),
                    placeholder=hint[:100] if hint else current_val,
                    default=str(current_val) if current_val else None,
                    required=False,
                    max_length=100,
                ))
            elif effect_key == "affinity_modifier":
                choices = get_effect_ui_choices(effect_key) or ["1.0", "1.25", "1.5"]
                hint = f"Options: {', '.join(choices)}"
                self.add_item(discord.ui.TextInput(
                    label=effect_key.replace("_", " ").title(),
                    placeholder=hint[:100],
                    default=str(current_val) if current_val else None,
                    required=False,
                    max_length=20,
                ))
            elif isinstance(current_val, bool) or effect_key.endswith("_enabled"):
                self.add_item(discord.ui.TextInput(
                    label=effect_key.replace("_", " ").title(),
                    placeholder="true or false",
                    default=str(current_val).lower() if current_val is not None else "false",
                    required=False,
                    max_length=10,
                ))
            else:
                self.add_item(discord.ui.TextInput(
                    label=effect_key.replace("_", " ").title(),
                    placeholder=f"Current: {current_val}",
                    default=str(current_val) if current_val else None,
                    required=False,
                    max_length=100,
                ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse inputs back into template_effects
            from abby_core.system.effects_registry import get_effect_ui_choices
            
            for idx, effect_key in enumerate(self.view.allowed_overrides[:5]):
                if idx >= len(self.children):
                    break
                    
                input_field = self.children[idx]
                value_str = str(input_field).strip()
                
                if not value_str:
                    continue
                
                # Parse based on effect type
                if effect_key == "affinity_modifier":
                    try:
                        self.view.template_effects[effect_key] = float(value_str)
                    except ValueError:
                        await interaction.response.send_message(
                            f"❌ Invalid number for {effect_key}: {value_str}",
                            ephemeral=True,
                        )
                        return
                elif isinstance(self.view.template_effects.get(effect_key), bool) or effect_key.endswith("_enabled"):
                    self.view.template_effects[effect_key] = value_str.lower() in ("true", "yes", "1", "enabled")
                elif effect_key == "persona_overlay":
                    choices = get_effect_ui_choices(effect_key)
                    if choices and value_str not in choices:
                        await interaction.response.send_message(
                            f"❌ Invalid persona overlay: {value_str}. Options: {', '.join(choices)}",
                            ephemeral=True,
                        )
                        return
                    self.view.template_effects[effect_key] = value_str
                else:
                    self.view.template_effects[effect_key] = value_str
            
            # Update embed with new effects
            embed = self.view.cog.build_event_template_embed(
                self.view.event_key,
                self.view.template,
                self.view.selected_year,
                start_override=self.view.start_at_override,
                end_override=self.view.end_at_override,
                date_override_reason=self.view.date_override_reason,
            )
            
            # Show current overrides
            overrides_applied = []
            default_effects = self.view.template.get("effects", {})
            for key in self.view.allowed_overrides:
                if key in self.view.template_effects:
                    current = self.view.template_effects[key]
                    default = default_effects.get(key)
                    if current != default:
                        overrides_applied.append(f"• {key}: {current}")
            
            override_msg = "\n".join(overrides_applied) if overrides_applied else "Using defaults"
            
            await interaction.response.edit_message(
                content=f"**Effect Overrides:**\n{override_msg}",
                embed=embed,
                view=self.view,
            )
            
        except Exception as exc:
            if logger:
                logger.error(f"[🔧] Failed to apply effects: {exc}")
            await interaction.response.send_message(
                f"❌ Error applying effects: {exc}",
                ephemeral=True,
            )


class EventDateOverrideModal(discord.ui.Modal):
    """Collect optional date overrides and a reason."""
    start_input = discord.ui.TextInput(
        label="Start date override",
        placeholder="YYYY-MM-DD or ISO datetime",
        required=False,
        max_length=32,
    )
    end_input = discord.ui.TextInput(
        label="End date override",
        placeholder="YYYY-MM-DD or ISO datetime",
        required=False,
        max_length=32,
    )
    reason_input = discord.ui.TextInput(
        label="Reason for override",
        placeholder="Why are you changing the dates?",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=200,
    )

    def __init__(self, view: CreateEventConfigView):
        super().__init__(title="Set Event Dates")
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        start_val = str(self.start_input).strip()
        end_val = str(self.end_input).strip()
        reason_val = str(self.reason_input).strip()

        start_override: Optional[str] = start_val or None
        end_override: Optional[str] = end_val or None
        reason: Optional[str] = reason_val or None
        if not start_override and not end_override:
            reason = None

        if (start_override or end_override) and not reason:
            await interaction.response.send_message("❌ Please provide a reason for changing dates.", ephemeral=True)
            return

        try:
            from abby_core.system.state_registry import get_event_schedule

            ok, err, _ = get_event_schedule(
                self.view.event_key,
                self.view.selected_year,
                start_at_override=start_override,
                end_at_override=end_override,
            )
            if not ok:
                await interaction.response.send_message(f"❌ {err}", ephemeral=True)
                return

            self.view.start_at_override = start_override
            self.view.end_at_override = end_override
            self.view.date_override_reason = reason

            embed = self.view.cog.build_event_template_embed(
                self.view.event_key,
                self.view.template,
                self.view.selected_year,
                start_override=self.view.start_at_override,
                end_override=self.view.end_at_override,
                date_override_reason=self.view.date_override_reason,
            )
            await interaction.response.edit_message(
                content="Configure event (year + overrides):",
                embed=embed,
                view=self.view,
            )
            await interaction.followup.send(
                "✅ Dates saved. Leave blank to use defaults.",
                ephemeral=True,
            )
        except Exception as exc:
            if logger:
                logger.error(f"[🔧] Failed to set date overrides: {exc}")
            await interaction.response.send_message(
                f"❌ Could not set dates: {exc}",
                ephemeral=True,
            )


class PreviewStatesDateModal(discord.ui.Modal):
    """Modal to select date for state preview."""
    date_input = discord.ui.TextInput(
        label="Date to Preview",
        placeholder="YYYY-MM-DD (e.g., 2026-02-14)",
        required=True,
        max_length=10
    )

    def __init__(self, cog: "OperatorPanel"):
        super().__init__(title="Preview States at Date")
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from datetime import datetime as dt
            target_date = dt.strptime(str(self.date_input), "%Y-%m-%d")
        except ValueError:
            await interaction.followup.send("❌ Invalid date format. Use YYYY-MM-DD", ephemeral=True)
            return

        await self.cog.preview_states_at_date(interaction, target_date)


class OperatorView(discord.ui.View):
    """Navigation and scoped actions for /operator screens."""

    def __init__(
        self,
        cog: "OperatorPanel",
        owner_id: int,
        active_tab: str = "overview",
        economy_section: str = "xp",
        system_subtab: str = "events",
    ):
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_id = owner_id
        self.active_tab = active_tab
        self.economy_section = economy_section
        self.system_subtab = system_subtab

        self._add_nav_buttons()
        self._add_tab_actions()

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            if interaction.response.is_done():
                await interaction.followup.send("❌ This panel is locked to the operator who opened it.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ This panel is locked to the operator who opened it.", ephemeral=True)
            return False
        return True

    def _add_nav_buttons(self) -> None:
        nav_items = [
            ("overview", "🏠", "Overview"),
            ("economy", "⭐", "Economy"),
            ("messaging", "📢", "Messaging"),
            ("system", "🔧", "System"),
            ("diagnostics", "🛠", "Diagnostics"),
        ]

        for idx, (tab, emoji, label) in enumerate(nav_items):
            style = discord.ButtonStyle.primary if tab == self.active_tab else discord.ButtonStyle.secondary
            button = discord.ui.Button(label=label, style=style, emoji=emoji, row=0)

            async def callback(interaction: discord.Interaction, tab=tab):
                if not await self._ensure_owner(interaction):
                    return
                # Reset economy section to default when switching tabs
                await self.cog.update_operator_panel(
                    interaction,
                    tab,
                    economy_section="xp",
                    system_subtab="events",
                )

            button.callback = callback
            self.add_item(button)

    def _add_tab_actions(self) -> None:
        if self.active_tab == "economy":
            self._add_economy_actions()
        elif self.active_tab == "messaging":
            self._add_messaging_actions()
        elif self.active_tab == "system":
            self._add_system_actions()
        elif self.active_tab == "diagnostics":
            self._add_diagnostics_actions()

    def _add_economy_actions(self) -> None:
        section = self.economy_section or "xp"
        section_select = discord.ui.Select(
            placeholder="Choose economy section",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="XP Actions", value="xp", emoji="🧪", default=section == "xp"),
                discord.SelectOption(label="Levels", value="levels", emoji="🎖️", default=section == "levels"),
                discord.SelectOption(label="Advanced", value="advanced", emoji="⚠️", default=section == "advanced"),
            ],
            row=4,
        )

        # XP Management buttons
        add_xp_button = discord.ui.Button(label="Add XP", style=discord.ButtonStyle.success, emoji="➕", row=1)
        remove_xp_button = discord.ui.Button(label="Remove XP", style=discord.ButtonStyle.secondary, emoji="➖", row=1)
        reset_user_xp_button = discord.ui.Button(label="Reset User XP", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
        
        # Level Management buttons
        view_level_button = discord.ui.Button(label="View User Level", style=discord.ButtonStyle.secondary, emoji="🎖️", row=1)
        reset_user_level_button = discord.ui.Button(label="Reset User Level", style=discord.ButtonStyle.secondary, emoji="⬇️", row=1)
        
        # Advanced buttons
        reset_all_xp_button = discord.ui.Button(label="Reset All XP (Season)", style=discord.ButtonStyle.danger, emoji="⚡", row=1)
        reset_all_levels_button = discord.ui.Button(label="Reset All Levels (Guild)", style=discord.ButtonStyle.danger, emoji="🎯", row=1)
        init_all_button = discord.ui.Button(label="Initialize Missing Records", style=discord.ButtonStyle.secondary, emoji="🌐", row=1)
        backfill_users_button = discord.ui.Button(label="Backfill User Schema", style=discord.ButtonStyle.secondary, emoji="📋", row=1)

        async def add_xp_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            if not interaction.guild:
                await interaction.response.send_message("❌ This action requires a guild.", ephemeral=True)
                return
            view = TargetUserPickerView(self.cog, interaction.user.id, interaction.guild.id, "add_xp")
            await interaction.response.send_message("Select a user to add XP:", view=view, ephemeral=True)

        async def remove_xp_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            if not interaction.guild:
                await interaction.response.send_message("❌ This action requires a guild.", ephemeral=True)
                return
            view = TargetUserPickerView(self.cog, interaction.user.id, interaction.guild.id, "remove_xp")
            await interaction.response.send_message("Select a user to remove XP:", view=view, ephemeral=True)

        async def reset_user_xp_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            if not interaction.guild:
                await interaction.response.send_message("❌ This action requires a guild.", ephemeral=True)
                return
            view = TargetUserPickerView(self.cog, interaction.user.id, interaction.guild.id, "reset_xp")
            await interaction.response.send_message("Select a user to reset XP:", view=view, ephemeral=True)
        
        async def view_level_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            if not interaction.guild:
                await interaction.response.send_message("❌ This action requires a guild.", ephemeral=True)
                return
            view = TargetUserPickerView(self.cog, interaction.user.id, interaction.guild.id, "view_level")
            await interaction.response.send_message("Select a user to view level:", view=view, ephemeral=True)
        
        async def reset_user_level_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            if not interaction.guild:
                await interaction.response.send_message("❌ This action requires a guild.", ephemeral=True)
                return
            view = TargetUserPickerView(self.cog, interaction.user.id, interaction.guild.id, "reset_level")
            await interaction.response.send_message("Select a user to reset level:", view=view, ephemeral=True)

        async def init_all_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            if not interaction.guild:
                await interaction.response.send_message("❌ This action requires a guild.", ephemeral=True)
                return
            confirm_view = ConfirmInitAllView(self.cog, self.owner_id, interaction.guild.id)
            await interaction.response.send_message(
                "⚠️ Initialize XP for all members? This will touch every non-bot user.",
                view=confirm_view,
                ephemeral=True,
            )

        async def reset_all_xp_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_xp_reset_preview(interaction)

        async def reset_all_levels_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            modal = ResetAllLevelsModal(self.cog)
            await interaction.response.send_modal(modal)

        async def backfill_users_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            # Show confirmation modal before running backfill
            modal = BackfillUsersModal(self.cog)
            await interaction.response.send_modal(modal)

        async def section_select_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            chosen = section_select.values[0]
            await self.cog.update_operator_panel(interaction, "economy", economy_section=chosen)

        section_select.callback = section_select_cb

        add_xp_button.callback = add_xp_cb
        remove_xp_button.callback = remove_xp_cb
        reset_user_xp_button.callback = reset_user_xp_cb
        view_level_button.callback = view_level_cb
        reset_user_level_button.callback = reset_user_level_cb
        init_all_button.callback = init_all_cb
        reset_all_xp_button.callback = reset_all_xp_cb
        reset_all_levels_button.callback = reset_all_levels_cb
        backfill_users_button.callback = backfill_users_cb

        # Add selector first
        self.add_item(section_select)

        # Add only buttons for the active section to keep layout clean
        if section == "xp":
            self.add_item(add_xp_button)
            self.add_item(remove_xp_button)
            self.add_item(reset_user_xp_button)
        elif section == "levels":
            self.add_item(view_level_button)
            self.add_item(reset_user_level_button)
        elif section == "advanced":
            self.add_item(reset_all_xp_button)
            self.add_item(reset_all_levels_button)
            self.add_item(init_all_button)
            self.add_item(backfill_users_button)

    def _add_messaging_actions(self) -> None:
        """Messaging tab: Announcement management"""
        world_announce_button = discord.ui.Button(
            label="Send World Announcement", 
            style=discord.ButtonStyle.primary, 
            emoji="📢", 
            row=1
        )
        
        async def world_announce_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            modal = SendWorldAnnouncementModal(self.cog)
            await interaction.response.send_modal(modal)
        
        world_announce_button.callback = world_announce_cb
        self.add_item(world_announce_button)
    
    def _add_system_actions(self) -> None:
        """System tab: Status + Event Management + DLQ + Metrics subtabs."""
        section = self.system_subtab or "status"
        section_select = discord.ui.Select(
            placeholder="Choose system subtab",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Status", value="status", emoji="📋", default=section == "status"),
                discord.SelectOption(label="Event Management", value="events", emoji="📅", default=section == "events"),
                discord.SelectOption(label="DLQ Inspector", value="dlq", emoji="🚨", default=section == "dlq"),
                discord.SelectOption(label="Metrics Dashboard", value="metrics", emoji="📊", default=section == "metrics"),
            ],
            row=4,
        )

        async def section_select_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            chosen = section_select.values[0]
            await self.cog.update_operator_panel(
                interaction,
                "system",
                economy_section=self.economy_section,
                system_subtab=chosen,
            )

        section_select.callback = section_select_cb
        self.add_item(section_select)

        if section == "status":
            self._add_system_status_actions()
        elif section == "events":
            self._add_system_event_management_actions()
        elif section == "dlq":
            self._add_system_dlq_actions()
        elif section == "metrics":
            self._add_system_metrics_actions()

    def _add_system_status_actions(self) -> None:
        """System > Status actions - documented system status commands as buttons."""
        status_all_button = discord.ui.Button(
            label="All Systems",
            style=discord.ButtonStyle.primary,
            emoji="📋",
            row=2,
        )
        
        status_seasons_button = discord.ui.Button(
            label="Seasons",
            style=discord.ButtonStyle.secondary,
            emoji="🌍",
            row=2,
        )
        
        status_events_button = discord.ui.Button(
            label="Events",
            style=discord.ButtonStyle.secondary,
            emoji="📅",
            row=2,
        )
        
        status_effects_button = discord.ui.Button(
            label="Effects",
            style=discord.ButtonStyle.secondary,
            emoji="⚙️",
            row=3,
        )
        
        status_jobs_button = discord.ui.Button(
            label="Jobs",
            style=discord.ButtonStyle.secondary,
            emoji="⚙️",
            row=3,
        )

        async def status_all_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_system_status_all(interaction)

        async def status_seasons_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_system_status_seasons(interaction)

        async def status_events_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_system_status_events(interaction)

        async def status_effects_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_system_status_effects(interaction)

        async def status_jobs_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_system_status_jobs(interaction)

        status_all_button.callback = status_all_cb
        status_seasons_button.callback = status_seasons_cb
        status_events_button.callback = status_events_cb
        status_effects_button.callback = status_effects_cb
        status_jobs_button.callback = status_jobs_cb

        self.add_item(status_all_button)
        self.add_item(status_seasons_button)
        self.add_item(status_events_button)
        self.add_item(status_effects_button)
        self.add_item(status_jobs_button)

    def _add_system_event_management_actions(self) -> None:
        """System > Event Management actions."""
        list_events_button = discord.ui.Button(
            label="List Upcoming Events",
            style=discord.ButtonStyle.primary,
            emoji="📅",
            row=1,
        )

        create_event_button = discord.ui.Button(
            label="Create Event",
            style=discord.ButtonStyle.success,
            emoji="✨",
            row=1,
        )

        preview_states_button = discord.ui.Button(
            label="Preview States",
            style=discord.ButtonStyle.secondary,
            emoji="🔮",
            row=1,
        )

        rollback_button = discord.ui.Button(
            label="Rollback Operation",
            style=discord.ButtonStyle.danger,
            emoji="↩️",
            row=2,
        )

        async def list_events_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_upcoming_events(interaction)

        async def create_event_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_create_event_menu(interaction)

        async def preview_states_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_preview_states_menu(interaction)

        async def rollback_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_rollback_operations(interaction)

        list_events_button.callback = list_events_cb
        create_event_button.callback = create_event_cb
        preview_states_button.callback = preview_states_cb
        rollback_button.callback = rollback_cb

        self.add_item(list_events_button)
        self.add_item(create_event_button)
        self.add_item(preview_states_button)
        self.add_item(rollback_button)

    def _add_system_dlq_actions(self) -> None:
        """System > DLQ Inspector actions."""
        list_dlq_button = discord.ui.Button(
            label="List DLQ",
            style=discord.ButtonStyle.primary,
            emoji="📋",
            row=1,
        )
        retry_button = discord.ui.Button(
            label="Retry Item",
            style=discord.ButtonStyle.success,
            emoji="🔄",
            row=1,
        )
        discard_button = discord.ui.Button(
            label="Discard Item",
            style=discord.ButtonStyle.danger,
            emoji="🗑️",
            row=1,
        )
        stats_button = discord.ui.Button(
            label="DLQ Stats",
            style=discord.ButtonStyle.secondary,
            emoji="📊",
            row=2,
        )

        async def list_dlq_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_dlq_list(interaction)

        async def retry_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_dlq_retry_select(interaction)

        async def discard_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_dlq_discard_select(interaction)

        async def stats_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_dlq_stats(interaction)

        list_dlq_button.callback = list_dlq_cb
        retry_button.callback = retry_cb
        discard_button.callback = discard_cb
        stats_button.callback = stats_cb

        self.add_item(list_dlq_button)
        self.add_item(retry_button)
        self.add_item(discard_button)
        self.add_item(stats_button)

    def _add_system_metrics_actions(self) -> None:
        """System > Metrics Dashboard actions."""
        dashboard_button = discord.ui.Button(
            label="Dashboard",
            style=discord.ButtonStyle.primary,
            emoji="📊",
            row=1,
        )
        trend_button = discord.ui.Button(
            label="7-Day Trend",
            style=discord.ButtonStyle.secondary,
            emoji="📈",
            row=1,
        )
        by_guild_button = discord.ui.Button(
            label="By Guild",
            style=discord.ButtonStyle.secondary,
            emoji="🌍",
            row=1,
        )
        cost_button = discord.ui.Button(
            label="Cost Analysis",
            style=discord.ButtonStyle.secondary,
            emoji="💰",
            row=2,
        )

        async def dashboard_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_metrics_dashboard(interaction)

        async def trend_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_metrics_trend(interaction, days=7)

        async def by_guild_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_metrics_by_guild(interaction)

        async def cost_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_metrics_cost_analysis(interaction)

        dashboard_button.callback = dashboard_cb
        trend_button.callback = trend_cb
        by_guild_button.callback = by_guild_cb
        cost_button.callback = cost_cb

        self.add_item(dashboard_button)
        self.add_item(trend_button)
        self.add_item(by_guild_button)
        self.add_item(cost_button)

    def _add_data_actions(self) -> None:
        inspect_button = discord.ui.Button(label="Inspect User", style=discord.ButtonStyle.secondary, emoji="🔍", row=1)
        maintenance_button = discord.ui.Button(label="Run Maintenance", style=discord.ButtonStyle.secondary, emoji="🔧", row=1)

        async def inspect_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            if not self.cog.memory_service:
                await interaction.response.send_message("❌ Memory system unavailable.", ephemeral=True)
                return
            view = TargetUserPickerView(self.cog, interaction.user.id, interaction.guild.id if interaction.guild else None, "inspect_memory")
            await interaction.response.send_message("Select a user to inspect:", view=view, ephemeral=True)

        async def maintenance_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.run_memory_maintenance(interaction)

        inspect_button.callback = inspect_cb
        maintenance_button.callback = maintenance_cb

        self.add_item(inspect_button)
        self.add_item(maintenance_button)

    def _add_diagnostics_actions(self) -> None:
        """Diagnostics tab: System health checks and scheduling"""
        schedule_config_button = discord.ui.Button(
            label="Configure Job Schedules",
            style=discord.ButtonStyle.primary,
            emoji="⏰",
            row=1
        )
        
        async def schedule_config_cb(interaction: discord.Interaction):
            if not await self._ensure_owner(interaction):
                return
            await self.cog.show_schedule_configuration(interaction)
        
        schedule_config_button.callback = schedule_config_cb
        self.add_item(schedule_config_button)


# ════════════════════════════════════════════════════════════════════════════════
# MAIN COG
# ════════════════════════════════════════════════════════════════════════════════

class OperatorPanel(commands.Cog):
    """Platform-level operator console for maintenance, recovery, and integrity."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Initialize memory service
        try:
            self.memory_service = create_discord_memory_service(logger_override=logger)
        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to initialize memory service: {e}")
            self.memory_service = None
        
        if logger:
            logger.info(f"[🔧] Operator Panel loaded ({len(OPERATOR_IDS)} operators)")

    def _get_platform_health(self) -> dict:
        """Check platform subsystem health (read-only confidence signals)."""
        health = {}

        # Scheduler
        try:
            from abby_core.services.scheduler import get_scheduler_service

            scheduler = get_scheduler_service()
            health["scheduler"] = "running" if scheduler.running else "stopped"
        except Exception:
            health["scheduler"] = "unavailable"

        # Registry
        try:
            from abby_core.discord.cogs.system.registry import JOB_HANDLERS
            job_count = len(JOB_HANDLERS)
            health["registry"] = f"loaded ({job_count} jobs)"
        except Exception:
            health["registry"] = "unavailable"

        # Memory
        health["memory"] = "healthy" if self.memory_service else "unavailable"

        # Canon system
        canon_cog = self.bot.get_cog("CanonCommands")
        health["canon"] = "loaded" if canon_cog else "not loaded"

        # Personality system (module-level, no cog needed)
        try:
            from abby_core.personality.manager import PersonalityManager
            health["personality"] = "loaded"
        except Exception:
            health["personality"] = "unavailable"

        return health

    # ==================== XP RESET OPERATIONS ====================

    async def show_xp_reset_preview(self, interaction: discord.Interaction) -> None:
        """Show XP reset preview with dry-run and execute options."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from abby_core.system.system_state import get_active_state
            from abby_core.system.season_reset_operations import check_concurrent_xp_operations
            
            # Check for concurrent operations
            safe, blocking_op_id = check_concurrent_xp_operations()
            if not safe:
                await interaction.followup.send(
                    f"❌ Another XP operation is in progress: `{blocking_op_id}`\n"
                    f"Wait for it to complete or rollback first.",
                    ephemeral=True
                )
                return
            
            # Get current season
            active_season = get_active_state("season")
            if not active_season:
                await interaction.followup.send("❌ No active season found.", ephemeral=True)
                return
            
            new_season_id = active_season.get("state_id", "unknown")
            
            # Show preview UI directly - no need to call execute yet
            # User can click "Dry Run" button to record intent or "Execute" to proceed
            embed = discord.Embed(
                title="📊 XP Reset Preview",
                description=f"Ready to reset XP to season `{new_season_id}`",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="Scope",
                value=f"System-wide (all guilds)",
                inline=False
            )
            
            embed.add_field(
                name="Options",
                value=(
                    "🧪 **Dry Run**: Record intent in MongoDB without mutations\n"
                    "⚡ **Execute Reset**: Apply mutations (requires typed confirmation)\n"
                    "❌ **Cancel**"
                ),
                inline=False
            )
            
            embed.set_footer(text="After dry-run, check MongoDB system_operations collection")
            
            # Preview dict for view - will be populated during dry-run
            preview = {"total_users": 0, "sample_users": []}
            view = XPResetConfirmView(self, interaction.user.id, preview, new_season_id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        except Exception as e:
            if logger:
                logger.error(f"[⚡] XP reset preview failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Preview failed: {str(e)}", ephemeral=True)

    async def show_xp_reset_timing_confirmation(self, interaction: discord.Interaction, new_season_id: str) -> None:
        """Show timing options for XP reset execution."""
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="⚡ Choose Announcement Timing",
            description="XP reset will be applied immediately, but you can choose when to announce it.",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="🚀 Send Now (All Guilds)",
            value="Send announcement immediately to all guild channels (priority queue)",
            inline=False
        )
        
        embed.add_field(
            name="📅 Queue for Tomorrow",
            value="Queue announcement for next daily announcement run (standard timing)",
            inline=False
        )
        
        embed.set_footer(text="Both options will reset XP immediately; only announcement timing differs")
        
        view = XPResetExecuteView(self, interaction.user.id, new_season_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def execute_xp_reset_operation(
        self,
        interaction: discord.Interaction,
        new_season_id: str,
        dry_run: bool = False,
        immediate: bool = False,
    ) -> None:
        """Execute XP reset with atomic transaction boundaries and rollback.
        
        **ATOMICITY:** Multi-phase operation with rollback on failure:
        - Phase A: Create operation + snapshot
        - Phase B: Apply mutation (atomic)
        - Phase C: Update summaries
        - Phase D: Record announcement event
        - Phase E: Trigger delivery (if immediate)
        
        If any phase fails, operation is marked as failed and rollback is attempted.
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            from abby_core.system.season_reset_operations import (
                create_xp_season_reset,
                apply_xp_season_reset,
            )
            from abby_core.system.system_operations import mark_operation_failed
            
            # Phase A: Create operation + snapshot (atomic)
            operation = None
            try:
                operation = create_xp_season_reset(
                    guild_ids=[],  # System-wide
                    new_season_id=new_season_id,
                    dry_run=dry_run,
                    operator_id=interaction.user.id,
                    reason=f"Operator reset via /operator panel",
                )
            except Exception as phase_a_error:
                if logger:
                    logger.error(f"[❌] Phase A (create operation) failed: {phase_a_error}", exc_info=True)
                await interaction.followup.send(
                    f"❌ Failed to create operation: {str(phase_a_error)[:200]}",
                    ephemeral=True
                )
                return
            
            if not operation:
                await interaction.followup.send("❌ Failed to create operation.", ephemeral=True)
                return
            
            op_id = operation["operation_id"]
            affected = operation["affected_count"]
            
            if dry_run:
                # Dry-run only; don't apply mutations
                embed = discord.Embed(
                    title="🧪 Dry-Run Complete",
                    description=f"Operation recorded without mutations",
                    color=discord.Color.blue()
                )
                
                embed.add_field(name="Operation ID", value=f"`{op_id}`", inline=False)
                embed.add_field(name="Affected Users", value=str(affected), inline=False)
                embed.add_field(
                    name="Next Steps",
                    value="Check MongoDB `system_operations` to verify intent, then execute or cancel.",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                if logger:
                    logger.warning(f"[🧪] XP reset DRY RUN: {affected} users, op_id={op_id}")
            else:
                # Phase B+C+D: Apply mutation with rollback on failure
                try:
                    success, details = apply_xp_season_reset(op_id, [])
                    
                    if not success:
                        raise Exception(details.get("error", "Unknown mutation error"))
                    
                    # Phase E: Log queued status (scheduler handles delivery)
                    if immediate and details.get("event_id"):
                        try:
                            from abby_core.services.content_delivery import set_priority
                            
                            set_priority(details["event_id"], priority=True)
                            if logger:
                                logger.info(f"[📢] Announcement queued for scheduler (event_id={details['event_id']}, priority=high)")
                        except Exception as priority_error:
                            if logger:
                                logger.warning(f"[⚠️] Priority set failed (non-fatal): {priority_error}")
                    
                    timing_text = "priority queued: scheduler will process within 60s" if immediate else "queued for next scheduled generation and delivery"
                    
                    embed = discord.Embed(
                        title="✅ XP Reset Complete",
                        description=f"Reset XP for **{details['success_count']}** users",
                        color=discord.Color.green()
                    )
                    
                    embed.add_field(name="Operation ID", value=f"`{op_id}`", inline=False)
                    embed.add_field(name="Success Count", value=str(details["success_count"]), inline=False)
                    embed.add_field(name="Failure Count", value=str(details["failure_count"]), inline=False)
                    if details.get("event_id"):
                        embed.add_field(name="Announcement Event", value=f"`{details['event_id']}`", inline=False)
                        embed.add_field(name="Announcement Timing", value=timing_text, inline=False)
                    
                    embed.set_footer(text="User summaries have been recomputed")
                    
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    
                    if logger:
                        logger.warning(f"[✅] XP reset APPLIED: {details['success_count']} users, op_id={op_id}")
                        
                except Exception as mutation_error:
                    # ROLLBACK: Mark operation as failed
                    if logger:
                        logger.error(f"[❌] Mutation failed, rolling back operation {op_id}: {mutation_error}", exc_info=True)
                    try:
                        mark_operation_failed(op_id, f"Mutation failed: {str(mutation_error)[:200]}")
                    except Exception as rollback_err:
                        if logger:
                            logger.error(f"[❌] Failed to mark operation as failed: {rollback_err}")
                    
                    await interaction.followup.send(
                        f"❌ Mutation failed: {str(mutation_error)[:200]}\n"
                        f"Operation {op_id} marked as failed. Check logs for details.",
                        ephemeral=True
                    )
        
        except Exception as e:
            if logger:
                logger.error(f"[⚡] XP reset execution failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Execution failed: {str(e)}", ephemeral=True)

    async def show_rollback_operations(self, interaction: discord.Interaction) -> None:
        """Show recent operations eligible for rollback."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # NOTE: system_operations module removed - feature disabled
            # from abby_core.economy.system_operations import list_operations
            
            # Feature disabled - module removed
            await interaction.followup.send(
                "❌ Rollback operations feature is currently unavailable.",
                ephemeral=True
            )
            return
            
            # Get recent APPLIED operations
            # applied_ops = list_operations(
            #     op_type="xp_season_reset",
            #     status="applied",
            #     limit=5,
            # )
            
            if not applied_ops:
                await interaction.followup.send("❌ No recent operations to rollback.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="↩️ Rollback Operations",
                description="Select an operation to rollback",
                color=discord.Color.red()
            )
            
            for op in applied_ops:
                timestamp = op.get("applied_at", op.get("created_at", "?"))
                embed.add_field(
                    name=f"{op['op_type']}: {op.get('scope')}",
                    value=f"ID: `{op['id']}`\nApplied: {timestamp}\nAffected: {op.get('success_count', 0)} users",
                    inline=False
                )
            
            # For now, just show the most recent one
            if applied_ops:
                op = applied_ops[0]
                view = RollbackOperationView(self, interaction.user.id, op["id"])
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        except Exception as e:
            if logger:
                logger.error(f"[⚡] Rollback list failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Failed to list operations: {str(e)}", ephemeral=True)

    async def execute_rollback_operation(self, interaction: discord.Interaction, operation_id: str) -> None:
        """Execute rollback of an operation."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # NOTE: season_reset_operations module removed - feature disabled
            # from abby_core.economy.season_reset_operations import rollback_xp_season_reset
            
            # Feature disabled - module removed
            await interaction.followup.send(
                "❌ Rollback feature is currently unavailable.",
                ephemeral=True
            )
            return
            
            # success, details = rollback_xp_season_reset(operation_id)
            
            if success:
                embed = discord.Embed(
                    title="✅ Rollback Complete",
                    description="Data restored from snapshot",
                    color=discord.Color.green()
                )
                
                embed.add_field(name="Operation ID", value=f"`{operation_id}`", inline=False)
                embed.set_footer(text="All affected users have been restored to pre-mutation state")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                if logger:
                    logger.warning(f"[↩️] Rollback COMPLETE for operation {operation_id}")
            else:
                await interaction.followup.send(
                    f"❌ Rollback failed: {details.get('error', 'Unknown error')}",
                    ephemeral=True
                )
        
        except Exception as e:
            if logger:
                logger.error(f"[⚡] Rollback execution failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Rollback failed: {str(e)}", ephemeral=True)

    async def show_announcement_preview(self, interaction: discord.Interaction, content: str) -> None:
        """Show preview of world announcement with LLM enhancement via background task."""
        await interaction.response.defer(ephemeral=True)
        
        # Show immediate response without LLM generation
        embed = discord.Embed(
            title="📢 World Announcement Preview",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📝 Original Content",
            value=content[:400] + ("..." if len(content) > 400 else ""),
            inline=False
        )
        
        embed.add_field(
            name="✨ Enhanced Version",
            value="⏳ **Generating...** (generating enhanced message with personality)\n\nThis will update in a moment",
            inline=False
        )
        
        embed.add_field(
            name="📋 Distribution",
            value="Will be sent to all guild announcement channels\n**Not the same as `/announce` (guild-scoped)**",
            inline=False
        )
        
        embed.set_footer(text=f"Operator: {interaction.user.display_name} • Generation in progress...")
        
        view = SendAnnouncementConfirmView(self, interaction.user.id, content, None)
        message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        # Queue background enhancement task (type: Optional[discord.Message])
        asyncio.create_task(self._enhance_announcement_background(
            message,
            interaction.user.id,
            content,
            view
        ))

    async def _enhance_announcement_background(
        self,
        message: Optional[discord.Message],
        user_id: int,
        content: str,
        view: "SendAnnouncementConfirmView"
    ) -> None:
        """Background task to enhance announcement with LLM and update the message."""
        if not message:
            if logger:
                logger.warning("[📢] Message not available for background enhancement")
            return
        
        try:
            from abby_core.services.conversation_service import get_conversation_service
            from abby_core.llm.context_factory import build_conversation_context
            
            # Generate enhanced message
            user_prompt = (
                f"Take this announcement and enhance it with personality, enthusiasm, and charm while keeping "
                f"the core message. Keep it concise (under 200 words) and maintain the event/news focus:\n\n"
                f"\"{content}\""
            )
            
            context = build_conversation_context(
                user_id="system:operator",
                user_name="Operator",
                is_final_turn=False,
                turn_number=1,
            )
            
            conversation_service = get_conversation_service()
            enhanced_message, error = await conversation_service.generate_response(user_prompt, context, max_retries=1, max_tokens=300)
            if error or enhanced_message is None:
                if logger:
                    logger.warning(f"[Operator Panel] Announcement enhancement failed: {error or 'no response'}")
                enhanced_message = content  # Fallback to original
            
            if logger:
                logger.info(f"[📢] LLM enhanced world announcement in background")
            
            # Update view's enhanced message
            await view.update_enhanced_message(enhanced_message)
            
            # Update message with enhanced version
            embed = discord.Embed(
                title="📢 World Announcement Preview",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📝 Original Content",
                value=content[:400] + ("..." if len(content) > 400 else ""),
                inline=False
            )
            
            embed.add_field(
                name="✨ Enhanced Version",
                value=enhanced_message[:400] + ("..." if len(enhanced_message) > 400 else ""),
                inline=False
            )
            
            embed.add_field(
                name="📋 Distribution",
                value="Will be sent to all guild announcement channels\n**Not the same as `/announce` (guild-scoped)**",
                inline=False
            )
            
            # Get operator name from original footer
            original_footer = message.embeds[0].footer.text if message.embeds and message.embeds[0].footer else None
            if original_footer and " • " in original_footer:
                operator_part = original_footer.split(" • ")[0]
            else:
                operator_part = original_footer or "Operator: Unknown"
            
            embed.set_footer(text=f"{operator_part} • ✅ Ready to send")
            
            # Update original message with enhanced version
            await message.edit(embed=embed)
            
        except Exception as e:
            if logger:
                logger.debug(f"[📢] LLM enhancement failed: {e}")
            
            # Update message to show enhancement failed but can still proceed
            try:
                embed = discord.Embed(
                    title="📢 World Announcement Preview",
                    color=discord.Color.orange()
                )
                
                embed.add_field(
                    name="📝 Original Content",
                    value=content[:400] + ("..." if len(content) > 400 else ""),
                    inline=False
                )
                
                embed.add_field(
                    name="✨ Enhanced Version",
                    value="_(Enhancement failed - will use original message)_",
                    inline=False
                )
                
                embed.add_field(
                    name="📋 Distribution",
                    value="Will be sent to all guild announcement channels\n**Not the same as `/announce` (guild-scoped)**",
                    inline=False
                )
                
                # Get operator name from original footer
                original_footer = message.embeds[0].footer.text if message.embeds and message.embeds[0].footer else None
                if original_footer and " • " in original_footer:
                    operator_part = original_footer.split(" • ")[0]
                else:
                    operator_part = original_footer or "Operator: Unknown"
                
                embed.set_footer(text=f"{operator_part} • Ready to send (using original)")
                
                await message.edit(embed=embed)
            except Exception as update_e:
                if logger:
                    logger.error(f"[📢] Failed to update preview message: {update_e}")

    async def execute_world_announcement_background(self, interaction: discord.Interaction, message: str, immediate: bool, scope: str = "world") -> None:
        """Execute announcement in background without using interaction responses.
        
        This version doesn't defer or send followup messages since the interaction
        has already been responded to. It just processes the announcement silently.
        
        Args:
            interaction: Discord interaction (for user context only, already responded)
            message: Announcement content
            immediate: If True, deliver ASAP; if False, queue for tomorrow
            scope: "guild" for current guild only, "world" for all guilds
        """
        try:
            from abby_core.database.collections.guild_configuration import get_all_guild_configs, get_guild_config
            from abby_core.services.announcement_dispatcher import get_announcement_dispatcher
            import asyncio
            import pytz

            # Get guild configs based on scope
            if scope == "guild":
                # Single guild announcement
                if not interaction.guild_id:
                    if logger:
                        logger.warning("[📢] Cannot send guild-local announcement: No guild context")
                    return
                current_config = get_guild_config(interaction.guild_id)
                if not current_config:
                    if logger:
                        logger.warning("[📢] Cannot send guild-local announcement: Guild not configured")
                    return
                all_configs = [current_config]
            else:
                # World-wide announcement (all guilds)
                all_configs = get_all_guild_configs()
            
            created_ids: list[str] = []

            # Determine scheduled_at (system-wide schedule/timezone)
            from abby_core.database.collections.system_configuration import get_system_config

            system_config = get_system_config()
            system_jobs = system_config.get("system_jobs", {})
            announcements = system_jobs.get("announcements", {})
            daily_job = announcements.get("daily_world_announcements", {})
            schedule = daily_job.get("schedule", {})
            time_str = schedule.get("time", "08:00")
            tz_name = system_config.get("timezone", "UTC")

            def _next_daily_dt() -> datetime:
                try:
                    tz = pytz.timezone(tz_name)
                except Exception:
                    tz = pytz.UTC
                now_local = datetime.now(tz)
                hour, minute = map(int, time_str.split(":")) if ":" in time_str else (8, 0)
                candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if candidate <= now_local:
                    candidate = candidate + timedelta(days=1)
                return candidate.astimezone(pytz.UTC).replace(tzinfo=None)

            # Create items for all guilds with unified pipeline
            for cfg in all_configs:
                guild_id = cfg.get("guild_id")
                if not guild_id:
                    continue

                scheduled_at = datetime.utcnow() if immediate else _next_daily_dt()

                # UPDATED: Use unified content delivery pipeline
                from abby_core.services.content_delivery import create_announcement_for_delivery
                item_id = create_announcement_for_delivery(
                    guild_id=int(guild_id),
                    content_type="world",
                    title="World Announcement",
                    description=message,
                    scheduled_at=scheduled_at,
                    delivery_channel_id=None,
                    delivery_roles=[],
                    operator_id=f"user:{interaction.user.id}",
                    context={
                        "event_type": "world_announcement",
                        "trigger": "operator_messaging",
                        "operator_id": interaction.user.id,
                    },
                    context_refs={
                        "event_type": "world_announcement",
                        "trigger": "operator_messaging",
                        "operator_id": interaction.user.id,
                    },
                )
                created_ids.append(item_id)
                
                # Use unified pipeline for content generation
                try:
                    from abby_core.services.content_delivery import mark_announcement_generated
                    mark_announcement_generated(
                        item_id=item_id,
                        generated_message=message,
                        operator_id=f"user:{interaction.user.id}"
                    )
                except Exception as e:
                    if logger:
                        logger.error(f"[📢] Failed to generate content for item {item_id}: {e}")
                
                await asyncio.sleep(0.05)

            if logger:
                logger.info(
                    f"[📢] OPERATOR ANNOUNCEMENT: {interaction.user.id} created announcement "
                    f"(scope={scope}, immediate={immediate}, items={len(created_ids)})"
                )

        except Exception as e:
            if logger:
                logger.error(f"[📢] Background announcement failed: {e}", exc_info=True)

    async def execute_world_announcement(self, interaction: discord.Interaction, message: str, immediate: bool, scope: str = "world") -> None:
        """Execute announcement with atomic transaction boundaries.
        
        **Architectural Fix:**
        - Recording Layer (HERE): Create content items with rollback on failure
        - Generation Layer (Background Worker): LLM batching  
        - Delivery Layer (Scheduler Job): Actually send messages
        
        **ATOMICITY:** All phases wrapped in try/except with rollback.
        If any phase fails, created items are marked as failed and no delivery occurs.
        
        For immediate=True, we record and immediately trigger the delivery job.
        For immediate=False, we record for next scheduled run.
        
        Args:
            interaction: Discord interaction
            message: Announcement content
            immediate: If True, deliver ASAP; if False, queue for tomorrow
            scope: "guild" for current guild only, "world" for all guilds
        """
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.database.collections.guild_configuration import get_all_guild_configs, get_guild_config
            import asyncio
            import pytz

            # Get guild configs based on scope
            if scope == "guild":
                # Single guild announcement
                if not interaction.guild_id:
                    await interaction.followup.send(
                        "❌ Cannot send guild-local announcement: No guild context.",
                        ephemeral=True
                    )
                    return
                current_config = get_guild_config(interaction.guild_id)
                if not current_config:
                    await interaction.followup.send(
                        "❌ Cannot send guild-local announcement: Guild not configured.",
                        ephemeral=True
                    )
                    return
                all_configs = [current_config]
            else:
                # World-wide announcement (all guilds)
                all_configs = get_all_guild_configs()
            
            created_ids: list[str] = []

            # Determine scheduled_at
            def _next_daily_dt(cfg: dict) -> datetime:
                tz_name = cfg.get("scheduling", {}).get("timezone", "UTC")
                time_str = cfg.get("scheduling", {}).get("jobs", {}).get("system", {}).get("daily_world_announcements", {}).get("time", "08:00")
                try:
                    tz = pytz.timezone(tz_name)
                except Exception:
                    tz = pytz.UTC
                now_local = datetime.now(tz)
                hour, minute = map(int, time_str.split(":")) if ":" in time_str else (8, 0)
                candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if candidate <= now_local:
                    candidate = candidate + timedelta(days=1)
                return candidate.astimezone(pytz.UTC).replace(tzinfo=None)

            # PHASE 1: Recording - create items for all guilds (atomic phase)
            # Use unified content delivery pipeline (canonical path)
            try:
                from abby_core.services.content_delivery import create_announcement_for_delivery
                
                for cfg in all_configs:
                    guild_id = cfg.get("guild_id")
                    if not guild_id:
                        continue

                    scheduled_at = datetime.utcnow() if immediate else _next_daily_dt(cfg)

                    item_id = create_announcement_for_delivery(
                        guild_id=int(guild_id),
                        content_type="world",
                        title="World Announcement",
                        description=message,
                        scheduled_at=scheduled_at,
                        delivery_channel_id=None,
                        delivery_roles=[],
                        operator_id=f"user:{interaction.user.id}",
                        context={
                            "event_type": "world_announcement",
                            "trigger": "operator_messaging",
                            "operator_id": interaction.user.id,
                        },
                        context_refs={
                            "event_type": "world_announcement",
                            "trigger": "operator_messaging",
                            "operator_id": interaction.user.id,
                        },
                    )
                    created_ids.append(item_id)
                    
                    # Use unified pipeline for content generation
                    try:
                        from abby_core.services.content_delivery import mark_announcement_generated
                        mark_announcement_generated(
                            item_id=item_id,
                            generated_message=message,
                            operator_id=f"user:{interaction.user.id}"
                        )
                    except Exception as gen_err:
                        if logger:
                            logger.error(f"[❌] Failed to generate content for item {item_id}: {gen_err}")
                    
                    await asyncio.sleep(0.05)
            except Exception as creation_error:
                # ROLLBACK: Mark all created items as failed via unified pipeline
                if logger:
                    logger.error(f"[❌] World announcement creation failed: {creation_error}", exc_info=True)
                from abby_core.services.content_delivery import mark_announcement_generation_failed
                for item_id in created_ids:
                    try:
                        mark_announcement_generation_failed(
                            item_id=item_id,
                            error_message=f"Creation rollback: {str(creation_error)[:200]}",
                            operator_id=f"user:{interaction.user.id}"
                        )
                    except Exception as rollback_err:
                        if logger:
                            logger.error(f"[❌] Failed to rollback item {item_id}: {rollback_err}")
                
                await interaction.followup.send(
                    f"❌ World announcement creation failed: {str(creation_error)[:200]}\n"
                    f"Rolled back {len(created_ids)} items.",
                    ephemeral=True
                )
                return

            timing_text = "recorded for immediate delivery" if immediate else "queued for next scheduled run"
            scope_text = "This Guild Only" if scope == "guild" else "All Guilds (World)"

            embed = discord.Embed(
                title="✅ Announcement Created",
                color=discord.Color.green()
            )

            embed.add_field(
                name="📢 Content",
                value=message[:400] + ("..." if len(message) > 400 else ""),
                inline=False
            )

            embed.add_field(
                name="📋 Distribution",
                value=f"**Scope:** {scope_text}\n{timing_text}\nto {len(created_ids)} guild(s)",
                inline=False
            )

            # PHASE 2 & 3: Trigger delivery pipeline
            if immediate:
                embed.add_field(
                    name="⚙️ Processing Pipeline",
                    value=(
                        "1. **Recording** ✅\n"
                        "2. **Generation** ✅ (via dispatcher)\n"
                        "3. **Delivery** ⏳ (scheduler will deliver within 60s)"
                    ),
                    inline=False
                )
                
                embed.add_field(
                    name="⏰ Scheduler Status",
                    value="Content items queued for next scheduler tick (every 60s)",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚙️ Processing Pipeline",
                    value=(
                        "1. **Recording** ✅\n"
                        "2. **Generation** 🔄 (background worker batching)\n"
                        "3. **Delivery** ⏳ (next scheduled run)"
                    ),
                    inline=False
                )

            embed.add_field(
                name="🛡️ Audit Trail",
                value=f"Operator: {interaction.user.mention}\nItems: {len(created_ids)} created",
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            if logger:
                logger.info(
                    f"[📢] OPERATOR ANNOUNCEMENT: {interaction.user.id} created announcement "
                    f"(scope={scope}, immediate={immediate}, items={len(created_ids)})"
                )

        except Exception as e:
            if logger:
                logger.error(f"[📢] Announcement failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Announcement failed: {str(e)}", ephemeral=True)

    async def build_embed_for_tab(
        self,
        interaction: discord.Interaction,
        tab: str,
        economy_section: str = "xp",
        system_subtab: str = "events",
    ) -> discord.Embed:
        if tab == "economy":
            return await self.build_economy_embed(interaction, economy_section)
        if tab == "system":
            return await self.build_system_embed(interaction, system_subtab)
        if tab == "data":
            return await self.build_data_memory_embed(interaction)
        if tab == "diagnostics":
            return await self.build_diagnostics_embed(interaction)
        return await self.build_overview_embed(interaction)

    async def update_operator_panel(
        self,
        interaction: discord.Interaction,
        tab: str,
        economy_section: str = "xp",
        system_subtab: str = "events",
    ) -> None:
        embed = await self.build_embed_for_tab(
            interaction,
            tab,
            economy_section=economy_section,
            system_subtab=system_subtab,
        )
        view = OperatorView(
            self,
            interaction.user.id,
            active_tab=tab,
            economy_section=economy_section,
            system_subtab=system_subtab,
        )

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)
    
    @app_commands.command(name="operator", description="[Operator Only] Advanced bot controls")
    async def operator(self, interaction: discord.Interaction):
        """Operator-only control panel."""
        if not is_operator(interaction.user.id):
            await interaction.response.send_message(
                "❌ You don't have operator permissions.",
                ephemeral=True
            )
            return
        
        embed = await self.build_overview_embed(interaction)
        view = OperatorView(self, interaction.user.id, active_tab="overview")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def build_overview_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Build the operator overview embed."""
        embed = discord.Embed(
            title="🔧 Operator Control Panel",
            description="Platform-level maintenance, recovery, and integrity tools",
            color=discord.Color.red()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=getattr(interaction.user.display_avatar, "url", None)
        )
        
        embed.add_field(
            name="🏠 Scope",
            value=(
                "Operator = platform governor, not guild admin.\n"
                "Imperative actions only: run, reset, inspect."
            ),
            inline=False
        )
        
        # Environment detection
        environment = _get_environment()
        embed.add_field(
            name="🌐 Environment",
            value=f"Environment: {environment}\nAudit logging: {'enabled' if logger else 'unknown'}",
            inline=False
        )
        
        # Platform health (read-only confidence signals)
        health = self._get_platform_health()
        health_emoji = {
            "running": "🟢",
            "healthy": "🟢",
            "applied": "🟢",
            "not loaded": "🟡",
            "unavailable": "🔴"
        }
        
        health_lines = []
        for key, status in health.items():
            emoji = "🟢"
            if "unavailable" in status or "not loaded" in status:
                emoji = "🟡" if "not loaded" in status else "🔴"
            elif "loaded" in status:
                emoji = "🟢"
            health_lines.append(f"{emoji} {key.title()}: {status}")
        
        embed.add_field(
            name="💚 Platform Health",
            value="\n".join(health_lines),
            inline=False
        )
        
        embed.add_field(
            name="📋 Sections",
            value=(
                "⭐ Economy Operations — user vs system XP ops\n"
                "🧠 Data & Memory — inspect, force maintenance\n"
                "🛠 Diagnostics — recovery & debug lane"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Access Level",
            value=f"Operator ID: {interaction.user.id}",
            inline=False
        )
        
        embed.set_footer(text="Use buttons to navigate • Operator never configures policy; only executes")
        return embed
    
    async def build_economy_embed(self, interaction: discord.Interaction, economy_section: str = "xp") -> discord.Embed:
        """Economy operations (user-scoped vs system-scoped)."""
        from abby_core.system.system_state import get_active_season
        
        active_season = get_active_season()
        season_label = active_season.get("label", "Unknown") if active_season else "No active season"
        section_labels = {
            "xp": "🧪 XP Actions",
            "levels": "🎖️ Level Actions",
            "advanced": "⚠️ Advanced Actions",
        }
        active_label = section_labels.get(economy_section, "🧪 XP Actions")
        
        embed = discord.Embed(
            title=f"⭐ Economy • {active_label}",
            description="Switch sections with the selector to keep the surface minimal.",
            color=discord.Color.gold()
        )
        
        if economy_section == "xp":
            embed.add_field(
                name="🧪 XP Actions",
                value=(
                    "➕ Add XP — grant to a single user\n"
                    "➖ Remove XP — subtract from a single user\n"
                    "🔄 Reset User XP — zero out a single user"
                ),
                inline=False
            )
        elif economy_section == "levels":
            embed.add_field(
                name="🎖️ Level Actions",
                value=(
                    "📊 View User Level — show permanent level record\n"
                    "⬇️ Reset User Level — set level to 1 (audit + reason required)"
                ),
                inline=False
            )
        elif economy_section == "advanced":
            embed.add_field(
                name="⚠️ Advanced Actions",
                value=(
                    "⚡ Reset All XP (Season) — guarded, timing confirmation\n"
                    "🎯 Reset All Levels (Guild) — force levels to 1 for this guild\n"
                    "🌐 Initialize Missing Records — bootstrap XP docs for all non-bots"
                ),
                inline=False
            )
        
        embed.add_field(
            name="🌍 Current Season",
            value=f"**{season_label}**\nXP resets seasonally. Levels are permanent.",
            inline=False
        )
        
        embed.set_footer(text="Section selector keeps buttons focused • Advanced actions are gated")
        return embed

    async def build_system_embed(self, interaction: discord.Interaction, system_subtab: str = "status") -> discord.Embed:
        """System subtab overview (Status, Event Management, DLQ Inspector, Metrics)."""
        section_labels = {
            "status": "📋 System • Status",
            "events": "📅 System • Event Management",
            "dlq": "🚨 System • DLQ Inspector",
            "metrics": "📊 System • Metrics Dashboard",
        }
        title = section_labels.get(system_subtab, "📋 System • Status")

        embed = discord.Embed(
            title=title,
            description="Switch subtabs using the selector to focus on a specific system lane.",
            color=discord.Color.blue()
        )

        if system_subtab == "status":
            embed.add_field(
                name="📋 System Status Commands",
                value=(
                    "All Systems — complete platform state\n"
                    "Seasons — active and upcoming seasons\n"
                    "Events — active and upcoming events\n"
                    "Effects — currently active effects\n"
                    "Jobs — background job status and execution"
                ),
                inline=False
            )
            embed.set_footer(text="View documented system status • All commands from SYSTEM_STATUS_COMMANDS.md")
        elif system_subtab == "events":
            embed.add_field(
                name="📅 Event Management",
                value=(
                    "List Upcoming Events — view scheduled system events\n"
                    "Create Event — schedule new system events\n"
                    "Preview States — inspect state timeline\n"
                    "Rollback Operation — emergency rollback (if available)"
                ),
                inline=False
            )
            embed.set_footer(text="Manage canon events and system states")
        elif system_subtab == "dlq":
            embed.add_field(
                name="🚨 DLQ Inspector",
                value=(
                    "List DLQ — view recent failures\n"
                    "Retry Item — execute a retry now\n"
                    "Discard Item — mark as abandoned\n"
                    "DLQ Stats — status + category counts"
                ),
                inline=False
            )
        elif system_subtab == "metrics":
            embed.add_field(
                name="📊 Metrics Dashboard",
                value=(
                    "Dashboard — last 24h performance\n"
                    "7-Day Trend — error trend over time\n"
                    "By Guild — top activity breakdown\n"
                    "Cost Analysis — estimate cost footprint"
                ),
                inline=False
            )

        if system_subtab != "status":
            embed.set_footer(text="System subtabs keep actions scoped • DLQ actions are auditable")
        return embed
    
    async def build_data_memory_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Data integrity and memory operations."""
        embed = discord.Embed(
            title="🧠 Data & Memory Operations",
            description="Inspect profiles, force maintenance, and view integrity stats.",
            color=discord.Color.purple()
        )
        
        # Get some stats
        total_profiles = 0
        total_facts = 0
        
        try:
            from abby_core.database.collections.users import get_guild_profile_stats
            guild_id = str(interaction.guild.id) if interaction.guild else None

            if guild_id:
                stats = get_guild_profile_stats(guild_id)
                total_profiles = stats.get("total_profiles", 0)
                total_facts = stats.get("total_facts", 0)
        except Exception as e:
            if logger:
                logger.warning(f"[🔧] Failed to get memory stats: {e}")
        
        embed.add_field(
            name="📊 Current Server Stats",
            value=f"👥 Profiles: {total_profiles:,}\n🧠 Total Memories: {total_facts:,}",
            inline=False
        )
        
        embed.add_field(
            name="Available Actions",
            value=(
                "🔍 Inspect User — view a profile snapshot\n"
                "🔧 Run Maintenance — force decay/repair\n"
                "📊 View Stats — guild memory footprint"
            ),
            inline=False
        )
        
        embed.set_footer(text="Handle user data with care • GDPR compliant")
        return embed

    async def inspect_user_memory(self, interaction: discord.Interaction, target_user: discord.abc.User):
        """Fetch and display a user's memory profile after selection."""
        await interaction.response.defer(ephemeral=True)

        if not self.memory_service:
            await interaction.followup.send("❌ Memory system unavailable.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id) if interaction.guild else None
        profile = self.memory_service.get_profile(str(target_user.id), guild_id)

        if not profile:
            await interaction.followup.send(
                f"❌ No memory profile found for {getattr(target_user, 'display_name', target_user.name)}.",
                ephemeral=True
            )
            return

        facts = profile.get("creative_profile", {}).get("memorable_facts", [])

        embed = discord.Embed(
            title=f"🔍 Memory Profile: {getattr(target_user, 'display_name', target_user.name)}",
            description=f"Total memories: {len(facts)}",
            color=discord.Color.orange()
        )

        for i, fact in enumerate(facts[:10], 1):
            confidence = fact.get("confidence", 0)
            text = fact.get("text", "Unknown")
            embed.add_field(
                name=f"Memory {i} (Confidence: {confidence:.2f})",
                value=text[:200] + ("..." if len(text) > 200 else ""),
                inline=False
            )

        if len(facts) > 10:
            embed.add_field(
                name="📊",
                value=f"...and {len(facts) - 10} more memories",
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

        if logger:
            logger.info(f"[🔧] Operator {interaction.user.id} inspected user {target_user.id}")
    
    async def reset_user_xp(self, interaction: discord.Interaction, target_user: discord.abc.User):
        """Reset a user's XP to 0."""
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.services.economy_service import get_economy_service
            
            guild_id = interaction.guild.id if interaction.guild else None
            economy_service = get_economy_service()
            
            success, error = economy_service.reset_xp(target_user.id, guild_id)
            
            if not success:
                await interaction.followup.send(f"❌ Failed: {error}", ephemeral=True)
                return

            user_name = getattr(target_user, "display_name", None) or getattr(target_user, "name", f"User {target_user.id}")

            await interaction.followup.send(
                f"✅ Reset {user_name}'s XP to 0",
                ephemeral=True
            )

            if logger:
                logger.info(f"[🔧] Operator {interaction.user.id} reset XP for {target_user.id}")

        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to reset user XP: {e}")
            await interaction.followup.send(
                f"❌ Failed to reset XP. Please try again. ({e})",
                ephemeral=True
            )
    
    async def view_user_level(self, interaction: discord.Interaction, target_user: discord.abc.User):
        """View a user's permanent level record."""
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.economy.user_levels import get_user_level_record
            
            if not interaction.guild:
                await interaction.followup.send("❌ This action requires a guild.", ephemeral=True)
                return

            guild_id = str(interaction.guild.id)
            user_id = str(target_user.id)
            
            level_record = get_user_level_record(user_id, guild_id)
            
            if not level_record:
                await interaction.followup.send(
                    f"📊 **Level Record for {target_user.display_name}**\n"
                    f"Status: No level record found\n"
                    f"Note: User may not have earned XP yet in this guild.",
                    ephemeral=True
                )
                return
            
            current_level = level_record.get("level", 1)
            season_id = level_record.get("season_id", "unknown")
            last_updated = level_record.get("updated_at")
            
            timestamp_str = f"<t:{int(last_updated.timestamp())}:R>" if last_updated else "N/A"
            
            await interaction.followup.send(
                f"📊 **Level Record for {target_user.display_name}**\n"
                f"Level: **{current_level}**\n"
                f"Season: `{season_id}`\n"
                f"Last Updated: {timestamp_str}",
                ephemeral=True
            )

            if logger:
                logger.info(f"[🔧] Operator {interaction.user.id} viewed level for user {target_user.id}")

        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to view user level: {e}")
            await interaction.followup.send(
                f"❌ Failed to view level record. ({e})",
                ephemeral=True
            )
    
    async def reset_user_level(self, interaction: discord.Interaction, target_user: discord.abc.User):
        """Reset a user's permanent level to 1 with audit trail (requires reason)."""
        # Show modal for reason entry
        modal = ResetUserLevelModal(self, target_user)
        await interaction.response.send_modal(modal)

    async def execute_user_level_reset(
        self, 
        interaction: discord.Interaction, 
        target_user: discord.abc.User,
        reason: str
    ):
        """Execute the level reset after collecting reason."""
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.services.economy_service import get_economy_service
            
            if not interaction.guild:
                await interaction.followup.send("❌ This action requires a guild.", ephemeral=True)
                return

            guild_id = interaction.guild.id
            economy_service = get_economy_service()
            
            success, error = economy_service.reset_level(target_user.id, guild_id, reason)
            
            if not success:
                await interaction.followup.send(f"❌ Failed: {error}", ephemeral=True)
                return
            
            await interaction.followup.send(
                f"✅ Reset {target_user.display_name}'s level to 1\n"
                f"Reason: {reason}",
                ephemeral=True
            )

            if logger:
                logger.info(
                    f"[🔧] Operator {interaction.user.id} reset level for user {target_user.id} "
                    f"(reason: {reason})"
                )

        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to reset user level: {e}")
            await interaction.followup.send(
                f"❌ Failed to reset level. ({e})",
                ephemeral=True
            )

    async def execute_reset_all_levels(self, interaction: discord.Interaction, reason: str) -> None:
        """Reset all users' levels in the current guild to 1 with audit trail."""
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.services.economy_service import get_economy_service

            if not interaction.guild:
                await interaction.followup.send("❌ This action requires a guild.", ephemeral=True)
                return

            guild_id = interaction.guild.id
            economy_service = get_economy_service()
            
            count, error = economy_service.reset_all_levels(guild_id, reason)
            
            if error:
                await interaction.followup.send(f"❌ Failed: {error}", ephemeral=True)
                return

            await interaction.followup.send(
                f"✅ Reset levels to 1 for {count} users in this guild.\n"
                f"Reason: {reason}",
                ephemeral=True,
            )

            if logger:
                logger.info(
                    f"[🔧] Operator {interaction.user.id} reset all levels in guild {guild_id} "
                    f"(modified={count}, reason={reason})"
                )

        except Exception as e:
            if logger:
                logger.error(f"[🔧] Guild level reset failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Guild level reset failed: {e}", ephemeral=True)

    async def initialize_all_xp(self, interaction: discord.Interaction, guild_id: Optional[int] = None):
        """Initialize XP for all guild members (confirmation-gated)."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild
            target_guild_id = guild_id or (guild.id if guild else None)

            if not guild or guild.id != target_guild_id:
                await interaction.followup.send("❌ This action requires the originating guild context.", ephemeral=True)
                return

            if not increment_xp or not initialize_xp:
                await interaction.followup.send("❌ XP system unavailable.", ephemeral=True)
                return

            initialized_count = 0

            for member in guild.members:
                if member.bot:
                    continue
                try:
                    user_data = get_xp(member.id) or {}
                    if user_data.get("points", 0) == 0:
                        initialize_xp(member.id, guild.id)
                        initialized_count += 1
                except Exception as e:
                    if logger:
                        logger.warning(f"[🔧] Failed to initialize XP for {member.id}: {e}")
                    continue

            await interaction.followup.send(
                f"✅ Initialized XP for {initialized_count} users in {guild.name}",
                ephemeral=True
            )

            if logger:
                logger.info(f"[🔧] Operator {interaction.user.id} initialized XP for {initialized_count} users in guild {guild.id}")

        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to initialize all XP: {e}")
            await interaction.followup.send(
                f"❌ Failed to initialize XP. Please try again. ({e})",
                ephemeral=True
            )

    async def show_dlq_list(self, interaction: discord.Interaction) -> None:
        """Display recent DLQ items with status summary."""
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.services.dlq_service import get_dlq_service, DLQStatus

            dlq_service = get_dlq_service()

            total = dlq_service.collection.count_documents({})
            status_counts = {
                "pending": dlq_service.collection.count_documents({"status": DLQStatus.PENDING.value}),
                "retrying": dlq_service.collection.count_documents({"status": DLQStatus.RETRYING.value}),
                "resolved": dlq_service.collection.count_documents({"status": DLQStatus.RESOLVED.value}),
                "abandoned": dlq_service.collection.count_documents({"status": DLQStatus.ABANDONED.value}),
            }

            items = list(
                dlq_service.collection.find({})
                .sort("created_at", -1)
                .limit(10)
            )

            embed = discord.Embed(
                title="🚨 System > DLQ Inspector",
                description="Recent failed announcements and recovery status.",
                color=discord.Color.red(),
            )

            embed.add_field(
                name="📊 Status Summary",
                value=(
                    f"Total: {total}\n"
                    f"Pending: {status_counts['pending']}\n"
                    f"Retrying: {status_counts['retrying']}\n"
                    f"Resolved: {status_counts['resolved']}\n"
                    f"Abandoned: {status_counts['abandoned']}"
                ),
                inline=False,
            )

            if not items:
                embed.add_field(
                    name="✅ No DLQ Items",
                    value="There are no pending or historical DLQ items.",
                    inline=False,
                )
            else:
                for idx, item in enumerate(items[:5], 1):
                    error_msg = item.get("error_message", "")
                    if len(error_msg) > 120:
                        error_msg = f"{error_msg[:117]}..."
                    embed.add_field(
                        name=f"[{idx}] Item {str(item.get('_id'))[:8]}...",
                        value=(
                            f"Status: {item.get('status')}\n"
                            f"Category: {item.get('error_category')}\n"
                            f"Retries: {item.get('retry_count', 0)}/{item.get('max_retries', 3)}\n"
                            f"Error: {error_msg or 'N/A'}"
                        ),
                        inline=False,
                    )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            if logger:
                logger.error(f"[🔧] DLQ list failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Failed to load DLQ list: {e}", ephemeral=True)

    async def show_dlq_stats(self, interaction: discord.Interaction) -> None:
        """Display DLQ statistics by status and category."""
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.services.dlq_service import get_dlq_service

            dlq_service = get_dlq_service()

            status_pipeline = [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
            category_pipeline = [
                {"$group": {"_id": "$error_category", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]

            status_results = list(dlq_service.collection.aggregate(status_pipeline))
            category_results = list(dlq_service.collection.aggregate(category_pipeline))

            embed = discord.Embed(
                title="📊 System > DLQ Stats",
                description="Summary of DLQ status and error categories.",
                color=discord.Color.orange(),
            )

            if status_results:
                status_lines = [f"{r['_id']}: {int(r['count'])}" for r in status_results]
                embed.add_field(name="By Status", value="\n".join(status_lines), inline=False)
            else:
                embed.add_field(name="By Status", value="No DLQ items found.", inline=False)

            if category_results:
                category_lines = [f"{r['_id']}: {int(r['count'])}" for r in category_results]
                embed.add_field(name="By Category", value="\n".join(category_lines), inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            if logger:
                logger.error(f"[🔧] DLQ stats failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Failed to load DLQ stats: {e}", ephemeral=True)

    async def show_dlq_retry_select(self, interaction: discord.Interaction) -> None:
        """Prompt operator to retry a DLQ item by ID."""
        modal = DLQActionModal(self, "retry")
        await interaction.response.send_modal(modal)

    async def show_dlq_discard_select(self, interaction: discord.Interaction) -> None:
        """Prompt operator to discard a DLQ item by ID."""
        modal = DLQActionModal(self, "discard")
        await interaction.response.send_modal(modal)

    async def execute_dlq_retry(self, interaction: discord.Interaction, dlq_id: str) -> None:
        """Execute a DLQ retry immediately."""
        from bson import ObjectId

        try:
            if not ObjectId.is_valid(dlq_id):
                await interaction.followup.send("❌ Invalid DLQ ID.", ephemeral=True)
                return

            from abby_core.services.dlq_service import get_dlq_service

            dlq_service = get_dlq_service()
            operator_id = f"operator:{interaction.user.id}"
            success = dlq_service.execute_retry(dlq_id, operator_id=operator_id)

            if success:
                await interaction.followup.send(f"✅ Retry succeeded for {dlq_id[:8]}...", ephemeral=True)
            else:
                await interaction.followup.send(f"⚠️ Retry failed for {dlq_id[:8]}...", ephemeral=True)

        except Exception as e:
            if logger:
                logger.error(f"[🔧] DLQ retry failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Retry failed: {e}", ephemeral=True)

    async def execute_dlq_discard(self, interaction: discord.Interaction, dlq_id: str) -> None:
        """Discard a DLQ item (mark abandoned)."""
        from bson import ObjectId
        from datetime import datetime as dt

        try:
            if not ObjectId.is_valid(dlq_id):
                await interaction.followup.send("❌ Invalid DLQ ID.", ephemeral=True)
                return

            from abby_core.services.dlq_service import get_dlq_service, DLQStatus

            dlq_service = get_dlq_service()
            operator_id = f"operator:{interaction.user.id}"

            result = dlq_service.collection.update_one(
                {"_id": ObjectId(dlq_id)},
                {"$set": {
                    "status": DLQStatus.ABANDONED.value,
                    "resolution": "discarded_by_operator",
                    "resolved_at": dt.utcnow(),
                    "resolved_by": operator_id,
                    "updated_at": dt.utcnow(),
                }}
            )

            if result.modified_count > 0:
                await interaction.followup.send(f"🗑️ Discarded {dlq_id[:8]}...", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ DLQ item not found.", ephemeral=True)

        except Exception as e:
            if logger:
                logger.error(f"[🔧] DLQ discard failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Discard failed: {e}", ephemeral=True)

    async def show_metrics_dashboard(self, interaction: discord.Interaction) -> None:
        """Display metrics dashboard (last 24h)."""
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.services.metrics_service import get_metrics_service

            metrics_service = get_metrics_service()
            stats = metrics_service.get_performance_stats(hours=24)

            embed = discord.Embed(
                title="📊 System > Metrics Dashboard",
                description="Performance and error overview (last 24h).",
                color=discord.Color.green(),
            )

            timing = stats.get("timing", {})
            def _fmt_timing(metric_key: str) -> str:
                entry = timing.get(metric_key)
                if not entry:
                    return "n/a"
                return f"{entry.get('avg_seconds', 0):.2f}s"

            embed.add_field(
                name="⏱️ Average Timing",
                value=(
                    f"Generation: {_fmt_timing('generation_time')}\n"
                    f"Queue Wait: {_fmt_timing('queue_wait_time')}\n"
                    f"Delivery: {_fmt_timing('delivery_time')}\n"
                    f"Total Cycle: {_fmt_timing('total_cycle_time')}"
                ),
                inline=False,
            )

            error_stats = stats.get("errors", {})
            if error_stats:
                error_lines = [f"{k}: {v}" for k, v in error_stats.items()]
                embed.add_field(name="🚨 Errors", value="\n".join(error_lines), inline=False)
            else:
                embed.add_field(name="🚨 Errors", value="No errors recorded in last 24h.", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            if logger:
                logger.error(f"[🔧] Metrics dashboard failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Metrics dashboard failed: {e}", ephemeral=True)

    async def show_metrics_trend(self, interaction: discord.Interaction, days: int = 7) -> None:
        """Display error trend for the last N days."""
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.services.metrics_service import get_metrics_service

            metrics_service = get_metrics_service()
            trend = metrics_service.get_error_trend(hours=days * 24)
            by_hour = trend.get("by_hour", {})

            daily_totals: Dict[str, int] = {}
            for hour_key, categories in by_hour.items():
                date_key = hour_key.split("T")[0]
                daily_totals.setdefault(date_key, 0)
                daily_totals[date_key] += sum(int(v) for v in categories.values())

            embed = discord.Embed(
                title="📈 System > Error Trend",
                description=f"Error volume by day (last {days} days).",
                color=discord.Color.blurple(),
            )

            if daily_totals:
                for date_key in sorted(daily_totals.keys())[-days:]:
                    embed.add_field(
                        name=date_key,
                        value=f"Errors: {daily_totals[date_key]}",
                        inline=True,
                    )
            else:
                embed.add_field(name="No Data", value="No errors recorded in this period.", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            if logger:
                logger.error(f"[🔧] Metrics trend failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Metrics trend failed: {e}", ephemeral=True)

    async def show_metrics_by_guild(self, interaction: discord.Interaction) -> None:
        """Display metrics grouped by guild (last 7 days)."""
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.services.metrics_service import get_metrics_service
            from datetime import datetime as dt, timedelta as td

            metrics_service = get_metrics_service()
            since = dt.utcnow() - td(days=7)

            pipeline = [
                {"$match": {"timestamp": {"$gte": since}}},
                {"$group": {"_id": "$guild_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5},
            ]
            results = list(metrics_service.collection.aggregate(pipeline))

            embed = discord.Embed(
                title="🌍 System > Metrics by Guild",
                description="Top guild activity (last 7 days).",
                color=discord.Color.teal(),
            )

            if results:
                for row in results:
                    embed.add_field(
                        name=f"Guild {row['_id']}",
                        value=f"Metrics: {int(row['count'])}",
                        inline=False,
                    )
            else:
                embed.add_field(name="No Data", value="No metrics recorded in this period.", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            if logger:
                logger.error(f"[🔧] Metrics by guild failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Metrics by guild failed: {e}", ephemeral=True)

    async def show_metrics_cost_analysis(self, interaction: discord.Interaction) -> None:
        """Display cost analysis based on recorded metadata (last 30 days)."""
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.services.metrics_service import get_metrics_service
            from datetime import datetime as dt, timedelta as td

            metrics_service = get_metrics_service()
            since = dt.utcnow() - td(days=30)

            pipeline = [
                {"$match": {"timestamp": {"$gte": since}}},
                {"$project": {"cost": {"$ifNull": ["$metadata.cost_usd", 0]}}},
                {"$group": {"_id": None, "total": {"$sum": "$cost"}}},
            ]
            result = list(metrics_service.collection.aggregate(pipeline))
            total_cost = float(result[0]["total"]) if result else 0.0
            projected_50y = total_cost * 12 * 50

            embed = discord.Embed(
                title="💰 System > Cost Analysis",
                description="Estimated cost footprint (last 30 days).",
                color=discord.Color.gold(),
            )
            embed.add_field(name="Last 30 Days", value=f"${total_cost:.2f}", inline=False)
            embed.add_field(name="Projected 50 Years", value=f"${projected_50y:,.2f}", inline=False)
            embed.set_footer(text="Costs derived from metrics metadata (cost_usd).")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            if logger:
                logger.error(f"[🔧] Cost analysis failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Cost analysis failed: {e}", ephemeral=True)
    
    async def build_diagnostics_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Diagnostics and recovery lane (read-first, execute cautiously)."""
        embed = discord.Embed(
            title="🛠 Diagnostics & Recovery",
            description="Inspect system state and reserve space for future repair tooling.",
            color=discord.Color.dark_teal()
        )

        total_sessions = 0
        total_messages = 0

        try:
            from abby_core.database.collections.chat_sessions import get_guild_session_stats
            guild_id = str(interaction.guild.id) if interaction.guild else None

            if guild_id:
                stats = get_guild_session_stats(guild_id)
                total_sessions = stats.get("total_sessions", 0)
                total_messages = stats.get("total_messages", 0)
        except Exception as e:
            if logger:
                logger.warning(f"[🔧] Failed to get conversation stats: {e}")

        embed.add_field(
            name="📊 Current Signals",
            value=f"💬 Stored Sessions: {total_sessions:,}\n📝 Session Records: {total_messages:,}",
            inline=False
        )

        embed.add_field(
            name="Guardrails",
            value=(
                "Read-only by default; destructive tools require explicit IDs and confirmation.\n"
                "This lane is reserved for job reconciliation, repairs, and dry-run migrations."
            ),
            inline=False
        )

        embed.set_footer(text="Diagnostics is imperative-only • No policy or scheduling edits here")
        return embed
    
    async def run_memory_maintenance(self, interaction: discord.Interaction):
        """Run memory system maintenance."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if logger:
                logger.info(f"[🔧] Operator {interaction.user.id} initiated memory maintenance")
            
            # Run maintenance
            if not run_maintenance:
                await interaction.followup.send("❌ Memory maintenance unavailable.", ephemeral=True)
                return

            result = run_maintenance()
            
            embed = discord.Embed(
                title="🔧 Memory Maintenance Complete",
                description="Memory system maintenance has been executed",
                color=discord.Color.green()
            )
            
            if isinstance(result, dict):
                for key, value in result.items():
                    embed.add_field(name=key.replace("_", " ").title(), value=str(value), inline=True)
            else:
                embed.add_field(name="Result", value=str(result), inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            if logger:
                logger.error(f"[🔧] Maintenance failed: {e}")
            await interaction.followup.send(
                f"❌ Maintenance failed: {str(e)}",
                ephemeral=True
            )

    # ==================== SYSTEM STATE MANAGEMENT ====================

    def build_event_template_embed(
        self,
        event_key: str,
        template: Dict[str, Any],
        year: int,
        start_override: Optional[Any] = None,
        end_override: Optional[Any] = None,
        date_override_reason: Optional[str] = None,
    ) -> discord.Embed:
        title = template.get("label_template", event_key).format(year=year)
        priority = template.get("priority", 0)
        allowed_overrides = template.get("allowed_overrides", [])

        schedule_lines: List[str] = []
        try:
            from abby_core.system.state_registry import get_event_schedule

            ok, err, schedule = get_event_schedule(
                event_key,
                year,
                start_at_override=start_override,
                end_at_override=end_override,
            )

            if ok and schedule:
                def _fmt(dt_val: Any) -> str:
                    if not dt_val:
                        return "N/A"
                    return dt_val.strftime("%Y-%m-%d") if hasattr(dt_val, "strftime") else str(dt_val)

                default_start_str = _fmt(schedule.get("default_start_at"))
                default_end_str = _fmt(schedule.get("default_end_at"))
                actual_start_str = _fmt(schedule.get("start_at"))
                actual_end_str = _fmt(schedule.get("end_at"))

                schedule_lines.append(f"Default: {default_start_str} → {default_end_str}")
                schedule_lines.append(f"Scheduled: {actual_start_str} → {actual_end_str}")

                if start_override or end_override:
                    schedule_lines.append("Overrides: provided by operator")
                    if date_override_reason:
                        schedule_lines.append(f"Reason: {date_override_reason}")
            else:
                schedule_lines.append(f"Schedule error: {err}")
        except Exception as exc:
            if logger:
                logger.error(f"[🔧] Failed to compute schedule for {event_key}-{year}: {exc}")
            schedule_lines.append("Schedule unavailable")

        embed = discord.Embed(
            title=f"Configure: {title}",
            description=template.get("description", ""),
            color=discord.Color.teal(),
        )

        embed.add_field(
            name="Dates",
            value="\n".join(schedule_lines) or "N/A",
            inline=True,
        )
        embed.add_field(name="Priority", value=str(priority), inline=True)

        effects = template.get("effects", {})
        if effects:
            effect_lines = [f"• {k}: {v}" for k, v in effects.items()]
            embed.add_field(name="Default Effects", value="\n".join(effect_lines), inline=False)

        if allowed_overrides:
            embed.add_field(
                name="Allowed Overrides",
                value="\n".join([f"• {k}" for k in allowed_overrides]),
                inline=False,
            )

        embed.set_footer(text="Select year and optional overrides, then Create Event")
        return embed

    async def show_upcoming_events(self, interaction: discord.Interaction) -> None:
        """Show list of upcoming events."""
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.system.state_registry import list_upcoming_events

            events = list_upcoming_events(days_ahead=90)

            if not events:
                await interaction.followup.send("📅 No upcoming events scheduled.", ephemeral=True)
                return

            embed = discord.Embed(
                title="📅 Upcoming Events (Next 90 Days)",
                description=f"{len(events)} event(s) scheduled",
                color=discord.Color.blue()
            )

            for event in events:
                state_id = event.get("state_id", "Unknown")
                label = event.get("label", state_id)
                start = event.get("start_at")
                end = event.get("end_at")
                status = "🟢 Active" if event.get("active") else "⏰ Scheduled"

                date_str = ""
                if isinstance(start, str):
                    date_str = start[:10]
                elif start and hasattr(start, "date"):
                    date_str = str(start.date())

                embed.add_field(
                    name=f"{label} ({status})",
                    value=f"Starts: {date_str}\nID: `{state_id}`",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to list events: {e}")
            await interaction.followup.send(f"❌ Error listing events: {e}", ephemeral=True)

    # ==================== SYSTEM STATUS COMMANDS ====================

    async def show_system_status_all(self, interaction: discord.Interaction) -> None:
        """Show complete platform state - equivalent to /operator system status (all)."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from abby_core.database.mongodb import get_database
            from datetime import datetime, timezone
            
            db = get_database()
            
            embed = discord.Embed(
                title="📋 PLATFORM STATE SUMMARY",
                description=f"Status as of {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                color=discord.Color.blue()
            )
            
            # Active Season
            season = db.system_state.find_one({"state_type": "season", "active": True})
            if season:
                label = season.get("label", "Unknown")
                start = season.get("start_at")
                end = season.get("end_at")
                start_str = start.strftime("%b %d") if hasattr(start, "strftime") else str(start)[:10]
                end_str = end.strftime("%b %d") if hasattr(end, "strftime") else str(end)[:10]
                embed.add_field(
                    name="🌍 ACTIVE SEASON",
                    value=f"**{label}** ({start_str} - {end_str})\nStatus: ✅ ACTIVE",
                    inline=False
                )
            
            # Active Events
            active_events = list(db.system_state.find({"state_type": "event", "active": True}))
            if active_events:
                events_text = "\n".join([
                    f"  ✅ {e.get('label', 'Unknown')}"
                    for e in active_events
                ])
                embed.add_field(name="💕 ACTIVE EVENTS", value=events_text, inline=False)
            
            # Upcoming Events
            upcoming_events = list(db.system_state.find({"state_type": "event", "active": False}))
            if upcoming_events:
                events_text = "\n".join([
                    f"  ⏸️ {e.get('label', 'Unknown')}"
                    for e in upcoming_events[:3]
                ])
                if len(upcoming_events) > 3:
                    events_text += f"\n  ... and {len(upcoming_events) - 3} more"
                embed.add_field(name="🥚 UPCOMING EVENTS", value=events_text, inline=False)
            
            # Background Jobs
            jobs = list(db.scheduler_jobs.find({"enabled": True}).limit(3))
            if jobs:
                jobs_text = "\n".join([
                    f"  ✅ {j.get('job_type', 'Unknown').split('.')[-1]}: {'Daily' if 'daily' in str(j.get('schedule', '')) else 'Periodic'}"
                    for j in jobs
                ])
                embed.add_field(name="📅 SYSTEM JOBS", value=jobs_text, inline=False)
            
            embed.set_footer(text="Click other buttons for detailed sections • All sections from SYSTEM_STATUS_COMMANDS.md")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to show system status all: {e}")
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    async def show_system_status_seasons(self, interaction: discord.Interaction) -> None:
        """Show seasonal cycle information."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from abby_core.database.mongodb import get_database
            
            db = get_database()
            seasons = list(db.system_state.find({"state_type": "season"}))
            
            embed = discord.Embed(
                title="🌍 SEASONAL CYCLE (2026)",
                color=discord.Color.blue()
            )
            
            for season in seasons:
                label = season.get("label", "Unknown")
                active = season.get("active", False)
                start = season.get("start_at")
                end = season.get("end_at")
                
                start_str = start.strftime("%b %d") if hasattr(start, "strftime") else str(start)[:10]
                end_str = end.strftime("%b %d") if hasattr(end, "strftime") else str(end)[:10]
                status = "✅ ACTIVE" if active else "⏸️ UPCOMING"
                
                effects = season.get("effects", {})
                effects_str = ", ".join(effects.keys()) if effects else "None"
                
                embed.add_field(
                    name=f"{label} ({status})",
                    value=f"**Dates:** {start_str} - {end_str}\n**Effects:** {effects_str}",
                    inline=False
                )
            
            embed.set_footer(text="Seasons auto-transition at UTC midnight • XP resets at transition")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to show seasons: {e}")
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    async def show_system_status_events(self, interaction: discord.Interaction) -> None:
        """Show event schedule information."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from abby_core.database.mongodb import get_database
            
            db = get_database()
            events = list(db.system_state.find({"state_type": "event"}))
            
            embed = discord.Embed(
                title="📅 EVENT SCHEDULE (2026)",
                color=discord.Color.blue()
            )
            
            for event in events:
                label = event.get("label", "Unknown")
                active = event.get("active", False)
                start = event.get("start_at")
                end = event.get("end_at")
                
                start_str = start.strftime("%b %d") if hasattr(start, "strftime") else str(start)[:10]
                end_str = end.strftime("%b %d") if hasattr(end, "strftime") else str(end)[:10]
                status = "✅ ACTIVE" if active else "⏸️ UPCOMING"
                
                effects = event.get("effects", {})
                effects_str = ", ".join(effects.keys()) if effects else "None"
                
                embed.add_field(
                    name=f"{label} ({status})",
                    value=f"**Dates:** {start_str} - {end_str}\n**Effect:** {effects_str}\n**Auto-Manage:** YES",
                    inline=False
                )
            
            embed.set_footer(text="All events auto-manage • Announcements scheduled for 09:00 UTC")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to show events: {e}")
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    async def show_system_status_effects(self, interaction: discord.Interaction) -> None:
        """Show currently active effects."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from abby_core.database.mongodb import get_database
            
            db = get_database()
            
            embed = discord.Embed(
                title="⚙️ ACTIVE EFFECTS",
                color=discord.Color.blue()
            )
            
            # Season Effects
            season = db.system_state.find_one({"state_type": "season", "active": True})
            if season:
                effects = season.get("effects", {})
                season_label = season.get("label", "Unknown")
                if effects:
                    effects_str = "\n".join([f"  ✅ {k}: Enabled" for k in effects.keys()])
                    embed.add_field(
                        name=f"SEASON EFFECTS ({season_label})",
                        value=effects_str,
                        inline=False
                    )
            
            # Event Effects
            active_events = list(db.system_state.find({"state_type": "event", "active": True}))
            for event in active_events:
                effects = event.get("effects", {})
                event_label = event.get("label", "Unknown")
                if effects:
                    effects_str = "\n".join([f"  ✅ {k}: Enabled" for k in effects.keys()])
                    embed.add_field(
                        name=f"EVENT EFFECTS ({event_label})",
                        value=effects_str,
                        inline=False
                    )
            
            # Jobs
            jobs = list(db.scheduler_jobs.find({"enabled": True}))
            if jobs:
                jobs_str = "\n".join([
                    f"  ✅ {j.get('job_type', 'Unknown')}: Enabled"
                    for j in jobs
                ])
                embed.add_field(name="BACKGROUND JOBS", value=jobs_str, inline=False)
            
            embed.set_footer(text="Effects applied automatically based on active states")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to show effects: {e}")
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    async def show_system_status_jobs(self, interaction: discord.Interaction) -> None:
        """Show background job status and execution information."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from abby_core.database.mongodb import get_database
            
            db = get_database()
            jobs = list(db.scheduler_jobs.find())
            
            embed = discord.Embed(
                title="📅 BACKGROUND JOB STATUS",
                color=discord.Color.blue()
            )
            
            for job in jobs:
                job_type = job.get("job_type", "Unknown")
                enabled = job.get("enabled", False)
                schedule = job.get("schedule", {})
                last_run = job.get("last_run_at")
                next_run = job.get("next_run_at")
                
                status_emoji = "✅" if enabled else "❌"
                schedule_str = "Daily 00:00 UTC" if schedule.get("type") == "daily" else "Every 60s"
                
                last_run_str = last_run.strftime("%H:%M UTC") if hasattr(last_run, "strftime") else "Never"
                next_run_str = next_run.strftime("%b %d, %H:%M UTC") if hasattr(next_run, "strftime") else "N/A"
                
                embed.add_field(
                    name=f"{job_type}",
                    value=f"**Status:** {status_emoji} {'ENABLED' if enabled else 'DISABLED'}\n**Schedule:** {schedule_str}\n**Last:** {last_run_str}\n**Next:** {next_run_str}",
                    inline=False
                )
            
            embed.set_footer(text="Jobs manage platform lifecycle automatically")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to show jobs: {e}")
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    async def show_create_event_menu(self, interaction: discord.Interaction) -> None:
        """Show event template selection menu."""
        await interaction.response.defer(ephemeral=True)

        try:
            view = CreateEventSelectView(self, interaction.user.id)
            await interaction.followup.send(
                "✨ Select an event template to create:",
                view=view,
                ephemeral=True
            )
        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to show event menu: {e}")
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    async def create_event_from_template(
        self,
        interaction: discord.Interaction,
        event_key: str,
        year: int,
        overrides: Optional[Dict[str, Any]] = None,
        start_at_override: Optional[Any] = None,
        end_at_override: Optional[Any] = None,
        date_override_reason: Optional[str] = None,
    ) -> None:
        """Create event instance from template."""
        try:
            from abby_core.system.state_registry import create_event_from_template

            success, message, state_id = create_event_from_template(
                event_key=event_key,
                year=year,
                operator_id=interaction.user.id,
                override_effects=overrides,
                start_at_override=start_at_override,
                end_at_override=end_at_override,
                date_override_reason=date_override_reason,
            )

            if success:
                embed = discord.Embed(
                    title="✨ Event Created Successfully",
                    description=message,
                    color=discord.Color.green()
                )
                embed.add_field(name="State ID", value=f"`{state_id}`", inline=False)
                embed.add_field(
                    name="Next Steps",
                    value="✅ Instance created and scheduled for auto-activation\n"
                    "ℹ️ Use Preview States to see when it will be active",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

                if logger:
                    logger.info(f"[🔧] Operator {interaction.user.id} created event {state_id}")
            else:
                embed = discord.Embed(
                    title="❌ Event Creation Failed",
                    description=message,
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to create event: {e}")
            await interaction.followup.send(f"❌ Error creating event: {e}", ephemeral=True)

    async def show_preview_states_menu(self, interaction: discord.Interaction) -> None:
        """Show date selection for state preview."""
        try:
            modal = PreviewStatesDateModal(self)
            await interaction.response.send_modal(modal)
        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to show preview menu: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    async def preview_states_at_date(
        self,
        interaction: discord.Interaction,
        target_date: "datetime"
    ) -> None:
        """Preview active states at a specific date."""
        try:
            from abby_core.system.state_registry import preview_active_states_at_date

            preview = preview_active_states_at_date(target_date)

            embed = discord.Embed(
                title=f"🔮 State Preview: {preview['target_date'][:10]}",
                color=discord.Color.purple()
            )

            states = preview.get("active_states", [])
            if states:
                state_list = "\n".join(
                    f"• **{s['label']}** (Priority: {s['priority']})"
                    for s in states
                )
                embed.add_field(name="Active States", value=state_list, inline=False)
            else:
                embed.add_field(name="Active States", value="None", inline=False)

            effects = preview.get("merged_effects", {})
            if effects:
                effects_list = "\n".join(
                    f"• `{k}`: {v}"
                    for k, v in effects.items()
                )
                embed.add_field(name="Merged Effects", value=effects_list, inline=False)
            else:
                embed.add_field(name="Merged Effects", value="None", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            if logger:
                logger.error(f"[🔧] Failed to preview states: {e}")
            await interaction.followup.send(f"❌ Error previewing states: {e}", ephemeral=True)

    async def show_schedule_configuration(self, interaction: discord.Interaction) -> None:
        """Show current job schedule configuration and allow edits."""
        await interaction.response.defer(ephemeral=True)

        try:
            from abby_core.database.collections.guild_configuration import get_guild_config, set_guild_setting
            from abby_core.database.collections.system_configuration import get_system_config
            
            if not interaction.guild:
                await interaction.followup.send("❌ This requires a guild context.", ephemeral=True)
                return
            
            guild_id = interaction.guild.id
            guild_config = get_guild_config(guild_id)
            system_config = get_system_config()
            
            # Get current schedules from system config (announcements are system-wide)
            system_jobs = system_config.get("system_jobs", {})
            announcements = system_jobs.get("announcements", {})
            daily_announcements_job = announcements.get("daily_world_announcements", {})
            schedule = daily_announcements_job.get("schedule", {})
            daily_announcements_time = schedule.get("time", "09:00")
            is_enabled = daily_announcements_job.get("enabled", False)
            system_timezone = system_config.get("timezone", "UTC")
            
            embed = discord.Embed(
                title="⏰ System Job Schedule Configuration",
                description="Announcements are sent to all guilds using the system timezone",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="🌍 System Timezone",
                value=f"**{system_timezone}**\n\n(Determines when daily jobs execute)",
                inline=False
            )
            
            embed.add_field(
                name="📢 Daily World Announcements",
                value=f"Status: {'✅ Enabled' if is_enabled else '❌ Disabled'}\nCurrent time: **{daily_announcements_time}** ({system_timezone})",
                inline=False
            )
            
            embed.add_field(
                name="Format",
                value="Time: 24-hour format `HH:MM` (e.g., `08:00`, `09:00`, `20:00`)",
                inline=False
            )
            
            view = ScheduleConfigView(self, interaction.user.id, guild_id, daily_announcements_time, is_enabled, system_timezone)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        except Exception as e:
            if logger:
                logger.error(f"[🔧] Schedule config failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Schedule config failed: {e}", ephemeral=True)


class ScheduleConfigView(discord.ui.View):
    """UI for configuring daily job schedules."""
    
    def __init__(self, cog: "OperatorPanel", user_id: int, guild_id: int, current_time: str, is_enabled: bool = False, timezone: str = "UTC"):
        super().__init__(timeout=300.0)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.current_time = current_time
        self.is_enabled = is_enabled
        self.timezone = timezone
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the operator who opened this to interact."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Only the operator who opened this can modify settings.",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="✏️ Change Time", style=discord.ButtonStyle.primary)
    async def change_time_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to change daily announcement time."""
        modal = ScheduleTimeModal(self.cog, self.guild_id, self.current_time)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🌍 Change Timezone", style=discord.ButtonStyle.primary)
    async def change_timezone_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show timezone selection view."""
        view = TimezoneSelectView(self.cog, interaction.user.id, self.timezone)
        embed = discord.Embed(
            title="🌍 Select System Timezone",
            description="Choose a timezone for system-wide scheduled jobs",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="⏱️ Toggle Status", style=discord.ButtonStyle.secondary)
    async def toggle_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle the daily announcements job on/off."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from abby_core.database.collections.system_configuration import get_system_config, set_system_config
            
            new_enabled = not self.is_enabled
            
            updates = {
                "system_jobs": {
                    "announcements": {
                        "daily_world_announcements": {
                            "enabled": new_enabled
                        }
                    }
                }
            }
            
            set_system_config(updates)
            self.is_enabled = new_enabled
            
            if logger:
                status = "enabled" if new_enabled else "disabled"
                logger.info(f"[📢] Operator {interaction.user.id} {status} daily announcements")
            
            status_text = "✅ Enabled" if new_enabled else "❌ Disabled"
            embed = discord.Embed(
                title="Status Updated",
                description=f"Daily announcements are now {status_text}",
                color=discord.Color.green() if new_enabled else discord.Color.orange()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            if logger:
                logger.error(f"[📢] Failed to toggle status: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Failed: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🔄 Reload", style=discord.ButtonStyle.secondary)
    async def reload_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reload the schedule configuration."""
        await self.cog.show_schedule_configuration(interaction)
    
    @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close this panel."""
        await interaction.response.defer()
        self.stop()


class TimezoneSelectView(discord.ui.View):
    """UI for selecting system timezone."""
    
    # Common timezones
    TIMEZONES = [
        ("UTC", "UTC"),
        ("🇺🇸 US/Eastern", "US/Eastern"),
        ("🇺🇸 US/Central", "US/Central"),
        ("🇺🇸 US/Mountain", "US/Mountain"),
        ("🇺🇸 US/Pacific", "US/Pacific"),
        ("🇬🇧 Europe/London", "Europe/London"),
        ("🇫🇷 Europe/Paris", "Europe/Paris"),
        ("🇩🇪 Europe/Berlin", "Europe/Berlin"),
        ("🇯🇵 Asia/Tokyo", "Asia/Tokyo"),
        ("🇨🇳 Asia/Shanghai", "Asia/Shanghai"),
        ("🇦🇺 Australia/Sydney", "Australia/Sydney"),
    ]
    
    def __init__(self, cog: "OperatorPanel", user_id: int, current_timezone: str):
        super().__init__(timeout=300.0)
        self.cog = cog
        self.user_id = user_id
        self.current_timezone = current_timezone
        
        # Add timezone select
        self.tz_select = discord.ui.Select(
            placeholder="Choose a timezone",
            options=[
                discord.SelectOption(
                    label=label,
                    value=tz_value,
                    default=(tz_value == current_timezone)
                )
                for label, tz_value in self.TIMEZONES
            ]
        )
        self.tz_select.callback = self.on_timezone_select
        self.add_item(self.tz_select)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the operator who opened this to interact."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Only the operator who opened this can modify settings.",
                ephemeral=True
            )
            return False
        return True
    
    async def on_timezone_select(self, interaction: discord.Interaction):
        """Handle timezone selection."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from abby_core.database.collections.system_configuration import get_system_config, set_system_config
            
            selected_tz = self.tz_select.values[0]
            
            # Update system config
            updates = {
                "timezone": selected_tz
            }
            
            set_system_config(updates)
            self.current_timezone = selected_tz
            
            if logger:
                logger.info(f"[🌍] Operator {interaction.user.id} set system timezone to {selected_tz}")
            
            embed = discord.Embed(
                title="✅ Timezone Updated",
                description=f"System timezone is now **{selected_tz}**\n\nDaily announcements will execute at the scheduled time in this timezone.",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            if logger:
                logger.error(f"[🌍] Failed to update timezone: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Failed: {str(e)}", ephemeral=True)


class ScheduleTimeModal(discord.ui.Modal, title="Daily Announcement Time"):
    """Modal to set daily world announcement time."""
    
    def __init__(self, cog: "OperatorPanel", guild_id: int, current_time: str):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        
        # Add input field with current value
        self.time_input = discord.ui.TextInput(
            label="Announcement Time",
            placeholder="HH:MM (e.g., 08:00, 09:00, 20:00)",
            default=current_time,
            min_length=5,
            max_length=5,
            required=True
        )
        self.add_item(self.time_input)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle time submission."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from abby_core.database.collections.system_configuration import get_system_config, set_system_config
            import re
            
            new_time = self.time_input.value.strip()
            
            # Validate format HH:MM
            if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', new_time):
                await interaction.followup.send(
                    "❌ Invalid format. Use 24-hour format: `HH:MM` (e.g., `08:00`, `09:00`)",
                    ephemeral=True
                )
                return
            
            # Update system config with proper nested structure
            updates = {
                "system_jobs": {
                    "announcements": {
                        "daily_world_announcements": {
                            "schedule": {
                                "type": "daily",
                                "time": new_time
                            }
                        }
                    }
                }
            }
            
            set_system_config(updates)
            
            if logger:
                logger.info(f"[📢] Operator {interaction.user.id} set daily announcements to {new_time}")
            
            embed = discord.Embed(
                title="✅ Schedule Updated",
                description=f"Daily world announcements will now fire at **{new_time}** (UTC)\n\nThe scheduler will pick this up within the next minute.",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            if logger:
                logger.error(f"[📢] Failed to update schedule: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to update: {str(e)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Load the operator panel cog."""
    await bot.add_cog(OperatorPanel(bot))

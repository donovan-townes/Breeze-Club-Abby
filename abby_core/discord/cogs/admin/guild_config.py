"""
Guild Configuration System v2.0 - Production-Grade Control Plane

ARCHITECTURE PRINCIPLES:
=======================
1. Config Ownership: Each panel section owns its state and validation independently.
   This enables future modularization (lift panels to separate files without refactoring).

2. Disabled-But-Configured: Preserve settings when features are disabled.
   Allows pre-configuration and prevents re-entry of data on re-enable.

3. Consistent Naming: 
   - Panels: GuildConfig*Panel (CoreBehaviorPanel, ChannelsPanel, etc.)
   - Actions: Verbs only (Set, Enable, Disable, Save)
   - States: Nouns (Status, Channel, Timezone)

4. Progressive Disclosure: Show only required fields by default, hide complexity.

5. Mandatory Channel Selection: Any feature that posts messages MUST explicitly
   select a channel (prevents ghost behavior and scaling pain).

ROLE-BASED ACCESS:
==================
- Owner/Operator: System, Automations, Limits (platform-wide controls)
- Guild Admin: All panels (day-to-day configuration)
- Moderator: Overview only (read-only monitoring)

CONTROL PLANE STRUCTURE:
========================
/config → Overview (status dashboard)
    ├─ Channels (where messages go)
    ├─ Automations (when things run: times, intervals, enable/disable)
    ├─ Features (feature toggles: cores, games, personas, integrations)
    ├─ Community (community engagement jobs)
    ├─ System (platform automation: MOTD, giveaways, maintenance)
    └─ Limits (usage gates & anti-abuse)

CRITICAL RULES:
===============
1. Channels define WHERE (not WHEN or WHAT)
2. Automations define WHEN (not WHERE or WHAT FEATURE)
3. Features toggle on/off and set channels (not times)
4. Feature panels show schedules READ-ONLY with link to Automations
5. Only one source of truth for each configuration value
"""


import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import os

from abby_core.database.collections.guild_configuration import (
    get_guild_config,
    set_guild_config,
    validate_config,
    CONFIG_SCHEMA,
)
from abby_core.database.mongodb import get_database
from abby_core.discord.cogs.system.schedule_utils import (
    normalize_schedule_read,
    normalize_schedule_write,
    get_schedule_display
)
from abby_core.discord.cogs.system.registry import JOB_METADATA
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
# CAPABILITY & PERMISSION HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def _load_operator_ids() -> List[int]:
    """Load operator IDs from environment variable."""
    operator_ids_str = os.getenv("OPERATOR_IDS", "")
    if not operator_ids_str:
        return []
    try:
        return [int(id.strip()) for id in operator_ids_str.split(",") if id.strip()]
    except ValueError:
        logger.warning("Invalid OPERATOR_IDS format in .env. Expected comma-separated integers.")
        return []


OPERATOR_IDS = _load_operator_ids()


def is_operator(user_id: int) -> bool:
    """Check if user is a bot operator."""
    return user_id in OPERATOR_IDS


def is_guild_admin(interaction: discord.Interaction) -> bool:
    """Check if user is guild admin (owner or administrator)."""
    if not interaction.guild:
        return False
    user = interaction.user
    guild = interaction.guild
    member = guild.get_member(user.id)
    if not member:
        return False
    return guild.owner_id == user.id or member.guild_permissions.administrator


# ════════════════════════════════════════════════════════════════════════════════
# CONFIG HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def format_channel(channel_id: Optional[int]) -> str:
    """Format channel ID for display."""
    return f"<#{channel_id}>" if channel_id else "Not set"


def format_role(role_id: Optional[int]) -> str:
    """Format role ID for display."""
    return f"<@&{role_id}>" if role_id else "Not set"


def format_boolean(value: bool) -> str:
    """Format boolean as emoji."""
    return "✅" if value else "❌"


def get_feature_status(config: Dict[str, Any], feature: str) -> bool:
    """
    Get feature enabled status.
    
    Supports nested features like features.memory.enabled
    """
    parts = feature.split(".")
    current = config
    
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, None)
        else:
            return False
    
    return bool(current)


# ════════════════════════════════════════════════════════════════════════════════
# MAIN GUILD CONFIG COG
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfig(commands.Cog):
    """Manage server configuration for Abby with production-grade UI."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.debug("[⚙️] Guild Config System v2.0 loaded")
        if OPERATOR_IDS:
            operator_word = "operator" if len(OPERATOR_IDS) == 1 else "operators"
            logger.debug(f"[⚙️] Operator IDs configured: {len(OPERATOR_IDS)} {operator_word}")

    @app_commands.command(name="config", description="Configure Abby settings for this server")
    @app_commands.default_permissions(administrator=True)
    async def config_guild(self, interaction: discord.Interaction):
        """Guild configuration hub - show overview and navigation."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        # Get current settings
        if interaction.guild_id is None:
            await interaction.response.send_message("❌ Cannot use this command in DMs.", ephemeral=True)
            return
        
        config = get_guild_config(interaction.guild_id)
        
        # Show overview panel
        view = GuildConfigOverviewPanel(interaction.guild_id, config)
        embed = view.build_overview_embed()
        
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=False
        )

    # Note: /privacy and /operator are now implemented in separate cog files:
    # - /privacy → abby_core/discord/cogs/utility/privacy_panel.py
    # - /operator → abby_core/discord/cogs/admin/operator_panel.py
    # 
    # These commands have been moved out of guild_config to keep the codebase
    # modular and follow the single-responsibility principle.


# ════════════════════════════════════════════════════════════════════════════════
# OVERVIEW PANEL - Read-Only Landing Screen
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigOverviewPanel(discord.ui.View):
    """
    Read-only overview panel showing current state.
    
    This is the landing screen - answers "What is enabled right now?"
    with clear, scannable information and section-specific Edit buttons.
    """
    
    def __init__(self, guild_id: Optional[int], config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id or 0
        self.config = config

    def build_overview_embed(self) -> discord.Embed:
        """Build the read-only overview embed."""
        from datetime import timezone as tz
        embed = discord.Embed(
            title="⚙️ Server Configuration - Overview",
            description="Current state of all settings. Click **Edit** on any section to modify.",
            color=discord.Color.blue(),
            timestamp=datetime.now(tz.utc)
        )

        # ─────────────────────────────────────────────────────────────
        # Memory System
        # ─────────────────────────────────────────────────────────────
        memory_enabled = get_feature_status(self.config, "features.memory.enabled")
        embed.add_field(
            name="🧠 Memory System",
            value=(
                f"Status: {format_boolean(memory_enabled)}\n"
                f"Decay: {format_boolean(get_feature_status(self.config, 'features.memory.decay'))}\n"
                f"Extraction: {format_boolean(get_feature_status(self.config, 'features.memory.extraction'))}\n"
                f"Retention: {self.config.get('memory', {}).get('decay', {}).get('retention_days', 90)}d"
            ),
            inline=True
        )

        # ─────────────────────────────────────────────────────────────
        # Chat Behavior
        # ─────────────────────────────────────────────────────────────
        chat_mode = self.config.get("conversation", {}).get("default_chat_mode", "multi_turn")
        summon_mode = self.config.get("conversation", {}).get("summon_mode", "both")
        
        embed.add_field(
            name="💬 Chat Mode",
            value=(
                f"Mode: {chat_mode.replace('_', ' ').title()}\n"
                f"Summon: {summon_mode.replace('_', ' ').title()}"
            ),
            inline=True
        )

        # ─────────────────────────────────────────────────────────────
        # Channels (Infrastructure)
        # ─────────────────────────────────────────────────────────────
        channels = self.config.get("channels", {})
        mod_ch = channels.get("moderation", {}).get("id")
        announce_ch = channels.get("announcements", {}).get("id")
        welcome_ch = channels.get("welcome", {}).get("id")
        xp_ch = channels.get("xp", {}).get("id")
        
        embed.add_field(
            name="📡 Infrastructure Channels",
            value=(
                f"Mod: {format_channel(mod_ch)}\n"
                f"Announcements: {format_channel(announce_ch)}\n"
                f"Welcome: {format_channel(welcome_ch)}"
            ),
            inline=False
        )

        embed.add_field(
            name="💰 Economy Channels",
            value=(
                f"XP Gains: {format_channel(xp_ch)}"
            ),
            inline=False
        )

        # ─────────────────────────────────────────────────────────────
        # Scheduling (Temporal Context)
        # ─────────────────────────────────────────────────────────────
        scheduling = self.config.get("scheduling", {})
        timezone_str = scheduling.get("timezone", "UTC")
        jobs = scheduling.get("jobs", {})
        system_jobs = jobs.get("system", {})
        community_jobs = jobs.get("community", {})

        motd_job = system_jobs.get("motd", {})
        motd_enabled = motd_job.get("enabled", get_feature_status(self.config, "features.motd"))
        motd_schedule = normalize_schedule_read(motd_job)
        motd_display = get_schedule_display(motd_schedule)

        emoji_job = jobs.get("games", {}).get("emoji", {})
        auto_game_enabled = emoji_job.get("enabled", get_feature_status(self.config, "features.auto_game"))
        emoji_schedule = normalize_schedule_read(emoji_job)
        emoji_display = get_schedule_display(emoji_schedule)

        random_job = community_jobs.get("random_messages", {})
        random_enabled = random_job.get("enabled", False)
        random_schedule = normalize_schedule_read(random_job)
        random_display = get_schedule_display(random_schedule)
        random_jitter = random_job.get("jitter_minutes", 0)

        nudge_job = community_jobs.get("nudge", {})
        nudge_enabled = nudge_job.get("enabled", False)
        nudge_schedule = normalize_schedule_read(nudge_job)
        nudge_display = get_schedule_display(nudge_schedule)

        giveaways_job = system_jobs.get("giveaways", {})
        giveaway_enabled = giveaways_job.get("enabled", False)
        giveaway_schedule = normalize_schedule_read(giveaways_job)
        giveaway_display = get_schedule_display(giveaway_schedule)

        embed.add_field(
            name="🌍 Timezone",
            value=f"**{timezone_str}**",
            inline=True
        )

        embed.add_field(
            name="🕒 Active System Jobs",
            value=(
                f"MOTD: {format_boolean(motd_enabled)} {motd_display}\n"
                f"Auto Game: {format_boolean(auto_game_enabled)} {emoji_display}\n"
                f"Random Msgs: {format_boolean(random_enabled)} {random_display}"
                f"{' (±' + str(random_jitter) + 'm)' if random_jitter else ''}\n"
                f"Nudges: {format_boolean(nudge_enabled)} {nudge_display}\n"
                f"Giveaways: {format_boolean(giveaway_enabled)} {giveaway_display}"
            ),
            inline=True
        )

        # ─────────────────────────────────────────────────────────────
        # Bot Personality
        # ─────────────────────────────────────────────────────────────
        from abby_core.personality.manager import get_personality_manager
        try:
            manager = get_personality_manager()
            registry = manager.get_available_personas()
            personas = [name for name, info in registry.items() if info.get("enabled", True)]
            persona_display = ", ".join([p.capitalize() for p in sorted(personas)]) if personas else "None available"
        except:
            persona_display = "Unknown"
        
        embed.add_field(
            name="🎭 Personas",
            value=f"Available: {persona_display}",
            inline=True
        )

        # ─────────────────────────────────────────────────────────────
        # Integrations
        # ─────────────────────────────────────────────────────────────
        twitch_enabled = self.config.get("integrations", {}).get("twitch_enabled", False)
        twitch_channel = self.config.get("integrations", {}).get("twitch_channel_id")
        
        embed.add_field(
            name="🔗 Integrations",
            value=f"Twitch: {format_boolean(twitch_enabled)} {format_channel(twitch_channel) if twitch_enabled else ''}",
            inline=True
        )

        embed.set_footer(text="Click section buttons to edit | All times in guild timezone")
        return embed

    @discord.ui.button(label="Channels", style=discord.ButtonStyle.primary, emoji="📡", row=0)
    async def button_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Channels panel."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigChannelsPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Automations", style=discord.ButtonStyle.primary, emoji="⏰", row=0)
    async def button_automations(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Automations (Scheduler & Jobs) panel."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigAutomationsPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Features", style=discord.ButtonStyle.primary, emoji="✨", row=0)
    async def button_features(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Features router panel."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigFeaturesPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Community", style=discord.ButtonStyle.primary, emoji="👥", row=1)
    async def button_community(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Community Jobs panel."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigCommunityJobsPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="System", style=discord.ButtonStyle.primary, emoji="⚙️", row=1)
    async def button_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open System Jobs panel."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigSystemJobsPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Limits", style=discord.ButtonStyle.primary, emoji="⏱️", row=1)
    async def button_limits(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Limits panel."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigLimitsPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, emoji="❌", row=2)
    async def button_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the panel."""
        await interaction.response.defer()
        await interaction.delete_original_response()


# ════════════════════════════════════════════════════════════════════════════════
# CORE BEHAVIOR PANEL
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigCoreBehaviorPanel(discord.ui.View):
    """Chat Behavior Configuration - Core Conversation Feature.
    
    SCOPE: Chat modes, summon behavior, and conversation exchange limits.
    
    Part of Features panel. Does NOT handle scheduling.
    """
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config
        
        # Add inline selects
        self._add_chat_mode_select()
        self._add_summon_mode_select()
    
    def _add_chat_mode_select(self):
        """Add chat mode select dropdown."""
        conversation = self.config.get("conversation", {})
        current_mode = conversation.get("default_chat_mode", "multi_turn")
        
        select = discord.ui.Select(
            placeholder="Chat Mode",
            options=[
                discord.SelectOption(label="One Shot", value="one_shot", description="Single response per interaction", default=(current_mode=="one_shot")),
                discord.SelectOption(label="Multi Turn", value="multi_turn", description="Back-and-forth conversation", default=(current_mode=="multi_turn"))
            ],
            row=0
        )
        
        async def on_select(interaction: discord.Interaction):
            mode = select.values[0]
            success = set_guild_config(
                self.guild_id,
                {"conversation": {"default_chat_mode": mode}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigCoreBehaviorPanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save.", ephemeral=True)
        
        select.callback = on_select
        self.add_item(select)
    
    def _add_summon_mode_select(self):
        """Add summon mode select dropdown."""
        conversation = self.config.get("conversation", {})
        current_mode = conversation.get("summon_mode", "both")
        
        select = discord.ui.Select(
            placeholder="Summon Mode",
            options=[
                discord.SelectOption(label="Both", value="both", description="Mention or /chat command", default=(current_mode=="both")),
                discord.SelectOption(label="Mention Only", value="mention_only", description="Only @mentions trigger Abby", default=(current_mode=="mention_only")),
                discord.SelectOption(label="Slash Only", value="slash_only", description="Only /chat command", default=(current_mode=="slash_only"))
            ],
            row=1
        )
        
        async def on_select(interaction: discord.Interaction):
            mode = select.values[0]
            success = set_guild_config(
                self.guild_id,
                {"conversation": {"summon_mode": mode}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigCoreBehaviorPanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save.", ephemeral=True)
        
        select.callback = on_select
        self.add_item(select)

    def build_embed(self) -> discord.Embed:
        """Build section embed."""
        chat_mode = self.config.get("conversation", {}).get("default_chat_mode", "multi_turn")
        summon_mode = self.config.get("conversation", {}).get("summon_mode", "both")
        
        embed = discord.Embed(
            title="💬 Core Chat Behavior",
            description="How Abby responds and when she's summoned.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Chat Mode",
            value=f"**{chat_mode.replace('_', ' ').title()}**\nOne-shot: single response | Multi-turn: back-and-forth",
            inline=False
        )
        embed.add_field(
            name="Summon Mode",
            value=f"**{summon_mode.replace('_', ' ').title()}**\nHow to trigger Abby: mention, /chat, or both",
            inline=False
        )
        
        embed.set_footer(text="Use dropdowns above to change modes")
        return embed

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=3)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to Features panel."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigFeaturesPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# CHANNELS PANEL - Router
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigChannelsPanel(discord.ui.View):
    """Channel category router - choose a channel category to configure."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    def build_embed(self) -> discord.Embed:
        """Build channels router embed."""
        channels = self.config.get("channels", {})
        
        embed = discord.Embed(
            title="📡 Channel Configuration",
            description="Choose a channel category to configure:",
            color=discord.Color.blue()
        )
        
        # Infrastructure summary
        mod_ch = channels.get("moderation", {}).get("id")
        announce_ch = channels.get("announcements", {}).get("id")
        infra_status = "✅" if (mod_ch and announce_ch) else "⚠️"
        embed.add_field(
            name=f"{infra_status} Infrastructure",
            value="Core system channels\n(Mod, Announcements)",
            inline=True
        )
        
        # Messaging summary
        welcome_ch = channels.get("welcome", {}).get("id")
        random_ch = channels.get("random_messages", {}).get("id")
        motd_ch = channels.get("motd", {}).get("id")
        xp_ch = channels.get("xp", {}).get("id")
        msg_status = "✅" if (welcome_ch or random_ch or motd_ch or xp_ch) else "⚠️"
        embed.add_field(
            name=f"{msg_status} Messaging",
            value="User-facing content\n(Welcome, Random, MOTD, XP)",
            inline=True
        )
        
        embed.set_footer(text="Feature-owned channels (like Games) live in their feature panels")
        
        return embed

    @discord.ui.button(label="Infrastructure", style=discord.ButtonStyle.primary, emoji="🏗️", row=0)
    async def button_infrastructure(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure infrastructure channels."""
        view = GuildConfigInfrastructureChannelsPanel(self.guild_id, self.config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Messaging", style=discord.ButtonStyle.primary, emoji="💬", row=0)
    async def button_messaging(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure messaging channels."""
        view = GuildConfigMessagingChannelsPanel(self.guild_id, self.config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to overview."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigOverviewPanel(self.guild_id, config)
        embed = view.build_overview_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# INFRASTRUCTURE CHANNELS SUB-PANEL
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigInfrastructureChannelsPanel(discord.ui.View):
    """Configure core infrastructure channels (rarely change)."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config
        
        # Add channel selects
        self._add_mod_channel_select()
        self._add_announcements_channel_select()
    
    def _add_mod_channel_select(self):
        """Add mod channel select."""
        channels = self.config.get("channels", {})
        
        select = discord.ui.ChannelSelect(
            placeholder="Mod Channel",
            channel_types=[discord.ChannelType.text],
            min_values=0,
            max_values=1,
            row=0
        )
        
        async def on_select(interaction: discord.Interaction):
            channel_id = None
            if interaction.data and "values" in interaction.data and interaction.data["values"]:
                channel_id = int(interaction.data["values"][0])
            
            success = set_guild_config(
                self.guild_id,
                {"channels": {"moderation": {"id": channel_id, "description": "Mod Channel"}}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigInfrastructureChannelsPanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save.", ephemeral=True)
        
        select.callback = on_select
        self.add_item(select)
    
    def _add_announcements_channel_select(self):
        """Add announcements channel select."""
        channels = self.config.get("channels", {})
        
        select = discord.ui.ChannelSelect(
            placeholder="Announcements Channel",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=0,
            max_values=1,
            row=1
        )
        
        async def on_select(interaction: discord.Interaction):
            channel_id = None
            if interaction.data and "values" in interaction.data and interaction.data["values"]:
                channel_id = int(interaction.data["values"][0])
            
            success = set_guild_config(
                self.guild_id,
                {"channels": {"announcements": {"id": channel_id, "description": "Announcements Channel"}}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigInfrastructureChannelsPanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save.", ephemeral=True)
        
        select.callback = on_select
        self.add_item(select)

    def build_embed(self) -> discord.Embed:
        """Build infrastructure channels embed."""
        channels = self.config.get("channels", {})
        
        embed = discord.Embed(
            title="🏗️ Infrastructure Channels",
            description="Core system channels (rarely change).",
            color=discord.Color.blue()
        )
        
        mod_ch = channels.get("moderation", {}).get("id")
        embed.add_field(name="Mod Channel", value=format_channel(mod_ch), inline=True)
        
        announce_ch = channels.get("announcements", {}).get("id")
        embed.add_field(name="Announcements", value=format_channel(announce_ch), inline=True)
        
        embed.set_footer(text="Use dropdowns above to set channels")
        
        return embed

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to channels router."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigChannelsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# MESSAGING CHANNELS SUB-PANEL
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigMessagingChannelsPanel(discord.ui.View):
    """Configure user-facing messaging channels."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config
        
        # Add channel selects
        self._add_welcome_channel_select()
        self._add_random_channel_select()
        self._add_motd_channel_select()
        self._add_xp_channel_select()
    
    def _add_welcome_channel_select(self):
        """Add welcome channel select."""
        select = discord.ui.ChannelSelect(
            placeholder="Welcome Channel",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=0,
            max_values=1,
            row=0
        )
        
        async def on_select(interaction: discord.Interaction):
            channel_id = None
            if interaction.data and "values" in interaction.data and interaction.data["values"]:
                channel_id = int(interaction.data["values"][0])
            
            success = set_guild_config(
                self.guild_id,
                {"channels": {"welcome": {"id": channel_id, "description": "Welcome Channel"}}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigMessagingChannelsPanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save.", ephemeral=True)
        
        select.callback = on_select
        self.add_item(select)
    
    def _add_random_channel_select(self):
        """Add random messages channel select."""
        select = discord.ui.ChannelSelect(
            placeholder="Random Messages Channel",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=0,
            max_values=1,
            row=1
        )
        
        async def on_select(interaction: discord.Interaction):
            channel_id = None
            if interaction.data and "values" in interaction.data and interaction.data["values"]:
                channel_id = int(interaction.data["values"][0])
            
            success = set_guild_config(
                self.guild_id,
                {"channels": {"random_messages": {"id": channel_id, "description": "Random Messages Channel"}}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigMessagingChannelsPanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save.", ephemeral=True)
        
        select.callback = on_select
        self.add_item(select)
    
    def _add_motd_channel_select(self):
        """Add MOTD channel select."""
        select = discord.ui.ChannelSelect(
            placeholder="MOTD Channel",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=0,
            max_values=1,
            row=2
        )
        
        async def on_select(interaction: discord.Interaction):
            channel_id = None
            if interaction.data and "values" in interaction.data and interaction.data["values"]:
                channel_id = int(interaction.data["values"][0])
            
            success = set_guild_config(
                self.guild_id,
                {"channels": {"motd": {"id": channel_id, "description": "MOTD Channel"}}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigMessagingChannelsPanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save.", ephemeral=True)
        
        select.callback = on_select
        self.add_item(select)

    def _add_xp_channel_select(self):
        """Add XP gain channel select."""
        select = discord.ui.ChannelSelect(
            placeholder="XP Gain Channel",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=0,
            max_values=1,
            row=3
        )

        async def on_select(interaction: discord.Interaction):
            channel_id = None
            if interaction.data and "values" in interaction.data and interaction.data["values"]:
                channel_id = int(interaction.data["values"][0])

            success = set_guild_config(
                self.guild_id,
                {"channels": {"xp": {"id": channel_id, "description": "XP gain channel"}}},
                audit_user_id=str(interaction.user.id)
            )

            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigMessagingChannelsPanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save.", ephemeral=True)

        select.callback = on_select
        self.add_item(select)

    def build_embed(self) -> discord.Embed:
        """Build messaging channels embed."""
        channels = self.config.get("channels", {})
        
        embed = discord.Embed(
            title="💬 Messaging Channels",
            description="User-facing content channels.",
            color=discord.Color.blue()
        )
        
        welcome_ch = channels.get("welcome", {}).get("id")
        embed.add_field(name="Welcome Channel", value=format_channel(welcome_ch), inline=True)
        
        random_ch = channels.get("random_messages", {}).get("id")
        embed.add_field(name="Random Messages", value=format_channel(random_ch), inline=True)
        
        motd_ch = channels.get("motd", {}).get("id")
        embed.add_field(name="MOTD Channel", value=format_channel(motd_ch), inline=True)

        xp_ch = channels.get("xp", {}).get("id")
        embed.add_field(name="XP Gain Channel", value=format_channel(xp_ch), inline=True)
        
        embed.set_footer(text="Use dropdowns above to set channels")
        
        return embed

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=4)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to channels router."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigChannelsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# SCHEDULING PANEL
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigAutomationsPanel(discord.ui.View):
    """Automations Control Panel - Temporal Context & Job Scheduling.
    
    SCOPE: Where all WHEN decisions live (times, intervals, enable/disable execution).
    
    This panel is the single source of truth for:
    - Guild timezone
    - All job execution times
    - Job enable/disable state
    - Execution intervals
    
    Feature panels reference these times READ-ONLY with link back here.
    """
    
    # Common timezones for dropdown
    COMMON_TIMEZONES = [
        "UTC",
        "US/Eastern",
        "US/Central",
        "US/Mountain",
        "US/Pacific",
        "Europe/London",
        "Europe/Paris",
        "Europe/Berlin",
        "Asia/Tokyo",
        "Asia/Shanghai",
        "Asia/Kolkata",
        "Australia/Sydney",
        "America/Toronto",
        "America/Los_Angeles",
        "America/New_York",
        "America/Chicago"
    ]
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config
        
        # Add timezone dropdown
        self._add_timezone_select()
    
    def _add_timezone_select(self):
        """Add timezone select dropdown."""
        scheduling = self.config.get("scheduling", {})
        current_tz = scheduling.get("timezone", "UTC")
        
        # Build options with current timezone marked as default
        options = []
        for tz in self.COMMON_TIMEZONES:
            options.append(
                discord.SelectOption(
                    label=tz,
                    value=tz,
                    default=(tz == current_tz)
                )
            )
        
        select = discord.ui.Select(
            placeholder=f"Timezone: {current_tz}",
            options=options[:25],  # Discord limit of 25 options
            row=0
        )
        
        async def on_select(interaction: discord.Interaction):
            tz = select.values[0]
            
            # Validate timezone
            import pytz
            try:
                pytz.timezone(tz)
            except pytz.UnknownTimeZoneError:
                await interaction.response.send_message(f"❌ Invalid timezone: {tz}", ephemeral=True)
                return
            
            success = set_guild_config(
                self.guild_id,
                {"scheduling": {"timezone": tz}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigAutomationsPanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save timezone.", ephemeral=True)
        
        select.callback = on_select
        self.add_item(select)

    def build_embed(self) -> discord.Embed:
        """Build authoritative scheduling embed (dynamically from job registry)."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        timezone_str = scheduling.get("timezone", "UTC")

        def get_job_config(job_type: str) -> Dict[str, Any]:
            """Navigate to job config by dotted path (e.g., 'system.motd' or 'system.xp_rewards.daily_bonus')."""
            parts = job_type.split(".")
            current = jobs
            for part in parts:
                current = current.get(part, {})
            return current

        def job_line(job_type: str, metadata) -> str:
            """Build a single job status line from registry metadata."""
            job_config = get_job_config(job_type)
            schedule = normalize_schedule_read(job_config)
            enabled = job_config.get("enabled", False)
            last_exec = job_config.get("last_executed_at", "—")
            
            # Get schedule display
            schedule_display = get_schedule_display(schedule)
            
            # Special handling for specific jobs
            extra = ""
            if job_type == "games.emoji":
                duration = job_config.get("duration_minutes", 5)
                schedule_display = f"{schedule_display} ({duration}m)"
            elif job_type == "community.random_messages":
                jitter = job_config.get("jitter_minutes", 0)
                extra = f" | Jitter: ±{jitter}m"
            
            status = format_boolean(enabled)
            return f"{metadata['icon']} {metadata['label']}: {schedule_display} | {status} | Last run: {last_exec}{extra}"

        # Group jobs by category from registry
        categories: Dict[str, list] = {}
        for job_type, metadata in JOB_METADATA.items():
            category = metadata["category"]
            if category not in categories:
                categories[category] = []
            categories[category].append(job_line(job_type, metadata))

        embed = discord.Embed(
            title="⏰ Automations & Scheduling",
            description="Central control plane for execution times and job scheduling. All WHEN decisions live here.",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Guild Timezone",
            value=f"**{timezone_str}**\nAll jobs run in this timezone.",
            inline=False
        )

        # Add category fields dynamically
        category_icons = {
            "System Jobs": "🏛️",
            "Games Jobs": "🎮",
            "Community Jobs": "👥"
        }
        
        for category_name in ["System Jobs", "Games Jobs", "Community Jobs"]:
            if category_name in categories:
                icon = category_icons.get(category_name, "")
                embed.add_field(
                    name=f"{icon} {category_name}",
                    value="\n".join(categories[category_name]),
                    inline=False
                )

        embed.add_field(
            name="ℹ️ Editing",
            value="Times and intervals are only editable here. Feature panels show schedules read-only.",
            inline=False
        )

        embed.set_footer(text="✅ Central scheduling hub | All job times and enable/disable controlled here | Feature panels reference read-only")
        return embed

    @discord.ui.button(label="Edit Emoji Time", style=discord.ButtonStyle.primary, emoji="🎮", row=1)
    async def button_edit_emoji_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open emoji game time modal."""
        modal = AutoGameStartTimeModal(self.guild_id, self.config)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Random Messages", style=discord.ButtonStyle.primary, emoji="💬", row=1)
    async def button_random_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open consolidated random messages configuration modal (time + interval + jitter)."""
        modal = RandomMessagesConfigModal(self.guild_id, self.config)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="XP Bonus Time", style=discord.ButtonStyle.primary, emoji="💰", row=1)
    async def button_edit_xp_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open XP bonus time modal."""
        modal = SystemJobTimeModal(self.guild_id, self.config, "xp_daily_bonus", "XP Daily Bonus Time")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Maintenance Time", style=discord.ButtonStyle.primary, emoji="🤖", row=2)
    async def button_edit_maintenance_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open maintenance time modal."""
        modal = SystemJobTimeModal(self.guild_id, self.config, "maintenance", "Memory Maintenance Time")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit Giveaway Interval", style=discord.ButtonStyle.primary, emoji="🎁", row=2)
    async def button_edit_giveaways(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open giveaway interval modal."""
        modal = GiveawayIntervalModal(self.guild_id, self.config)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=3)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to overview."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigOverviewPanel(self.guild_id, config)
        embed = view.build_overview_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# FEATURES PANEL - Feature Router
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigFeaturesPanel(discord.ui.View):
    """Features Control Panel - Router for all feature configurations.
    
    SCOPE: Where feature toggles, channels, and configuration live.
    
    Responsibilities:
    - Enable/disable individual features
    - Assign channels per feature
    - Configure feature-specific behavior (duration, etc.)
    - Show schedules READ-ONLY with link to Automations
    
    This panel routes to:
    - Core Chat Behavior (chat modes, exchanges)
    - Games (emoji game)
    - Personas (bot personality)
    - Integrations (third-party services)
    """
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    def build_embed(self) -> discord.Embed:
        """Build features overview embed."""
        chat_mode = self.config.get("conversation", {}).get("default_chat_mode", "multi_turn")
        auto_game_enabled = get_feature_status(self.config, "features.auto_game")
        memory_enabled = get_feature_status(self.config, "features.memory.enabled")
        twitch_enabled = self.config.get("integrations", {}).get("twitch_enabled", False)
        
        embed = discord.Embed(
            title="✨ Features",
            description="Toggle features on/off and configure feature-specific settings.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💬 Chat Behavior",
            value=f"Mode: {chat_mode.replace('_', ' ').title()}\n🔧 Configure modes and exchanges",
            inline=False
        )
        
        embed.add_field(
            name="🎮 Games",
            value=f"Auto Game: {format_boolean(auto_game_enabled)}\n⏰ See Automations for schedule",
            inline=False
        )
        
        embed.add_field(
            name="🎲 Random Content",
            value="Custom messages, LLM prompts, promos\n🛠️ CRUD your content pools",
            inline=False
        )
        
        embed.add_field(
            name="🧠 Memory",
            value=f"Status: {format_boolean(memory_enabled)}\n💾 Core learning system",
            inline=False
        )
        
        embed.add_field(
            name="🎭 Personas",
            value="Bot personality profiles",
            inline=False
        )
        
        embed.add_field(
            name="🔗 Integrations",
            value=f"Twitch: {format_boolean(twitch_enabled)}\n🌐 Third-party services",
            inline=False
        )
        
        embed.set_footer(text="Feature schedules are in Automations (read-only)")
        return embed

    @discord.ui.button(label="Chat Behavior", style=discord.ButtonStyle.primary, emoji="💬", row=0)
    async def button_core_behavior(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Chat Behavior configuration."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigCoreBehaviorPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Random Content", style=discord.ButtonStyle.primary, emoji="🎲", row=0)
    async def button_random_content(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Random Content CRUD panel."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigRandomContentPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Games", style=discord.ButtonStyle.primary, emoji="🎮", row=0)
    async def button_games(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Games configuration."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigGamesPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Personas", style=discord.ButtonStyle.primary, emoji="🎭", row=0)
    async def button_persona(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Persona configuration."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigPersonaPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Integrations", style=discord.ButtonStyle.primary, emoji="🔗", row=1)
    async def button_integrations(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Integrations configuration."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigIntegrationsPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to Overview."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigOverviewPanel(self.guild_id, config)
        embed = view.build_overview_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# GAMES PANEL - Mandatory Channel Selection
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigGamesPanel(discord.ui.View):
    """Games overview/router panel - future-proof for multiple game types."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    def build_embed(self) -> discord.Embed:
        """Build games overview embed."""
        auto_game_enabled = get_feature_status(self.config, "features.auto_game")
        channels = self.config.get("channels", {})
        game_channel = channels.get("auto_game", {}).get("id")
        
        embed = discord.Embed(
            title="🎮 Games",
            description="Manage game features and settings. ⏰ Scheduling lives in System → Scheduling.",
            color=discord.Color.blue()
        )
        
        # Emoji Game summary
        emoji_game_status = "✅ Enabled" if auto_game_enabled else "❌ Disabled"
        emoji_game_channel = format_channel(game_channel) if game_channel else "Not set"
        
        embed.add_field(
            name="🎲 Emoji Game",
            value=f"{emoji_game_status}\nChannel: {emoji_game_channel}",
            inline=False
        )
        
        embed.set_footer(text="Select a game below to configure")
        
        return embed

    @discord.ui.button(label="Emoji Game", style=discord.ButtonStyle.primary, emoji="🎲", row=0)
    async def button_emoji_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Emoji Game configuration."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigEmojiGamePanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=1)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to Features."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigFeaturesPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# EMOJI GAME PANEL
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigEmojiGamePanel(discord.ui.View):
    """Emoji Game Configuration - Feature Panel.
    
    SCOPE: Channel assignment and game duration.
    
    Scheduling (start time) is READ-ONLY and managed in Automations panel.
    See note in embed footer linking to Automations.
    """
    
    # Duration presets for dropdown (in minutes)
    DURATION_PRESETS = [
        (1, "1 minute"),
        (3, "3 minutes"),
        (5, "5 minutes"),
        (15, "15 minutes"),
        (30, "30 minutes"),
        (60, "1 hour"),
    ]
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config
        
        # Add channel select and duration select
        self._add_channel_select()
        self._add_duration_select()
    
    def _add_channel_select(self):
        """Add the game channel select dropdown."""
        channels = self.config.get("channels", {})
        game_channel_id = channels.get("auto_game", {}).get("id")
        
        select = discord.ui.ChannelSelect(
            placeholder="Select Game Channel" if not game_channel_id else "Change Game Channel",
            channel_types=[discord.ChannelType.text],
            min_values=0,
            max_values=1,
            row=0
        )
        
        async def on_channel_select(interaction: discord.Interaction):
            channel_id = None
            if interaction.data and "values" in interaction.data and interaction.data["values"]:
                channel_id = int(interaction.data["values"][0])
            
            success = set_guild_config(
                self.guild_id,
                {"channels": {"auto_game": {"id": channel_id, "description": "Auto-game channel"}}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigEmojiGamePanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save channel.", ephemeral=True)
        
        select.callback = on_channel_select
        self.add_item(select)
    
    def _add_duration_select(self):
        """Add the game duration select dropdown."""
        scheduling = self.config.get("scheduling", {})
        
        jobs = scheduling.get("jobs", {})
        emoji_game = jobs.get("games", {}).get("emoji", {})
        current_duration = emoji_game.get("duration_minutes", 5)
        
        # Build options from DURATION_PRESETS
        options = []
        for minutes, label in self.DURATION_PRESETS:
            options.append(discord.SelectOption(
                label=label,
                value=str(minutes),
                default=(minutes == current_duration)
            ))
        
        select = discord.ui.Select(
            placeholder="Game Duration",
            options=options,
            row=1
        )
        
        async def on_duration_select(interaction: discord.Interaction):
            if not interaction.data or "values" not in interaction.data or not interaction.data["values"]:
                return
            
            duration_minutes = int(interaction.data["values"][0])
            
            success = set_guild_config(
                self.guild_id,
                {"scheduling": {"jobs": {"games": {"emoji": {"duration_minutes": duration_minutes}}}}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigEmojiGamePanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save duration.", ephemeral=True)
        
        select.callback = on_duration_select
        self.add_item(select)

    def build_embed(self) -> discord.Embed:
        """Build emoji game configuration embed."""
        auto_game_enabled = get_feature_status(self.config, "features.auto_game")
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        emoji_game = jobs.get("games", {}).get("emoji", {})
        emoji_schedule = normalize_schedule_read(emoji_game)
        game_time_display = get_schedule_display(emoji_schedule)
        game_duration = emoji_game.get("duration_minutes", 5)
        
        channels = self.config.get("channels", {})
        game_channel = channels.get("auto_game", {}).get("id")
        
        embed = discord.Embed(
            title="🎲 Emoji Game",
            description="Configure emoji game behavior. ⏰ Start time is managed via System → Scheduling (read-only here).",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Status",
            value=format_boolean(auto_game_enabled),
            inline=True
        )
        
        embed.add_field(
            name="Channel",
            value=format_channel(game_channel) if game_channel else "❌ Not set",
            inline=True
        )
        
        if auto_game_enabled:
            embed.add_field(name="Start Time (read-only)", value=game_time_display, inline=True)
            embed.add_field(name="Duration", value=f"{game_duration} minutes", inline=True)
        
        embed.set_footer(text="Any posting feature requires explicit channel selection")
        
        return embed

    @discord.ui.button(label="Set Start Time", style=discord.ButtonStyle.primary, emoji="⏰", row=2)
    async def button_set_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Automations panel to edit schedule."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigAutomationsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Enable Auto Game", style=discord.ButtonStyle.success, emoji="✅", row=2)
    async def button_enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enable auto game - requires channel to be set first."""
        if get_feature_status(self.config, "features.auto_game"):
            await interaction.response.send_message("✅ Auto game already enabled!", ephemeral=True)
            return
        
        channels = self.config.get("channels", {})
        game_channel = channels.get("auto_game", {}).get("id")
        
        if not game_channel:
            await interaction.response.send_message(
                "❌ Please set a channel first using the dropdown above!",
                ephemeral=True
            )
            return
        
        success = set_guild_config(
            self.guild_id,
            {
                "features": {"auto_game": True},
                "scheduling": {"jobs": {"games": {"emoji": {"enabled": True}}}},
            },
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigEmojiGamePanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to save.", ephemeral=True)

    @discord.ui.button(label="Disable Auto Game", style=discord.ButtonStyle.danger, emoji="❌", row=2)
    async def button_disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Disable auto game."""
        if not get_feature_status(self.config, "features.auto_game"):
            await interaction.response.send_message("❌ Auto game already disabled!", ephemeral=True)
            return
        
        success = set_guild_config(
            self.guild_id,
            {
                "features": {"auto_game": False},
                "scheduling": {"jobs": {"games": {"emoji": {"enabled": False}}}},
            },
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigEmojiGamePanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to save.", ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=3)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to games overview."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigGamesPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# COMMUNITY JOBS PANEL - Router
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigCommunityJobsPanel(discord.ui.View):
    """Community Jobs Router - Engagement Automation.
    
    SCOPE: Routes to individual community engagement features.
    
    This panel organizes community automation jobs into separate,
    independently configurable modules for clarity and maintainability.
    """
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    def build_embed(self) -> discord.Embed:
        """Build community jobs router embed."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        community_jobs = jobs.get("community", {})
        
        random_msgs = community_jobs.get("random_messages", {})
        nudge = community_jobs.get("nudge", {})
        
        rm_enabled = random_msgs.get("enabled", False)
        nudge_enabled = nudge.get("enabled", False)
        
        embed = discord.Embed(
            title="✨ Community Jobs",
            description="Select a community engagement feature to configure.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💬 Random Messages",
            value=f"Status: {format_boolean(rm_enabled)}\n🔧 Send random messages to increase engagement",
            inline=False
        )
        
        embed.add_field(
            name="👈 User Nudges",
            value=f"Status: {format_boolean(nudge_enabled)}\n👥 Encourage inactive users to participate",
            inline=False
        )
        
        embed.set_footer(text="Each job manages its own channel and settings")
        return embed

    @discord.ui.button(label="Random Messages", style=discord.ButtonStyle.primary, emoji="💬", row=0)
    async def button_random_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Random Messages configuration."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigRandomMessagesPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="User Nudges", style=discord.ButtonStyle.primary, emoji="👈", row=0)
    async def button_nudges(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open User Nudges configuration."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigUserNudgesPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to Overview."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigOverviewPanel(self.guild_id, config)
        embed = view.build_overview_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# RANDOM MESSAGES PANEL
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigRandomMessagesPanel(discord.ui.View):
    """Random Messages Configuration Panel."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config
        
        # Add channel select
        self._add_channel_select()
    
    def _add_channel_select(self):
        """Add the random messages channel select dropdown."""
        channels = self.config.get("channels", {})
        rm_channel_id = channels.get("random_messages", {}).get("id")
        
        select = discord.ui.ChannelSelect(
            placeholder="Random Messages Channel",
            channel_types=[discord.ChannelType.text],
            min_values=0,
            max_values=1,
            row=0
        )
        
        async def on_channel_select(interaction: discord.Interaction):
            channel_id = None
            if interaction.data and "values" in interaction.data and interaction.data["values"]:
                channel_id = int(interaction.data["values"][0])
            
            success = set_guild_config(
                self.guild_id,
                {"channels": {"random_messages": {"id": channel_id, "description": "Channel for random messages", "last_used": None}}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigRandomMessagesPanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save channel.", ephemeral=True)
        
        select.callback = on_channel_select
        self.add_item(select)

    def build_embed(self) -> discord.Embed:
        """Build random messages configuration embed."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        community_jobs = jobs.get("community", {})
        random_msgs = community_jobs.get("random_messages", {})
        
        rm_schedule = normalize_schedule_read(random_msgs)
        rm_enabled = random_msgs.get("enabled", False)
        
        channels = self.config.get("channels", {})
        rm_channel = channels.get("random_messages", {}).get("id")
        
        embed = discord.Embed(
            title="💬 Random Messages",
            description="Send random messages to increase community engagement.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Status",
            value=format_boolean(rm_enabled),
            inline=True
        )
        
        embed.add_field(
            name="Channel",
            value=format_channel(rm_channel) if rm_channel else "❌ Not set",
            inline=True
        )
        
        rm_display = get_schedule_display(rm_schedule)
        embed.add_field(
            name="Schedule",
            value=f"{rm_display} (read-only)",
            inline=False
        )
        
        embed.set_footer(text="⏰ Times and intervals managed in Automations panel")
        return embed

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success, emoji="✅", row=1)
    async def button_enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enable random messages."""
        if get_feature_status(self.config, "features.random_messages"):
            await interaction.response.send_message("✅ Already enabled!", ephemeral=True)
            return
        
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"community": {"random_messages": {"enabled": True}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigRandomMessagesPanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to enable.", ephemeral=True)

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger, emoji="❌", row=1)
    async def button_disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Disable random messages."""
        if not get_feature_status(self.config, "features.random_messages"):
            await interaction.response.send_message("❌ Already disabled!", ephemeral=True)
            return
        
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"community": {"random_messages": {"enabled": False}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigRandomMessagesPanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to disable.", ephemeral=True)

    @discord.ui.button(label="Edit Timing", style=discord.ButtonStyle.primary, emoji="⏰", row=1)
    async def button_edit_timing(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Automations panel."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigAutomationsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to Community Jobs router."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigCommunityJobsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# USER NUDGES PANEL
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigUserNudgesPanel(discord.ui.View):
    """User Nudges Configuration Panel."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    def build_embed(self) -> discord.Embed:
        """Build user nudges configuration embed."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        community_jobs = jobs.get("community", {})
        nudge = community_jobs.get("nudge", {})
        
        nudge_schedule = normalize_schedule_read(nudge)
        nudge_enabled = nudge.get("enabled", False)
        
        embed = discord.Embed(
            title="👈 User Nudges",
            description="Encourage inactive users to participate.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Status",
            value=format_boolean(nudge_enabled),
            inline=True
        )
        
        nudge_display = get_schedule_display(nudge_schedule)
        embed.add_field(
            name="Schedule",
            value=f"{nudge_display} (read-only)",
            inline=True
        )
        
        embed.add_field(
            name="Channel",
            value="Uses Infrastructure Nudge channel",
            inline=False
        )
        
        embed.set_footer(text="⏰ Times managed in Automations panel")
        return embed

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success, emoji="✅", row=0)
    async def button_enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enable nudges."""
        if get_feature_status(self.config, "features.nudges"):
            await interaction.response.send_message("✅ Already enabled!", ephemeral=True)
            return
        
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"community": {"nudge": {"enabled": True}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigUserNudgesPanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to enable.", ephemeral=True)

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger, emoji="❌", row=0)
    async def button_disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Disable nudges."""
        if not get_feature_status(self.config, "features.nudges"):
            await interaction.response.send_message("❌ Already disabled!", ephemeral=True)
            return
        
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"community": {"nudge": {"enabled": False}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigUserNudgesPanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to disable.", ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=1)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to Community Jobs router."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigCommunityJobsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# COMMUNITY JOB TIME MODAL - Shared time setter for random messages and nudges
# ════════════════════════════════════════════════════════════════════════════════

class CommunityJobTimeModal(discord.ui.Modal, title="Set Job Time"):
    """Modal for setting community job start times."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any], job_type: str, modal_title: str):
        super().__init__(title=modal_title)
        self.guild_id = guild_id
        self.config = config
        self.job_type = job_type  # "random_messages" or "nudge"
        
        # Get current time from normalized schedule
        scheduling = config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        job_config = jobs.get("community", {}).get(job_type, {})
        schedule = normalize_schedule_read(job_config)
        current_time = schedule.get("time", "14:00" if job_type == "random_messages" else "19:00")
        
        self.time_input = discord.ui.TextInput(
            label="Start Time (HH:MM)",
            placeholder="e.g., 14:00 or 20:30",
            default=current_time,
            min_length=5,
            max_length=5,
            required=True
        )
        self.add_item(self.time_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        time_str = self.time_input.value.strip()
        
        # Validate time format
        try:
            hour, minute = map(int, time_str.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                await interaction.response.send_message(
                    "❌ Invalid time! Use 24-hour format (00:00 - 23:59)",
                    ephemeral=True
                )
                return
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "❌ Invalid format! Use HH:MM (e.g., 14:00)",
                ephemeral=True
            )
            return
        
        # Save the time using normalized schedule structure
        schedule = normalize_schedule_write("daily", time=time_str)
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"community": {self.job_type: {"schedule": schedule}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            await interaction.response.send_message(
                f"✅ {self.job_type.replace('_', ' ').title()} time set to {time_str}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to save time.",
                ephemeral=True
            )


# ════════════════════════════════════════════════════════════════════════════════
# SYSTEM JOB TIME MODAL - Time setter for system jobs (XP, Maintenance, MOTD)
# ════════════════════════════════════════════════════════════════════════════════

class SystemJobTimeModal(discord.ui.Modal, title="Set Job Time"):
    """Modal for setting system job start times."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any], job_type: str, modal_title: str):
        super().__init__(title=modal_title)
        self.guild_id = guild_id
        self.config = config
        self.job_type = job_type  # "xp_daily_bonus", "maintenance", "motd"
        
        # Get current time from normalized schedule
        scheduling = config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        system_jobs = jobs.get("system", {})
        
        # Navigate to correct job config based on type
        if job_type == "xp_daily_bonus":
            job_config = system_jobs.get("xp_rewards", {}).get("daily_bonus", {})
            default_time = "08:00"
        elif job_type == "maintenance":
            job_config = system_jobs.get("maintenance", {}).get("memory_decay", {})
            default_time = "02:00"
        else:  # motd
            job_config = system_jobs.get(job_type, {})
            default_time = "08:00"
        
        schedule = normalize_schedule_read(job_config)
        current_time = schedule.get("time", default_time)
        
        self.time_input = discord.ui.TextInput(
            label="Start Time (HH:MM)",
            placeholder=f"e.g., {default_time}",
            default=current_time,
            min_length=5,
            max_length=5,
            required=True
        )
        self.add_item(self.time_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        time_str = self.time_input.value.strip()
        
        # Validate time format
        try:
            hour, minute = map(int, time_str.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                await interaction.response.send_message(
                    "❌ Invalid time! Use 24-hour format (00:00 - 23:59)",
                    ephemeral=True
                )
                return
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "❌ Invalid format! Use HH:MM (e.g., 08:00)",
                ephemeral=True
            )
            return
        
        # Save the time using normalized schedule structure
        schedule = normalize_schedule_write("daily", time=time_str)
        
        # Build update path based on job type
        if self.job_type == "xp_daily_bonus":
            update = {"scheduling": {"jobs": {"system": {"xp_rewards": {"daily_bonus": {"schedule": schedule}}}}}}
        elif self.job_type == "maintenance":
            update = {"scheduling": {"jobs": {"system": {"maintenance": {"memory_decay": {"schedule": schedule}}}}}}
        else:  # motd
            update = {"scheduling": {"jobs": {"system": {self.job_type: {"schedule": schedule}}}}}
        
        success = set_guild_config(
            self.guild_id,
            update,
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            job_display = self.job_type.replace("_", " ").title()
            await interaction.response.send_message(
                f"✅ {job_display} time set to {time_str}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to update time. Check logs.",
                ephemeral=True
            )


# ════════════════════════════════════════════════════════════════════════════════
# SYSTEM JOBS PANEL - MOTD & Giveaways
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigSystemJobsPanel(discord.ui.View):
    """System Jobs Router - Routes to individual system job modules.
    
    SCOPE: Navigation hub for system-level automation.
    
    This panel serves as a router to:
    - MOTD announcements
    - XP bonus scheduling  
    - Giveaway management
    - Memory maintenance
    
    Each system has its own configuration panel with independent controls.
    """
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    def build_embed(self) -> discord.Embed:
        """Build system jobs router embed."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        system_jobs = jobs.get("system", {})
        
        motd = system_jobs.get("motd", {})
        giveaways = system_jobs.get("giveaways", {})
        maintenance = system_jobs.get("maintenance", {}).get("memory_decay", {})
        xp_rewards = system_jobs.get("xp_rewards", {}).get("daily_bonus", {})
        
        # Normalize schedules
        motd_schedule = normalize_schedule_read(motd)
        giveaway_schedule = normalize_schedule_read(giveaways)
        maintenance_schedule = normalize_schedule_read(maintenance)
        xp_schedule = normalize_schedule_read(xp_rewards)
        
        embed = discord.Embed(
            title="⚙️ System Jobs",
            description="Configure system-level automated jobs. Select a module below to manage it.",
            color=discord.Color.blue()
        )
        
        # MOTD Status
        motd_enabled = motd.get("enabled", False)
        motd_display = get_schedule_display(motd_schedule)
        embed.add_field(
            name="📅 Message of the Day",
            value=f"{format_boolean(motd_enabled)} • {motd_display}",
            inline=False
        )
        
        # XP Daily Bonus Status
        xp_enabled = xp_rewards.get("enabled", True)
        xp_display = get_schedule_display(xp_schedule)
        embed.add_field(
            name="💰 XP Daily Bonus",
            value=f"{format_boolean(xp_enabled)} • {xp_display}",
            inline=False
        )
        
        # Giveaways Status
        giveaway_enabled = giveaways.get("enabled", False)
        giveaway_display = get_schedule_display(giveaway_schedule)
        embed.add_field(
            name="🎁 Giveaways",
            value=f"{format_boolean(giveaway_enabled)} • {giveaway_display}",
            inline=False
        )
        
        # Maintenance Status
        maintenance_enabled = maintenance.get("enabled", True)
        maintenance_display = get_schedule_display(maintenance_schedule)
        embed.add_field(
            name="🤖 Memory Maintenance",
            value=f"{format_boolean(maintenance_enabled)} • {maintenance_display}",
            inline=False
        )
        
        embed.set_footer(text="System jobs manage core guild operations")
        return embed

    @discord.ui.button(label="MOTD", style=discord.ButtonStyle.primary, emoji="📅", row=0)
    async def button_motd(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open MOTD module."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigMOTDPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="XP Bonus", style=discord.ButtonStyle.primary, emoji="💰", row=0)
    async def button_xp_bonus(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open XP Bonus module."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigXPPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Giveaways", style=discord.ButtonStyle.primary, emoji="🎁", row=0)
    async def button_giveaways(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Giveaways module."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigGiveawaysPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Maintenance", style=discord.ButtonStyle.primary, emoji="🤖", row=0)
    async def button_maintenance(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Memory Maintenance module."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigMaintenancePanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=1)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to Overview."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigOverviewPanel(self.guild_id, config)
        embed = view.build_overview_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# MOTD MODULE - Message of the Day configuration
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigMOTDPanel(discord.ui.View):
    """MOTD Module - Configure Message of the Day announcements."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config
        
        # Add MOTD channel select
        self._add_motd_channel_select()
    
    def _add_motd_channel_select(self):
        """Add MOTD channel select dropdown."""
        select = discord.ui.ChannelSelect(
            placeholder="MOTD Channel",
            channel_types=[discord.ChannelType.text],
            min_values=0,
            max_values=1,
            row=0
        )
        
        async def on_channel_select(interaction: discord.Interaction):
            channel_id = None
            if interaction.data and "values" in interaction.data and interaction.data["values"]:
                channel_id = int(interaction.data["values"][0])
            
            success = set_guild_config(
                self.guild_id,
                {"channels": {"motd": {"id": channel_id, "description": "Channel for message of the day", "last_used": None}}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                self.config = get_guild_config(self.guild_id)
                await interaction.response.defer()
                if interaction.message:
                    new_view = GuildConfigMOTDPanel(self.guild_id, self.config)
                    await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
            else:
                await interaction.response.send_message("❌ Failed to save channel.", ephemeral=True)
        
        select.callback = on_channel_select
        self.add_item(select)

    def build_embed(self) -> discord.Embed:
        """Build MOTD configuration embed."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        motd = jobs.get("system", {}).get("motd", {})
        
        motd_schedule = normalize_schedule_read(motd)
        
        channels = self.config.get("channels", {})
        motd_channel = channels.get("motd", {}).get("id")
        
        embed = discord.Embed(
            title="📅 Message of the Day",
            description="Configure MOTD announcements. Times are managed in Automations panel.",
            color=discord.Color.blue()
        )
        
        motd_enabled = motd.get("enabled", False)
        motd_display = get_schedule_display(motd_schedule)
        embed.add_field(
            name="Status",
            value=(
                f"{format_boolean(motd_enabled)}\n"
                f"Channel: {format_channel(motd_channel) if motd_channel else '❌ Not set'}\n"
                f"Schedule: {motd_display}"
            ),
            inline=False
        )
        
        embed.set_footer(text="Set schedule times in Automations panel")
        return embed

    @discord.ui.button(label="Edit Timing", style=discord.ButtonStyle.primary, emoji="⏰", row=1)
    async def button_edit_timing(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Automations panel to edit schedule."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigAutomationsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success, emoji="✅", row=1)
    async def button_enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enable MOTD."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        motd = jobs.get("system", {}).get("motd", {})
        
        if motd.get("enabled", False):
            await interaction.response.send_message("✅ MOTD already enabled!", ephemeral=True)
            return
        
        channels = self.config.get("channels", {})
        motd_channel = channels.get("motd", {}).get("id")
        
        if not motd_channel:
            await interaction.response.send_message(
                "❌ Please set a channel first using the dropdown above!",
                ephemeral=True
            )
            return
        
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"system": {"motd": {"enabled": True}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigMOTDPanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to save.", ephemeral=True)

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger, emoji="❌", row=1)
    async def button_disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Disable MOTD."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        motd = jobs.get("system", {}).get("motd", {})
        
        if not motd.get("enabled", False):
            await interaction.response.send_message("✅ MOTD already disabled!", ephemeral=True)
            return
        
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"system": {"motd": {"enabled": False}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigMOTDPanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to save.", ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to System Jobs router."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigSystemJobsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# XP BONUS MODULE - Daily XP bonus scheduling
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigXPPanel(discord.ui.View):
    """XP Bonus Module - Configure Daily XP Bonus scheduling."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    def build_embed(self) -> discord.Embed:
        """Build XP bonus configuration embed."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        xp_rewards = jobs.get("system", {}).get("xp_rewards", {}).get("daily_bonus", {})
        
        xp_schedule = normalize_schedule_read(xp_rewards)
        
        channels = self.config.get("channels", {})
        xp_channel = channels.get("xp", {}).get("id")
        
        embed = discord.Embed(
            title="💰 XP Daily Bonus",
            description="Configure daily XP bonus announcements. Times are managed in Automations panel.",
            color=discord.Color.blue()
        )
        
        xp_enabled = xp_rewards.get("enabled", True)
        xp_display = get_schedule_display(xp_schedule)
        embed.add_field(
            name="Status",
            value=(
                f"{format_boolean(xp_enabled)}\n"
                f"Channel: {format_channel(xp_channel) if xp_channel else '❌ Not set (use Channels → Messaging)'}\n"
                f"Schedule: {xp_display}"
            ),
            inline=False
        )
        
        embed.set_footer(text="Set schedule times in Automations panel | Configure channel in Channels panel")
        return embed

    @discord.ui.button(label="Edit Timing", style=discord.ButtonStyle.primary, emoji="⏰", row=0)
    async def button_edit_timing(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Automations panel to edit schedule."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigAutomationsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success, emoji="✅", row=0)
    async def button_enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enable XP daily bonus."""
        channels = self.config.get("channels", {})
        xp_channel = channels.get("xp", {}).get("id")
        
        if not xp_channel:
            await interaction.response.send_message(
                "❌ Please set XP channel in Channels → Messaging first!",
                ephemeral=True
            )
            return
        
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"system": {"xp_rewards": {"daily_bonus": {"enabled": True}}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigXPPanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to save.", ephemeral=True)

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger, emoji="❌", row=0)
    async def button_disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Disable XP daily bonus."""
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"system": {"xp_rewards": {"daily_bonus": {"enabled": False}}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigXPPanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to save.", ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=1)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to System Jobs router."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigSystemJobsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# GIVEAWAYS MODULE - Giveaway management
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigGiveawaysPanel(discord.ui.View):
    """Giveaways Module - Configure Giveaway checking."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    def build_embed(self) -> discord.Embed:
        """Build giveaways configuration embed."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        giveaways = jobs.get("system", {}).get("giveaways", {})
        
        giveaway_schedule = normalize_schedule_read(giveaways)
        
        embed = discord.Embed(
            title="🎁 Giveaways",
            description="Configure giveaway checking intervals. Times are managed in Automations panel.",
            color=discord.Color.blue()
        )
        
        giveaway_enabled = giveaways.get("enabled", False)
        giveaway_display = get_schedule_display(giveaway_schedule)
        embed.add_field(
            name="Status",
            value=(
                f"{format_boolean(giveaway_enabled)}\n"
                f"Check Interval: {giveaway_display}\n"
                f"(Use /giveaway command to create giveaways)"
            ),
            inline=False
        )
        
        embed.set_footer(text="Set check intervals in Automations panel")
        return embed

    @discord.ui.button(label="Edit Interval", style=discord.ButtonStyle.primary, emoji="⏰", row=0)
    async def button_edit_interval(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Automations panel to edit check interval."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigAutomationsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success, emoji="✅", row=0)
    async def button_enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enable giveaway checks."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        giveaways = jobs.get("system", {}).get("giveaways", {})
        
        if giveaways.get("enabled", False):
            await interaction.response.send_message("✅ Giveaway checks already enabled!", ephemeral=True)
            return
        
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"system": {"giveaways": {"enabled": True}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigGiveawaysPanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to save.", ephemeral=True)

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger, emoji="❌", row=0)
    async def button_disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Disable giveaway checks."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        giveaways = jobs.get("system", {}).get("giveaways", {})
        
        if not giveaways.get("enabled", False):
            await interaction.response.send_message("✅ Giveaway checks already disabled!", ephemeral=True)
            return
        
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"system": {"giveaways": {"enabled": False}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigGiveawaysPanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to save.", ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=1)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to System Jobs router."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigSystemJobsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# MAINTENANCE MODULE - Memory maintenance scheduling
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigMaintenancePanel(discord.ui.View):
    """Maintenance Module - Configure Memory Maintenance scheduling."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    def build_embed(self) -> discord.Embed:
        """Build maintenance configuration embed."""
        scheduling = self.config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        maintenance = jobs.get("system", {}).get("maintenance", {}).get("memory_decay", {})
        
        maintenance_schedule = normalize_schedule_read(maintenance)
        
        embed = discord.Embed(
            title="🤖 Memory Maintenance",
            description="Configure memory decay cleanup scheduling. Times are managed in Automations panel.",
            color=discord.Color.blue()
        )
        
        maintenance_enabled = maintenance.get("enabled", True)
        maintenance_display = get_schedule_display(maintenance_schedule)
        embed.add_field(
            name="Status",
            value=(
                f"{format_boolean(maintenance_enabled)}\n"
                f"Schedule: {maintenance_display}\n"
                f"(Automatic memory decay cleanup)"
            ),
            inline=False
        )
        
        embed.set_footer(text="Set schedule times in Automations panel")
        return embed

    @discord.ui.button(label="Edit Timing", style=discord.ButtonStyle.primary, emoji="⏰", row=0)
    async def button_edit_timing(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Automations panel to edit schedule."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigAutomationsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success, emoji="✅", row=0)
    async def button_enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enable memory maintenance."""
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"system": {"maintenance": {"memory_decay": {"enabled": True}}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigMaintenancePanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to save.", ephemeral=True)

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger, emoji="❌", row=0)
    async def button_disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Disable memory maintenance."""
        success = set_guild_config(
            self.guild_id,
            {"scheduling": {"jobs": {"system": {"maintenance": {"memory_decay": {"enabled": False}}}}}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            self.config = get_guild_config(self.guild_id)
            await interaction.response.defer()
            if interaction.message:
                new_view = GuildConfigMaintenancePanel(self.guild_id, self.config)
                await interaction.message.edit(embed=new_view.build_embed(), view=new_view)
        else:
            await interaction.response.send_message("❌ Failed to save.", ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=1)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to System Jobs router."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigSystemJobsPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class RandomMessagesConfigModal(discord.ui.Modal, title="Configure Random Messages"):
    """Consolidated modal for Random Messages: start time, interval, and jitter."""

    start_time = discord.ui.TextInput(
        label="Start Time (HH:MM)",
        placeholder="e.g., 08:00",
        min_length=5,
        max_length=5,
        required=True
    )

    interval_hours = discord.ui.TextInput(
        label="Interval (hours)",
        placeholder="e.g., 8",
        min_length=1,
        max_length=4,
        required=True
    )

    jitter_minutes = discord.ui.TextInput(
        label="Jitter (±minutes, optional)",
        placeholder="e.g., 30 (leave empty for 0)",
        min_length=0,
        max_length=4,
        required=False
    )

    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__()
        self.guild_id = guild_id
        self.config = config

        scheduling = config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        job_config = jobs.get("community", {}).get("random_messages", {})
        schedule = normalize_schedule_read(job_config)
        
        # Get current values
        current_time = schedule.get("time", "08:00")
        interval_minutes = schedule.get("every_minutes", 480)
        current_interval = interval_minutes // 60
        current_jitter = job_config.get("jitter_minutes", 0)
        
        self.start_time.default = current_time
        self.interval_hours.default = str(current_interval)
        self.jitter_minutes.default = str(current_jitter) if current_jitter else ""

    async def on_submit(self, interaction: discord.Interaction):
        """Save all random messages configuration."""
        # Validate start time
        time_str = self.start_time.value.strip()
        try:
            hour, minute = map(int, time_str.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                await interaction.response.send_message(
                    "❌ Invalid start time! Use 24-hour format (00:00 - 23:59)",
                    ephemeral=True
                )
                return
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "❌ Invalid start time format! Use HH:MM (e.g., 14:00)",
                ephemeral=True
            )
            return

        # Validate interval
        try:
            interval_val = int(self.interval_hours.value)
            if interval_val < 1:
                await interaction.response.send_message(
                    "❌ Interval must be at least 1 hour.",
                    ephemeral=True
                )
                return
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid interval! Please enter a valid number of hours.",
                ephemeral=True
            )
            return

        # Validate jitter (optional)
        jitter_val = 0
        if self.jitter_minutes.value.strip():
            try:
                jitter_val = int(self.jitter_minutes.value.strip())
                if jitter_val < 0:
                    await interaction.response.send_message(
                        "❌ Jitter must be 0 or greater.",
                        ephemeral=True
                    )
                    return
                if jitter_val > 1440:  # Max 24 hours of jitter
                    await interaction.response.send_message(
                        "❌ Jitter cannot exceed 1440 minutes (24 hours).",
                        ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "❌ Invalid jitter! Please enter a valid number of minutes.",
                    ephemeral=True
                )
                return

        # Build schedule and update config
        schedule = normalize_schedule_write("interval", every_hours=interval_val, time=time_str)
        
        update_dict = {
            "scheduling": {
                "jobs": {
                    "community": {
                        "random_messages": {
                            "schedule": schedule,
                            "jitter_minutes": jitter_val
                        }
                    }
                }
            }
        }
        
        success = set_guild_config(
            self.guild_id,
            update_dict,
            audit_user_id=str(interaction.user.id)
        )

        if success:
            jitter_display = f" with ±{jitter_val}m jitter" if jitter_val > 0 else ""
            await interaction.response.send_message(
                f"✅ Random Messages configured:\n"
                f"• Start: {time_str}\n"
                f"• Interval: Every {interval_val} hour(s){jitter_display}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to save configuration.",
                ephemeral=True
            )


class RandomMessagesIntervalModal(discord.ui.Modal, title="Set Random Messages Interval"):
    """Modal for setting random messages interval (hours)."""

    interval_hours = discord.ui.TextInput(
        label="Interval (hours)",
        placeholder="8",
        min_length=1,
        max_length=4,
        required=True
    )

    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__()
        self.guild_id = guild_id
        self.config = config

        scheduling = config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        job_config = jobs.get("community", {}).get("random_messages", {})
        schedule = normalize_schedule_read(job_config)
        # Get interval in hours (convert from minutes if needed)
        interval_minutes = schedule.get("every_minutes", 480)
        current_interval = interval_minutes // 60
        self.interval_hours.default = str(current_interval)

    async def on_submit(self, interaction: discord.Interaction):
        """Save random messages interval."""
        try:
            interval_val = int(self.interval_hours.value)
            if interval_val < 1:
                await interaction.response.send_message(
                    "❌ Interval must be at least 1 hour.",
                    ephemeral=True
                )
                return

            # Save using normalized interval schedule structure
            schedule = normalize_schedule_write("interval", every_hours=interval_val)
            success = set_guild_config(
                self.guild_id,
                {"scheduling": {"jobs": {"community": {"random_messages": {"schedule": schedule}}}}},
                audit_user_id=str(interaction.user.id)
            )

            if success:
                await interaction.response.send_message(
                    f"✅ Random messages will post every {interval_val} hour(s)",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Failed to save interval.",
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number of hours.",
                ephemeral=True
            )


class GiveawayIntervalModal(discord.ui.Modal, title="Set Giveaway Poll Interval"):
    """Modal for setting giveaway check interval."""

    interval_minutes = discord.ui.TextInput(
        label="Interval (minutes)",
        placeholder="1",
        min_length=1,
        max_length=4,
        required=True
    )

    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__()
        self.guild_id = guild_id
        self.config = config

        scheduling = config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        job_config = jobs.get("system", {}).get("giveaways", {})
        schedule = normalize_schedule_read(job_config)
        current_interval = schedule.get("every_minutes", 1)
        self.interval_minutes.default = str(current_interval)

    async def on_submit(self, interaction: discord.Interaction):
        """Save giveaway interval."""
        try:
            interval_val = int(self.interval_minutes.value)
            if interval_val < 1:
                await interaction.response.send_message(
                    "❌ Interval must be at least 1 minute.",
                    ephemeral=True
                )
                return

            # Save using normalized interval schedule structure
            schedule = normalize_schedule_write("interval", every_minutes=interval_val)
            success = set_guild_config(
                self.guild_id,
                {"scheduling": {"jobs": {"system": {"giveaways": {"schedule": schedule}}}}},
                audit_user_id=str(interaction.user.id)
            )

            if success:
                await interaction.response.send_message(
                    f"✅ Giveaway interval set to every {interval_val} minute(s)",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Failed to save interval.",
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number of minutes.",
                ephemeral=True
            )


class GuildConfigLimitsPanel(discord.ui.View):
    """Configure usage limits (conversation, daily, burst)."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    def build_embed(self) -> discord.Embed:
        """Build limits embed."""
        limits = self.config.get("usage_limits", {})
        
        conv_limits = limits.get("conversation", {})
        daily_limits = limits.get("daily", {})
        burst_limits = limits.get("burst", {})
        
        embed = discord.Embed(
            title="⏱️ Usage Limits",
            description="Configure rate limiting and protection.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💬 Conversation Limits",
            value=(
                f"Max turns/session: {conv_limits.get('max_turns_per_session', 3)}\n"
                f"Session timeout: {conv_limits.get('session_timeout_seconds', 60)}s\n"
                f"Cooldown: {conv_limits.get('cooldown_seconds', 30)}s"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📅 Daily Limits",
            value=f"Max messages/day: {daily_limits.get('max_messages', 50)}",
            inline=False
        )
        
        embed.add_field(
            name="⚡ Burst Protection",
            value=(
                f"Max messages: {burst_limits.get('max_messages', 10)}\n"
                f"Window: {burst_limits.get('window_seconds', 60)}s"
            ),
            inline=False
        )
        
        return embed

    @discord.ui.button(label="Edit Conversation", style=discord.ButtonStyle.primary, row=0)
    async def button_conversation(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit conversation limits."""
        modal = ConversationLimitsModal(self.guild_id, self.config)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit Daily", style=discord.ButtonStyle.primary, row=0)
    async def button_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit daily limits."""
        modal = DailyLimitsModal(self.guild_id, self.config)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit Burst", style=discord.ButtonStyle.primary, row=0)
    async def button_burst(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit burst protection."""
        modal = BurstLimitsModal(self.guild_id, self.config)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to overview."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigOverviewPanel(self.guild_id, config)
        embed = view.build_overview_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# PERSONA PANEL - Bot Personality Configuration
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigPersonaPanel(discord.ui.View):
    """Configure bot personas for the guild."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config
        self._add_persona_select()
    
    def _add_persona_select(self):
        """Add persona selection dropdown."""
        from abby_core.personality.manager import get_personality_manager
        try:
            manager = get_personality_manager()
            registry = manager.get_available_personas()
            personas = sorted([name for name, info in registry.items() if info.get("enabled", True)])
            
            options = []
            for persona in personas:
                emoji_map = {"bunny": "🐰", "kiki": "🐱", "kitten": "🐱", "felix": "🦊", 
                           "owl": "🦉", "squirrel": "🐿️", "panda": "🐼"}
                emoji = emoji_map.get(persona, "🤖")
                options.append(discord.SelectOption(label=persona.capitalize(), value=persona, emoji=emoji))
            
            select = discord.ui.Select(placeholder="Choose a persona...", min_values=1, max_values=1, options=options, row=0)
            
            async def on_select(interaction: discord.Interaction):
                persona_name = select.values[0]
                success = set_guild_config(
                    self.guild_id,
                    {"active_persona": persona_name},
                    audit_user_id=str(interaction.user.id)
                )
                if success:
                    await interaction.response.send_message(f"✅ Persona set to **{persona_name.capitalize()}**", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Failed to update persona.", ephemeral=True)
            
            select.callback = on_select
            self.add_item(select)
        except Exception as e:
            logger.error(f"[❌] Failed to load personas: {e}")
    
    def build_embed(self) -> discord.Embed:
        """Build persona configuration embed."""
        embed = discord.Embed(
            title="🎭 Persona Configuration",
            description="Select the bot personality for your server",
            color=discord.Color.blue()
        )
        
        active = self.config.get("active_persona", "bunny")
        embed.add_field(
            name="Currently Active",
            value=f"**{active.capitalize()}**",
            inline=False
        )
        
        embed.add_field(
            name="Available Personas",
            value="Use the dropdown below to switch personas",
            inline=False
        )
        
        embed.set_footer(text="Personas define how Abby interacts with your server")
        return embed
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to Features panel."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigFeaturesPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# INTEGRATIONS PANEL - Third-Party Service Configuration
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigIntegrationsPanel(discord.ui.View):
    """Configure third-party integrations (Twitch, etc.)."""
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config
    
    def build_embed(self) -> discord.Embed:
        """Build integrations configuration embed."""
        embed = discord.Embed(
            title="🔗 Integrations",
            description="Configure third-party service integrations",
            color=discord.Color.blue()
        )
        
        integrations = self.config.get("integrations", {})
        twitch_enabled = integrations.get("twitch_enabled", False)
        twitch_channel = integrations.get("twitch_channel_id")
        
        status = "✅ Enabled" if twitch_enabled else "❌ Disabled"
        channel_info = f"<#{twitch_channel}>" if twitch_channel else "Not set"
        
        embed.add_field(
            name="🎬 Twitch Notifications",
            value=f"Status: {status}\nChannel: {channel_info}",
            inline=False
        )
        
        embed.set_footer(text="Use buttons below to configure integrations")
        return embed
    
    @discord.ui.button(label="Configure Twitch", emoji="🎬", style=discord.ButtonStyle.primary, row=0)
    async def button_twitch(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show Twitch configuration modal."""
        modal = TwitchConfigModal(self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to Features panel."""
        config = get_guild_config(self.guild_id)
        view = GuildConfigFeaturesPanel(self.guild_id, config)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# MODALS - Input Forms
# ════════════════════════════════════════════════════════════════════════════════

class TimezoneModal(discord.ui.Modal, title="Set Guild Timezone"):
    """Modal for setting timezone."""
    
    timezone = discord.ui.TextInput(
        label="Timezone (e.g., US/Eastern, Europe/London)",
        placeholder="UTC",
        min_length=1,
        max_length=50,
        required=True
    )
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__()
        self.guild_id = guild_id
        self.config = config

    async def on_submit(self, interaction: discord.Interaction):
        """Save timezone."""
        import pytz
        try:
            # Validate timezone
            tz = pytz.timezone(self.timezone.value)
            
            success = set_guild_config(
                self.guild_id,
                {"scheduling": {"timezone": self.timezone.value}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                await interaction.response.send_message(
                    f"✅ Timezone set to **{self.timezone.value}**",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("❌ Failed to save.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Invalid timezone: {e}",
                ephemeral=True
            )


class AutoGameStartTimeModal(discord.ui.Modal, title="Set Auto-Game Start Time"):
    """Modal for setting auto-game start time."""
    
    start_time = discord.ui.TextInput(
        label="Start Time (24-hour format: HH:MM)",
        placeholder="20:00",
        min_length=5,
        max_length=5,
        required=True
    )
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__()
        self.guild_id = guild_id
        self.config = config
        
        # Pre-fill with current time (check jobs structure first, fall back to legacy)
        scheduling = config.get("scheduling", {})
        jobs = scheduling.get("jobs", {})
        emoji_game = jobs.get("games", {}).get("emoji", {})
        emoji_schedule = normalize_schedule_read(emoji_game)
        current_time = emoji_schedule.get("time") or scheduling.get("auto_game", {}).get("time", "20:00")
        self.start_time.default = current_time

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Save start time."""
        try:
            time_str = self.start_time.value.strip()
            
            # Validate HH:MM format
            if not time_str or ":" not in time_str:
                await interaction.response.send_message(
                    "❌ Invalid format. Use HH:MM (e.g., 20:00)",
                    ephemeral=True
                )
                return
            
            parts = time_str.split(":")
            if len(parts) != 2:
                await interaction.response.send_message(
                    "❌ Invalid format. Use HH:MM (e.g., 20:00)",
                    ephemeral=True
                )
                return
            
            hour = int(parts[0])
            minute = int(parts[1])
            
            if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                await interaction.response.send_message(
                    "❌ Invalid time. Hour must be 0-23, minute must be 0-59.",
                    ephemeral=True
                )
                return
            
            # Format to ensure HH:MM format
            formatted_time = f"{hour:02d}:{minute:02d}"
            
            schedule = normalize_schedule_write("daily", time=formatted_time)
            success = set_guild_config(
                self.guild_id,
                {"scheduling": {"jobs": {"games": {"emoji": {"schedule": schedule}}}}},
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                await interaction.response.send_message(
                    f"✅ Auto-game start time set to **{formatted_time}** (guild timezone)",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("❌ Failed to save.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid time format. Use HH:MM (e.g., 20:00)",
                ephemeral=True
            )


class TwitchConfigModal(discord.ui.Modal, title="Twitch Notifications"):
    """Modal for configuring Twitch notifications."""
    
    enable_notifications = discord.ui.TextInput(
        label="Enable Notifications (yes/no)",
        placeholder="yes",
        required=True,
        default="yes"
    )
    
    channel_id = discord.ui.TextInput(
        label="Notification Channel ID (or leave blank)",
        placeholder="987654321",
        required=False
    )
    
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        await interaction.response.defer()
        
        # Parse enable input
        enable = self.enable_notifications.value.lower() in ("yes", "true", "1", "enable")
        
        # Parse channel ID if provided
        channel_id = None
        if self.channel_id.value.strip():
            try:
                channel_id = int(self.channel_id.value.strip())
                # Verify channel exists in guild
                guild = interaction.guild
                channel = guild.get_channel(channel_id) if guild else None
                if not channel:
                    embed = discord.Embed(
                        title="❌ Invalid Channel",
                        description=f"Channel {channel_id} not found in this server.",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
            except ValueError:
                embed = discord.Embed(
                    title="❌ Invalid Channel ID",
                    description="Please enter a valid channel ID.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
        
        # Update settings
        success = set_guild_config(
            self.guild_id,
            {"integrations": {"twitch_enabled": enable, "twitch_channel_id": channel_id}},
            audit_user_id=str(interaction.user.id)
        )
        
        if success:
            status = "✅ Enabled" if enable else "❌ Disabled"
            channel_info = f"Channel: <#{channel_id}>" if channel_id else "No channel set"
            
            embed = discord.Embed(
                title="✅ Twitch Notifications Updated",
                description=f"{status}\n{channel_info}",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="❌ Update Failed",
                description="Failed to update Twitch settings.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


# ════════════════════════════════════════════════════════════════════════════════
# LIMITS MODALS - Usage Limit Configuration
# ════════════════════════════════════════════════════════════════════════════════

class ConversationLimitsModal(discord.ui.Modal, title="Conversation Limits"):
    """Modal for configuring conversation limits.
    
    PRIMARY SETTING: max_turns_per_session
    This is the atomic, MongoDB-backed turn limiter that prevents race conditions.
    """
    
    max_turns = discord.ui.TextInput(
        label="Max Turns Per Session (1-100)",
        placeholder="10",
        min_length=1,
        max_length=3,
        required=True
    )
    
    cooldown = discord.ui.TextInput(
        label="Cooldown Between Sessions (seconds)",
        placeholder="30",
        min_length=1,
        max_length=5,
        required=False
    )
    
    session_timeout = discord.ui.TextInput(
        label="Session Timeout (seconds)",
        placeholder="60",
        min_length=1,
        max_length=5,
        required=False
    )
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__()
        self.guild_id = guild_id
        
        # Pre-fill current values
        conv_limits = config.get("usage_limits", {}).get("conversation", {})
        self.max_turns.default = str(conv_limits.get("max_turns_per_session", 10))
        self.cooldown.default = str(conv_limits.get("cooldown_seconds", 30))
        self.session_timeout.default = str(conv_limits.get("session_timeout_seconds", 60))
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        try:
            max_turns = int(self.max_turns.value)
            if not 1 <= max_turns <= 100:
                raise ValueError("Max turns must be between 1 and 100")
            
            updates = {
                "usage_limits.conversation.max_turns_per_session": max_turns
            }
            
            # Optional fields
            if self.cooldown.value:
                cooldown = int(self.cooldown.value)
                if cooldown < 0 or cooldown > 3600:
                    raise ValueError("Cooldown must be between 0 and 3600 seconds")
                updates["usage_limits.conversation.cooldown_seconds"] = cooldown
            
            if self.session_timeout.value:
                timeout = int(self.session_timeout.value)
                if timeout < 10 or timeout > 600:
                    raise ValueError("Session timeout must be between 10 and 600 seconds")
                updates["usage_limits.conversation.session_timeout_seconds"] = timeout
            
            # Save to database
            success = set_guild_config(
                self.guild_id,
                updates,
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Conversation Limits Updated",
                    description=(
                        f"Max Turns: **{max_turns}**\n"
                        f"Cooldown: **{self.cooldown.value or '30'}s**\n"
                        f"Session Timeout: **{self.session_timeout.value or '60'}s**\n\n"
                        f"ℹ️ This is the **atomic turn limit** (MongoDB-backed)."
                    ),
                    color=discord.Color.green()
                )
                
                # Refresh panel
                config = get_guild_config(self.guild_id)
                view = GuildConfigLimitsPanel(self.guild_id, config)
                panel_embed = view.build_embed()
                
                await interaction.response.edit_message(embed=panel_embed, view=view)
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                raise Exception("Failed to save configuration")
        
        except ValueError as e:
            embed = discord.Embed(
                title="❌ Invalid Input",
                description=str(e),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to update conversation limits: {e}")
            embed = discord.Embed(
                title="❌ Update Failed",
                description="Failed to save conversation limits. Please try again.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class DailyLimitsModal(discord.ui.Modal, title="Daily Limits"):
    """Modal for configuring daily usage limits."""
    
    max_messages = discord.ui.TextInput(
        label="Max Messages Per Day (1-1000)",
        placeholder="100",
        min_length=1,
        max_length=4,
        required=True
    )
    
    max_conversations = discord.ui.TextInput(
        label="Max Conversations Per Day (1-100)",
        placeholder="20",
        min_length=1,
        max_length=3,
        required=False
    )
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__()
        self.guild_id = guild_id
        
        daily_limits = config.get("usage_limits", {}).get("daily", {})
        self.max_messages.default = str(daily_limits.get("max_messages", 100))
        self.max_conversations.default = str(daily_limits.get("max_conversations", 20))
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        try:
            max_messages = int(self.max_messages.value)
            if not 1 <= max_messages <= 1000:
                raise ValueError("Max messages must be between 1 and 1000")
            
            updates = {
                "usage_limits.daily.max_messages": max_messages
            }
            
            if self.max_conversations.value:
                max_conversations = int(self.max_conversations.value)
                if not 1 <= max_conversations <= 100:
                    raise ValueError("Max conversations must be between 1 and 100")
                updates["usage_limits.daily.max_conversations"] = max_conversations
            
            success = set_guild_config(
                self.guild_id,
                updates,
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Daily Limits Updated",
                    description=(
                        f"Max Messages/Day: **{max_messages}**\n"
                        f"Max Conversations/Day: **{self.max_conversations.value or '20'}**"
                    ),
                    color=discord.Color.green()
                )
                
                config = get_guild_config(self.guild_id)
                view = GuildConfigLimitsPanel(self.guild_id, config)
                panel_embed = view.build_embed()
                
                await interaction.response.edit_message(embed=panel_embed, view=view)
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                raise Exception("Failed to save configuration")
        
        except ValueError as e:
            embed = discord.Embed(
                title="❌ Invalid Input",
                description=str(e),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to update daily limits: {e}")
            embed = discord.Embed(
                title="❌ Update Failed",
                description="Failed to save daily limits.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class BurstLimitsModal(discord.ui.Modal, title="Burst Protection"):
    """Modal for configuring burst protection limits."""
    
    max_messages = discord.ui.TextInput(
        label="Max Messages in Window (1-50)",
        placeholder="10",
        min_length=1,
        max_length=2,
        required=True
    )
    
    window_seconds = discord.ui.TextInput(
        label="Window Size (seconds, 10-300)",
        placeholder="60",
        min_length=2,
        max_length=3,
        required=True
    )
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__()
        self.guild_id = guild_id
        
        burst_limits = config.get("usage_limits", {}).get("burst", {})
        self.max_messages.default = str(burst_limits.get("max_messages", 10))
        self.window_seconds.default = str(burst_limits.get("window_seconds", 60))
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        try:
            max_messages = int(self.max_messages.value)
            if not 1 <= max_messages <= 50:
                raise ValueError("Max messages must be between 1 and 50")
            
            window_seconds = int(self.window_seconds.value)
            if not 10 <= window_seconds <= 300:
                raise ValueError("Window size must be between 10 and 300 seconds")
            
            updates = {
                "usage_limits.burst.max_messages": max_messages,
                "usage_limits.burst.window_seconds": window_seconds
            }
            
            success = set_guild_config(
                self.guild_id,
                updates,
                audit_user_id=str(interaction.user.id)
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Burst Protection Updated",
                    description=(
                        f"Max Messages: **{max_messages}**\n"
                        f"Window: **{window_seconds}s**\n\n"
                        f"ℹ️ Users sending more than {max_messages} messages "
                        f"in {window_seconds} seconds will be rate-limited."
                    ),
                    color=discord.Color.green()
                )
                
                config = get_guild_config(self.guild_id)
                view = GuildConfigLimitsPanel(self.guild_id, config)
                panel_embed = view.build_embed()
                
                await interaction.response.edit_message(embed=panel_embed, view=view)
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                raise Exception("Failed to save configuration")
        
        except ValueError as e:
            embed = discord.Embed(
                title="❌ Invalid Input",
                description=str(e),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to update burst limits: {e}")
            embed = discord.Embed(
                title="❌ Update Failed",
                description="Failed to save burst protection settings.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


# ════════════════════════════════════════════════════════════════════════════════
# RANDOM CONTENT PANEL - CRUD for guild-specific random messages
# ════════════════════════════════════════════════════════════════════════════════

class GuildConfigRandomContentPanel(discord.ui.View):
    """
    Random Content Management Panel - CRUD operations for random message pools.
    
    Features:
    - View custom messages + LLM prompts
    - Create new content entries
    - Edit/enable/disable existing entries
    - Delete content entries
    - View system content (read-only)
    """
    
    def __init__(self, guild_id: int, config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    def build_embed(self) -> discord.Embed:
        """Build random content overview embed."""
        from abby_core.database.collections.random_content_items import get_guild_content_pool
        
        # Get items from dedicated collection
        items = get_guild_content_pool(self.guild_id, include_system=False, enabled_only=True)
        
        custom_count = len([i for i in items if i.get("source_type") == "manual"])
        llm_count = len([i for i in items if i.get("source_type") == "llm"])
        
        # Get settings from guild_config
        random_content = self.config.get("random_content", {})
        settings = random_content.get("settings", {})
        
        embed = discord.Embed(
            title="🎲 Random Content Manager",
            description="Manage random messages, promotions, and facts for your guild.",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="📋 Custom Messages",
            value=f"Total: {custom_count}\n💬 Manual text entries (promos, facts)",
            inline=False
        )
        
        embed.add_field(
            name="🤖 LLM Prompts",
            value=f"Total: {llm_count}\n✨ Generated via AI",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Settings",
            value=f"Dedup: {format_boolean(settings.get('check_last_message', True))}\n"
                  f"Mix LLM: {format_boolean(settings.get('mix_llm_generated', True))}",
            inline=False
        )
        
        embed.add_field(
            name="🌍 System Content",
            value="• Abby canon lore\n• Meta tips & commands\n• Platform facts\n(Global, read-only)",
            inline=False
        )
        
        embed.add_field(
            name="📦 Storage",
            value="Content stored in dedicated database collection (not in guild_config)",
            inline=False
        )
        
        embed.set_footer(text="Click buttons below to manage content")
        return embed

    @discord.ui.button(label="View All", style=discord.ButtonStyle.secondary, emoji="👁️", row=0)
    async def button_view_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View all custom and system content."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        from abby_core.database.collections.random_content_items import get_guild_content_pool
        
        # Get items from dedicated collection
        items = get_guild_content_pool(self.guild_id, include_system=True, enabled_only=False)
        
        # Separate by type
        custom = [item for item in items if item.get("source_type") == "manual"]
        llm = [item for item in items if item.get("source_type") == "llm"]
        
        embed = discord.Embed(
            title="📚 Content Inventory",
            color=discord.Color.purple()
        )
        
        # Custom messages
        if custom:
            custom_str = "\n".join([
                f"• **{str(item.get('_id'))[:8]}...** ({item.get('category', 'uncategorized')}) "
                f"{'✅' if item.get('status') == 'active' else '❌'}"
                for item in custom[:10]  # Show first 10
            ])
            embed.add_field(
                name=f"📝 Custom Messages ({len(custom)} total)",
                value=custom_str or "None yet",
                inline=False
            )
        else:
            embed.add_field(
                name="📝 Custom Messages",
                value="No custom messages yet. Create one!",
                inline=False
            )
        
        # LLM prompts
        if llm:
            llm_str = "\n".join([
                f"• **{str(item.get('_id'))[:8]}...** ({item.get('category', 'uncategorized')}) "
                f"{'✅' if item.get('status') == 'active' else '❌'}"
                for item in llm[:10]  # Show first 10
            ])
            embed.add_field(
                name=f"🤖 LLM Prompts ({len(llm)} total)",
                value=llm_str or "None yet",
                inline=False
            )
        else:
            embed.add_field(
                name="🤖 LLM Prompts",
                value="No LLM prompts yet. Create one!",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Add Custom", style=discord.ButtonStyle.green, emoji="➕", row=0)
    async def button_add_custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a new custom message."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        modal = AddCustomMessageModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Add LLM Prompt", style=discord.ButtonStyle.green, emoji="✨", row=0)
    async def button_add_llm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a new LLM prompt."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        modal = AddLLMPromptModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Toggle Entry", style=discord.ButtonStyle.primary, emoji="🔄", row=1)
    async def button_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enable/disable a content entry."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        modal = ToggleContentModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Delete Entry", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def button_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete a content entry."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        modal = DeleteContentModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Settings", style=discord.ButtonStyle.primary, emoji="⚙️", row=1)
    async def button_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure random content settings."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        modal = RandomContentSettingsModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def button_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to Features."""
        if not is_guild_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        config = get_guild_config(self.guild_id)
        view = GuildConfigFeaturesPanel(self.guild_id, config)
        embed = view.build_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)


# ════════════════════════════════════════════════════════════════════════════════
# RANDOM CONTENT MODALS - CRUD Operations
# ════════════════════════════════════════════════════════════════════════════════

class AddCustomMessageModal(discord.ui.Modal, title="Add Custom Message"):
    """Modal to add a new custom message entry."""
    
    content = discord.ui.TextInput(
        label="Message Content",
        placeholder="Follow us on Facebook at [link]",
        min_length=5,
        max_length=250,
        style=discord.TextStyle.paragraph
    )
    
    category = discord.ui.TextInput(
        label="Category",
        placeholder="promotion, guild_fact, fun_fact, etc.",
        min_length=3,
        max_length=50
    )
    
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        """Save custom message to random_content_items collection."""
        try:
            from abby_core.database.collections.random_content_items import create_item
            
            item_id = create_item(
                guild_id=self.guild_id,
                source_type="manual",
                category=self.category.value,
                content_text=self.content.value,
                created_by=str(interaction.user.id),
                scope="guild"
            )
            
            if not item_id:
                raise Exception("Failed to create item in database")
            
            embed = discord.Embed(
                title="✅ Custom Message Added",
                description=f"**ID:** {item_id[:8]}...\n"
                            f"**Category:** {self.category.value}\n"
                            f"**Content:** {self.content.value[:100]}...",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"[Random Content] Error adding custom message: {e}")
            embed = discord.Embed(
                title="❌ Failed to Add Message",
                description=f"Error: {str(e)[:100]}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class AddLLMPromptModal(discord.ui.Modal, title="Add LLM Prompt"):
    """Modal to add a new LLM prompt entry."""
    
    prompt = discord.ui.TextInput(
        label="Prompt Description",
        placeholder="Generate an inspiring message about creativity...",
        min_length=10,
        max_length=300,
        style=discord.TextStyle.paragraph
    )
    
    category = discord.ui.TextInput(
        label="Category",
        placeholder="inspiration, encouragement, community, etc.",
        min_length=3,
        max_length=50
    )
    
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        """Save LLM prompt to random_content_items collection."""
        try:
            from abby_core.database.collections.random_content_items import create_item
            
            item_id = create_item(
                guild_id=self.guild_id,
                source_type="llm",
                category=self.category.value,
                content_prompt=self.prompt.value,
                created_by=str(interaction.user.id),
                scope="guild"
            )
            
            if not item_id:
                raise Exception("Failed to create item in database")
            
            embed = discord.Embed(
                title="✅ LLM Prompt Added",
                description=f"**ID:** {item_id[:8]}...\n"
                            f"**Category:** {self.category.value}\n"
                            f"**Prompt:** {self.prompt.value[:100]}...",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"[Random Content] Error adding LLM prompt: {e}")
            embed = discord.Embed(
                title="❌ Failed to Add Prompt",
                description=f"Error: {str(e)[:100]}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class ToggleContentModal(discord.ui.Modal, title="Toggle Content Entry"):
    """Modal to enable/disable a content entry."""
    
    entry_id = discord.ui.TextInput(
        label="Entry ID (copy from View All)",
        placeholder="[ObjectId from inventory]",
        min_length=3,
        max_length=100
    )
    
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        """Toggle entry enabled status."""
        try:
            from abby_core.database.collections.random_content_items import toggle_item, get_item_by_id
            
            item = get_item_by_id(self.entry_id.value)
            
            if not item:
                embed = discord.Embed(
                    title="❌ Entry Not Found",
                    description=f"Could not find entry: {self.entry_id.value}",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            success = toggle_item(self.entry_id.value)
            
            if not success:
                raise Exception("Failed to toggle item")
            
            new_status = "disabled" if item.get("status") == "active" else "active"
            pool_type = "LLM prompt" if item.get("source_type") == "llm" else "custom message"
            
            embed = discord.Embed(
                title="✅ Entry Toggled",
                description=f"**ID:** {self.entry_id.value[:8]}...\n"
                            f"**Type:** {pool_type}\n"
                            f"**Status:** {'✅ Enabled' if new_status == 'active' else '❌ Disabled'}",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"[Random Content] Error toggling entry: {e}")
            embed = discord.Embed(
                title="❌ Failed to Toggle",
                description=f"Error: {str(e)[:100]}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class DeleteContentModal(discord.ui.Modal, title="Delete Content Entry"):
    """Modal to delete a content entry."""
    
    entry_id = discord.ui.TextInput(
        label="Entry ID (copy from View All)",
        placeholder="[ObjectId from inventory]",
        min_length=3,
        max_length=100
    )
    
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        """Delete content entry."""
        try:
            from abby_core.database.collections.random_content_items import delete_item, get_item_by_id
            
            item = get_item_by_id(self.entry_id.value)
            
            if not item:
                embed = discord.Embed(
                    title="❌ Entry Not Found",
                    description=f"Could not find entry: {self.entry_id.value}",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            success = delete_item(self.entry_id.value)
            
            if not success:
                raise Exception("Failed to delete item")
            
            pool_type = "LLM prompt" if item.get("source_type") == "llm" else "custom message"
            
            embed = discord.Embed(
                title="✅ Entry Deleted",
                description=f"**ID:** {self.entry_id.value[:8]}...\n"
                            f"**Type:** {pool_type}",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"[Random Content] Error deleting entry: {e}")
            embed = discord.Embed(
                title="❌ Failed to Delete",
                description=f"Error: {str(e)[:100]}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class RandomContentSettingsModal(discord.ui.Modal, title="Random Content Settings"):
    """Modal to configure random content settings in guild_config."""
    
    check_dedup = discord.ui.TextInput(
        label="Check Last Message (true/false)",
        placeholder="true",
        min_length=4,
        max_length=5
    )
    
    mix_llm = discord.ui.TextInput(
        label="Mix LLM Generated (true/false)",
        placeholder="true",
        min_length=4,
        max_length=5
    )
    
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        """Update random content settings in guild config."""
        try:
            # Parse boolean inputs
            check_dedup = self.check_dedup.value.lower() in ("true", "1", "yes")
            mix_llm = self.mix_llm.value.lower() in ("true", "1", "yes")
            
            # Update only the settings part of guild_config (not content bodies)
            set_guild_config(
                self.guild_id,
                {
                    "random_content": {
                        "settings": {
                            "enabled": True,
                            "check_last_message": check_dedup,
                            "mix_llm_generated": mix_llm,
                            "llm_enrichment": True
                        }
                    }
                },
                audit_user_id=str(interaction.user.id)
            )
            
            embed = discord.Embed(
                title="✅ Settings Updated",
                description=f"**Dedup Check:** {format_boolean(check_dedup)}\n"
                            f"**Mix LLM:** {format_boolean(mix_llm)}\n\n"
                            f"_Content is now stored in dedicated database._",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"[Random Content] Error updating settings: {e}")
            embed = discord.Embed(
                title="❌ Failed to Update Settings",
                description=f"Error: {str(e)[:100]}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


# ════════════════════════════════════════════════════════════════════════════════
# COG SETUP
# ════════════════════════════════════════════════════════════════════════════════

async def setup(bot: commands.Bot):
    """Load the cog."""
    await bot.add_cog(GuildConfig(bot))

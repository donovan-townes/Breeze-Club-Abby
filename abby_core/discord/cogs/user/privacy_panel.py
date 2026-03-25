"""
/privacy - User Privacy & Data Management Hub

Consolidates:
- Memory management (view, forget, export, opt-out, terms)
- Conversation management (view, clear, export)
- Data control in one unified interface

Follows the button-based navigation pattern from /stats and /bank.
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from typing import Optional, Any
import json
from io import BytesIO

from abby_core.services.user_service import get_user_service
from abby_core.database.collections.chat_sessions import get_recent_sessions, count_sessions
from abby_core.services.memory_service_factory import create_discord_memory_service
memory: Any = None
logging: Any = None

try:  # noqa: SIM105 - we intentionally catch ImportError to allow partial environments
    from tdos_intelligence.observability import logging as _logging  # type: ignore[attr-defined]
    import tdos_intelligence.memory as memory  # type: ignore[attr-defined]
    logging = _logging
except ImportError:
    pass

def _missing_dep(name: str):
    def _raiser(*args, **kwargs):
        raise RuntimeError(f"{name} not available")
    return _raiser

if create_discord_memory_service is None:
    create_discord_memory_service = _missing_dep("Memory service")

logger = logging.getLogger(__name__) if logging else None


# ════════════════════════════════════════════════════════════════════════════════
# MODAL CLASSES
# ════════════════════════════════════════════════════════════════════════════════

class ForgetMemoryModal(discord.ui.Modal, title="Forget a Memory"):
    """Modal for deleting a specific memory."""
    memory_text = discord.ui.TextInput(
        label="Memory to forget (exact text)",
        placeholder="Enter the exact memory text to delete...",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    
    def __init__(self, cog: "PrivacyPanel"):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            guild_id = interaction.guild.id if interaction.guild else None
            memory_to_forget = str(self.memory_text).strip()
            
            # Use UserService to forget memory
            user_service = get_user_service()
            success, error = user_service.forget_memory(user_id, memory_to_forget, guild_id)
            
            if success:
                # Invalidate cache if memory module is available
                if memory:
                    memory.invalidate_cache(user_id, str(guild_id) if guild_id else None, source_id="discord")
                
                await interaction.followup.send(
                    f"✅ Forgot: \"{memory_to_forget}\"",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ {error or 'Memory not found. Check exact text and try again.'}",
                    ephemeral=True
                )
        
        except Exception as e:
            if logger:
                logger.error(f"[🔐] Failed to forget memory: {e}")
            await interaction.followup.send(
                "❌ Failed to forget memory. Please try again later.",
                ephemeral=True
            )


# ════════════════════════════════════════════════════════════════════════════════
# VIEW CLASSES
# ════════════════════════════════════════════════════════════════════════════════

class PrivacyOverviewView(discord.ui.View):
    """Navigation panel for privacy overview."""
    
    def __init__(self, cog: "PrivacyPanel", owner_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.owner_id = owner_id
    
    async def _switch_tab(self, interaction: discord.Interaction, tab: str):
        if tab == "overview":
            embed = await self.cog.build_overview_embed(interaction)
            view = PrivacyOverviewView(self.cog, self.owner_id)
        elif tab == "memory":
            embed = await self.cog.build_memory_embed(interaction)
            view = PrivacyMemoryView(self.cog, self.owner_id)
        elif tab == "conversations":
            embed = await self.cog.build_conversations_embed(interaction)
            view = PrivacyConversationsView(self.cog, self.owner_id)
        elif tab == "data_export":
            embed = await self.cog.build_data_export_embed(interaction)
            view = PrivacyDataExportView(self.cog, self.owner_id)
        else:
            embed = await self.cog.build_overview_embed(interaction)
            view = PrivacyOverviewView(self.cog, self.owner_id)
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Overview", style=discord.ButtonStyle.primary, emoji="🏠", row=0)
    async def button_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "overview")
    
    @discord.ui.button(label="Memory", style=discord.ButtonStyle.secondary, emoji="🧠", row=0)
    async def button_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "memory")
    
    @discord.ui.button(label="Conversations", style=discord.ButtonStyle.secondary, emoji="💬", row=0)
    async def button_conversations(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "conversations")
    
    @discord.ui.button(label="Data Export", style=discord.ButtonStyle.secondary, emoji="📥", row=1)
    async def button_data_export(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "data_export")
    
    @discord.ui.button(label="Toggle Opt-Out", style=discord.ButtonStyle.secondary, emoji="🔒", row=1)
    async def button_toggle_optout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.toggle_optout(interaction)


class PrivacyMemoryView(discord.ui.View):
    """Memory management panel with forget action."""
    
    def __init__(self, cog: "PrivacyPanel", owner_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.owner_id = owner_id
    
    async def _switch_tab(self, interaction: discord.Interaction, tab: str):
        if tab == "overview":
            embed = await self.cog.build_overview_embed(interaction)
            view = PrivacyOverviewView(self.cog, self.owner_id)
        elif tab == "memory":
            embed = await self.cog.build_memory_embed(interaction)
            view = PrivacyMemoryView(self.cog, self.owner_id)
        elif tab == "conversations":
            embed = await self.cog.build_conversations_embed(interaction)
            view = PrivacyConversationsView(self.cog, self.owner_id)
        elif tab == "data_export":
            embed = await self.cog.build_data_export_embed(interaction)
            view = PrivacyDataExportView(self.cog, self.owner_id)
        else:
            embed = await self.cog.build_overview_embed(interaction)
            view = PrivacyOverviewView(self.cog, self.owner_id)
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Overview", style=discord.ButtonStyle.primary, emoji="🏠", row=0)
    async def button_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "overview")
    
    @discord.ui.button(label="Memory", style=discord.ButtonStyle.secondary, emoji="🧠", row=0)
    async def button_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "memory")
    
    @discord.ui.button(label="Conversations", style=discord.ButtonStyle.secondary, emoji="💬", row=0)
    async def button_conversations(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "conversations")
    
    @discord.ui.button(label="Data Export", style=discord.ButtonStyle.secondary, emoji="📥", row=1)
    async def button_data_export(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "data_export")
    
    @discord.ui.button(label="Forget Memory", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def button_forget_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ForgetMemoryModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Toggle Opt-Out", style=discord.ButtonStyle.secondary, emoji="🔒", row=1)
    async def button_toggle_optout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.toggle_optout(interaction)


class PrivacyConversationsView(discord.ui.View):
    """Conversation management panel with clear action."""
    
    def __init__(self, cog: "PrivacyPanel", owner_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.owner_id = owner_id
    
    async def _switch_tab(self, interaction: discord.Interaction, tab: str):
        if tab == "overview":
            embed = await self.cog.build_overview_embed(interaction)
            view = PrivacyOverviewView(self.cog, self.owner_id)
        elif tab == "memory":
            embed = await self.cog.build_memory_embed(interaction)
            view = PrivacyMemoryView(self.cog, self.owner_id)
        elif tab == "conversations":
            embed = await self.cog.build_conversations_embed(interaction)
            view = PrivacyConversationsView(self.cog, self.owner_id)
        elif tab == "data_export":
            embed = await self.cog.build_data_export_embed(interaction)
            view = PrivacyDataExportView(self.cog, self.owner_id)
        else:
            embed = await self.cog.build_overview_embed(interaction)
            view = PrivacyOverviewView(self.cog, self.owner_id)
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Overview", style=discord.ButtonStyle.primary, emoji="🏠", row=0)
    async def button_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "overview")
    
    @discord.ui.button(label="Memory", style=discord.ButtonStyle.secondary, emoji="🧠", row=0)
    async def button_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "memory")
    
    @discord.ui.button(label="Conversations", style=discord.ButtonStyle.secondary, emoji="💬", row=0)
    async def button_conversations(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "conversations")
    
    @discord.ui.button(label="Data Export", style=discord.ButtonStyle.secondary, emoji="📥", row=1)
    async def button_data_export(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "data_export")
    
    @discord.ui.button(label="Clear Conversations", style=discord.ButtonStyle.danger, emoji="🧹", row=1)
    async def button_clear_conversations(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.clear_conversations(interaction)
    
    @discord.ui.button(label="Toggle Opt-Out", style=discord.ButtonStyle.secondary, emoji="🔒", row=1)
    async def button_toggle_optout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.toggle_optout(interaction)


class PrivacyDataExportView(discord.ui.View):
    """Data export panel with export buttons."""
    
    def __init__(self, cog: "PrivacyPanel", owner_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.owner_id = owner_id
    
    async def _switch_tab(self, interaction: discord.Interaction, tab: str):
        if tab == "overview":
            embed = await self.cog.build_overview_embed(interaction)
            view = PrivacyOverviewView(self.cog, self.owner_id)
        elif tab == "memory":
            embed = await self.cog.build_memory_embed(interaction)
            view = PrivacyMemoryView(self.cog, self.owner_id)
        elif tab == "conversations":
            embed = await self.cog.build_conversations_embed(interaction)
            view = PrivacyConversationsView(self.cog, self.owner_id)
        elif tab == "data_export":
            embed = await self.cog.build_data_export_embed(interaction)
            view = PrivacyDataExportView(self.cog, self.owner_id)
        else:
            embed = await self.cog.build_overview_embed(interaction)
            view = PrivacyOverviewView(self.cog, self.owner_id)
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Overview", style=discord.ButtonStyle.primary, emoji="🏠", row=0)
    async def button_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "overview")
    
    @discord.ui.button(label="Memory", style=discord.ButtonStyle.secondary, emoji="🧠", row=0)
    async def button_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "memory")
    
    @discord.ui.button(label="Conversations", style=discord.ButtonStyle.secondary, emoji="💬", row=0)
    async def button_conversations(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "conversations")
    
    @discord.ui.button(label="Data Export", style=discord.ButtonStyle.secondary, emoji="📥", row=1)
    async def button_data_export(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "data_export")
    
    @discord.ui.button(label="Export Memory", style=discord.ButtonStyle.primary, emoji="🧠", row=1)
    async def button_export_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.export_memory_data(interaction)
    
    @discord.ui.button(label="Export Conversations", style=discord.ButtonStyle.primary, emoji="💬", row=2)
    async def button_export_conversations(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.export_conversation_data(interaction)
    
    @discord.ui.button(label="Export All Data", style=discord.ButtonStyle.success, emoji="📦", row=2)
    async def button_export_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.export_all_data(interaction)
    
    @discord.ui.button(label="Toggle Opt-Out", style=discord.ButtonStyle.secondary, emoji="🔒", row=2)
    async def button_toggle_optout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.toggle_optout(interaction)


# ════════════════════════════════════════════════════════════════════════════════
# MAIN COG
# ════════════════════════════════════════════════════════════════════════════════

class PrivacyPanel(commands.Cog):
    """User privacy and data management hub."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_service = get_user_service()
        
        # Initialize memory service
        try:
            self.memory_service = create_discord_memory_service(logger_override=logger)
        except Exception as e:
            if logger:
                logger.error(f"[🔐] Failed to initialize memory service: {e}")
            self.memory_service = None
        
        if logger:
            logger.debug("[🔐] Privacy Panel loaded")
    
    @app_commands.command(name="privacy", description="Manage your privacy settings and personal data")
    async def privacy(self, interaction: discord.Interaction):
        """Single entry point with button navigation."""
        embed = await self.build_overview_embed(interaction)
        view = PrivacyOverviewView(self, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def build_overview_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Build the privacy overview embed."""
        user_id = str(interaction.user.id)
        guild_id = interaction.guild.id if interaction.guild else None
        
        # Check opt-out status
        opted_out, _ = self.user_service.get_optout_status(user_id, guild_id)
        
        # Get memory stats
        memory_stats, _ = self.user_service.get_memory_stats(user_id, guild_id)
        memory_count = memory_stats.get("memory_count", 0) if memory_stats else 0
        
        # Get conversation stats
        conv_stats, _ = self.user_service.get_conversation_stats(user_id, guild_id)
        conversation_count = conv_stats.get("session_count", 0) if conv_stats else 0
        
        embed = discord.Embed(
            title="🔐 Privacy Center",
            description="Manage your data and privacy settings with Abby",
            color=discord.Color.blue()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=getattr(interaction.user.display_avatar, "url", None)
        )
        
        # Status overview
        status_emoji = "❌" if opted_out else "✅"
        embed.add_field(
            name="Privacy Status",
            value=f"{status_emoji} Memory Collection: {'Disabled' if opted_out else 'Enabled'}",
            inline=False
        )
        
        embed.add_field(
            name="📊 Your Data",
            value=f"🧠 **Memories:** {memory_count} stored\n💬 **Conversations:** {conversation_count} sessions",
            inline=False
        )
        
        embed.add_field(
            name="🎛️ Quick Actions",
            value=(
                "• **Memory** - View and manage your memories\n"
                "• **Conversations** - View conversation history\n"
                "• **Data Export** - Download all your data\n"
                "• **Forget Memory** - Delete specific memories\n"
                "• **Clear Conversations** - Delete conversation history\n"
                "• **Toggle Opt-Out** - Enable/disable memory collection"
            ),
            inline=False
        )
        
        embed.set_footer(text="All data is encrypted at rest • You have full control")
        return embed
    
    async def build_memory_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Build the memory management embed."""
        user_id = str(interaction.user.id)
        guild_id = interaction.guild.id if interaction.guild else None
        
        embed = discord.Embed(
            title="🧠 Memory Management",
            color=discord.Color.purple()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=getattr(interaction.user.display_avatar, "url", None)
        )
        
        # Check opt-out status
        opted_out, _ = self.user_service.get_optout_status(user_id, guild_id)
        
        if opted_out:
            embed.description = "❌ You've opted out of memory collection. No memories are stored."
            embed.set_footer(text="Use 'Toggle Opt-Out' to enable memory collection")
            return embed
        
        if not self.memory_service:
            embed.description = "❌ Memory system temporarily unavailable."
            return embed
        
        try:
            profile = self.memory_service.get_profile(str(user_id), str(guild_id) if guild_id else None)
            if not profile:
                embed.description = "📭 No memories found. Chat with me to start building memories!"
                return embed
            
            facts = profile.get("creative_profile", {}).get("memorable_facts", [])
            if not facts:
                embed.description = "📭 No memories found. Chat with me to start building memories!"
                return embed
            
            embed.description = f"Total memories: {len(facts)}"
            
            # Show first 5 memories
            for i, fact in enumerate(facts[:5], 1):
                confidence = fact.get("confidence", 0)
                confidence_bar = "█" * int(confidence * 10) + "░" * (10 - int(confidence * 10))
                embed.add_field(
                    name=f"Memory {i} [{confidence_bar}]",
                    value=fact.get("text", "Unknown"),
                    inline=False
                )
            
            if len(facts) > 5:
                embed.add_field(
                    name="📊",
                    value=f"...and {len(facts) - 5} more memories",
                    inline=False
                )
            
            embed.set_footer(text="Use 'Forget Memory' button to remove specific memories")
        
        except Exception as e:
            if logger:
                logger.error(f"[🔐] Failed to build memory embed: {e}")
            embed.description = "❌ Failed to load memories. Please try again later."
        
        return embed
    
    async def build_conversations_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Build the conversations management embed."""
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id) if interaction.guild else None
        
        embed = discord.Embed(
            title="💬 Conversation History",
            color=discord.Color.green()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=getattr(interaction.user.display_avatar, "url", None)
        )
        
        try:
            sessions = get_recent_sessions(user_id, guild_id, limit=10)
            total_sessions = count_sessions(user_id, guild_id)

            if not sessions:
                embed.description = "📭 No conversation history found."
                return embed

            embed.description = f"Total sessions: {total_sessions}"

            for i, session in enumerate(sessions[:5], 1):
                created_at = session.get("created_at", datetime.utcnow())
                # interactions array contains user+assistant exchanges
                message_count = len(session.get("interactions", []))

                time_str = created_at.strftime("%Y-%m-%d %H:%M") if hasattr(created_at, "strftime") else "unknown"

                embed.add_field(
                    name=f"Session {i}",
                    value=f"📅 {time_str}\n💬 {message_count} interactions",
                    inline=True
                )

            if len(sessions) > 5:
                embed.add_field(
                    name="📊",
                    value=f"...and {len(sessions) - 5} more sessions",
                    inline=False
                )

            embed.set_footer(text="Use 'Clear Conversations' button to delete all sessions")

        except Exception as e:
            if logger:
                logger.error(f"[🔐] Failed to build conversations embed: {e}")
            embed.description = "❌ Failed to load conversations. Please try again later."

        return embed
    
    async def build_data_export_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Build the data export embed."""
        embed = discord.Embed(
            title="📥 Data Export",
            description="Export all your data in machine-readable format",
            color=discord.Color.gold()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=getattr(interaction.user.display_avatar, "url", None)
        )
        
        embed.add_field(
            name="Available Exports",
            value=(
                "🧠 **Memory Export** - All stored memories with metadata\n"
                "💬 **Conversation Export** - All conversation sessions\n"
                "📦 **Full Export** - Combined export of all data"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Export Format",
            value="JSON format with timestamps and metadata",
            inline=False
        )
        
        embed.add_field(
            name="Privacy Notice",
            value="Exports are generated on-demand and sent only to you. Files are never stored on our servers.",
            inline=False
        )
        
        embed.set_footer(text="Use the Export buttons below to download your data")
        return embed
    
    async def export_memory_data(self, interaction: discord.Interaction):
        """Export memory data as JSON."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            guild_id = interaction.guild.id if interaction.guild else None
            
            export_data, error = self.user_service.export_memory_data(user_id, guild_id, self.memory_service)
            
            if error:
                await interaction.followup.send(f"❌ {error}", ephemeral=True)
                return
            
            json_str = json.dumps(export_data, indent=2)
            json_bytes = BytesIO(json_str.encode('utf-8'))
            
            file = discord.File(json_bytes, filename=f"abby_memories_{user_id}.json")
            await interaction.followup.send(
                content="📥 Here's your memory data:",
                file=file,
                ephemeral=True
            )
        
        except Exception as e:
            if logger:
                logger.error(f"[🔐] Failed to export memory: {e}")
            await interaction.followup.send("❌ Failed to export memories. Please try again later.", ephemeral=True)
    
    async def export_conversation_data(self, interaction: discord.Interaction):
        """Export conversation data as JSON."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            guild_id = interaction.guild.id if interaction.guild else None
            
            export_data, error = self.user_service.export_conversation_data(user_id, guild_id)
            
            if error:
                await interaction.followup.send(f"❌ {error}", ephemeral=True)
                return
            
            json_str = json.dumps(export_data, indent=2)
            json_bytes = BytesIO(json_str.encode('utf-8'))
            
            file = discord.File(json_bytes, filename=f"abby_conversations_{user_id}.json")
            await interaction.followup.send(
                content="📥 Here's your conversation data:",
                file=file,
                ephemeral=True
            )
        
        except Exception as e:
            if logger:
                logger.error(f"[🔐] Failed to export conversations: {e}")
            await interaction.followup.send("❌ Failed to export conversations. Please try again later.", ephemeral=True)
    
    async def export_all_data(self, interaction: discord.Interaction):
        """Export all user data as combined JSON."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            guild_id = interaction.guild.id if interaction.guild else None
            
            export_data, error = self.user_service.export_all_data(user_id, guild_id, self.memory_service)
            
            if error:
                await interaction.followup.send(f"❌ {error}", ephemeral=True)
                return
            
            json_str = json.dumps(export_data, indent=2)
            json_bytes = BytesIO(json_str.encode('utf-8'))
            
            file = discord.File(json_bytes, filename=f"abby_full_export_{user_id}.json")
            await interaction.followup.send(
                content="📥 Here's your complete data export:",
                file=file,
                ephemeral=True
            )
        
        except Exception as e:
            if logger:
                logger.error(f"[🔐] Failed to export all data: {e}")
            await interaction.followup.send("❌ Failed to export data. Please try again later.", ephemeral=True)
    
    async def toggle_optout(self, interaction: discord.Interaction):
        """Toggle memory collection opt-out status."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            guild_id = interaction.guild.id if interaction.guild else None
            
            new_status, error = self.user_service.toggle_optout(user_id, guild_id)
            
            if error:
                await interaction.followup.send(f"❌ {error}", ephemeral=True)
                return
            
            if new_status:
                await interaction.followup.send(
                    "✅ You've opted out of memory collection. No new memories will be stored.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "✅ You've opted back in to memory collection.",
                    ephemeral=True
                )
            
            if logger:
                logger.info(f"[🔐] User {user_id} opted out: {new_status}")
        
        except Exception as e:
            if logger:
                logger.error(f"[🔐] Failed to toggle opt-out: {e}")
            await interaction.followup.send(
                "❌ Failed to update setting. Please try again later.",
                ephemeral=True
            )
    
    async def clear_conversations(self, interaction: discord.Interaction):
        """Clear all conversation sessions for this user."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            guild_id = interaction.guild.id if interaction.guild else None
            
            deleted_count, error = self.user_service.clear_conversations(user_id, guild_id)
            
            if error:
                await interaction.followup.send(f"❌ {error}", ephemeral=True)
                return
            
            await interaction.followup.send(
                f"✅ Deleted {deleted_count} conversation session(s).",
                ephemeral=True
            )
        
        except Exception as e:
            if logger:
                logger.error(f"[🔐] Failed to clear conversations: {e}")
            await interaction.followup.send(
                "❌ Failed to clear conversations. Please try again later.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Load the privacy panel cog."""
    await bot.add_cog(PrivacyPanel(bot))
                
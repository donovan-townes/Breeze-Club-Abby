"""
Operator Commands for System State Management (Seasons, Canon Events)

These commands allow operators to:
- View active season and canon state
- View season schedule
- Manually trigger season transitions (if needed)
- View historical season information

Integration point: Can be added to /operator economy subcommand group.
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from typing import Optional

from abby_core.observability.logging import logging
from abby_core.system.system_state import (
    get_active_state,
    get_state_by_id,
    list_all_states,
    activate_state,
    get_season_for_date
)

logger = logging.getLogger(__name__)


class SystemStateOperatorView(discord.ui.View):
    """Interactive view for system state management."""
    
    def __init__(self, timeout: int = 180):
        super().__init__(timeout=timeout)
    
    @discord.ui.button(label="View Season Schedule", style=discord.ButtonStyle.primary, emoji="📅")
    async def view_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View all defined seasons."""
        await interaction.response.defer(ephemeral=True)
        
        seasons = list_all_states("season")
        if not seasons:
            await interaction.followup.send("❌ No seasons found in database.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📅 Season Schedule 2026",
            description="Predefined astronomical seasons for the platform",
            color=discord.Color.blue()
        )
        
        for season in sorted(seasons, key=lambda s: s.get("start_at", datetime.min)):
            state_id = season.get("state_id", "unknown")
            label = season.get("label", "Unknown")
            start = season.get("start_at")
            end = season.get("end_at")
            active = season.get("active", False)
            
            start_str = start.strftime("%b %d") if isinstance(start, datetime) else "N/A"
            end_str = end.strftime("%b %d") if isinstance(end, datetime) else "N/A"
            
            status = "🟢 ACTIVE" if active else "⚪ Inactive"
            
            embed.add_field(
                name=f"{label} {status}",
                value=f"`{state_id}`\n{start_str} – {end_str}",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Force Season Transition", style=discord.ButtonStyle.danger, emoji="⏱️")
    async def force_transition(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Force an immediate season transition (admin only)."""
        await interaction.response.send_modal(ForceSeasonModal(interaction.user.id))


class ForceSeasonModal(discord.ui.Modal):
    """Modal to confirm and execute season transition."""
    
    season_id_input = discord.ui.TextInput(
        label="Season ID to Activate",
        placeholder="e.g., winter-2026, spring-2026, summer-2026, fall-2026",
        required=True,
        max_length=30
    )
    
    def __init__(self, operator_id: int):
        super().__init__(title="Force Season Transition")
        self.operator_id = operator_id
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            season_id = str(self.season_id_input).strip()
            
            # Validate season exists
            season = get_state_by_id(season_id)
            if not season:
                await interaction.followup.send(
                    f"❌ Season not found: `{season_id}`\n"
                    "Valid seasons: winter-2026, spring-2026, summer-2026, fall-2026",
                    ephemeral=True
                )
                return
            
            # Get current active season
            active = get_active_state("season")
            if active and active.get("state_id") == season_id:
                await interaction.followup.send(
                    f"ℹ️ Season `{season_id}` is already active.",
                    ephemeral=True
                )
                return
            
            # Activate the new season
            if activate_state(season_id):
                label = season.get("label", "Unknown")
                start = season.get("start_at")
                end = season.get("end_at")
                start_str = start.strftime("%b %d, %Y") if isinstance(start, datetime) else "N/A"
                end_str = end.strftime("%b %d, %Y") if isinstance(end, datetime) else "N/A"
                
                embed = discord.Embed(
                    title="✅ Season Transitioned",
                    description=f"Platform is now in: **{label}**",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Period",
                    value=f"{start_str} – {end_str}",
                    inline=False
                )
                embed.add_field(
                    name="State ID",
                    value=f"`{season_id}`",
                    inline=False
                )
                embed.add_field(
                    name="⚠️ Note",
                    value="Seasonal XP resets will occur at the next scheduled season_rollover job execution.",
                    inline=False
                )
                embed.set_footer(text=f"Operator: {interaction.user.mention} | {datetime.utcnow().isoformat()}")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                if logger:
                    logger.info(f"[🌍] Operator {interaction.user.id} manually transitioned to season: {season_id}")
            else:
                await interaction.followup.send(
                    f"❌ Failed to activate season `{season_id}`. Check logs.",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"[🌍] Season transition failed: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error during season transition: {e}",
                ephemeral=True
            )


async def view_system_state(interaction: discord.Interaction):
    """View current system state (can be called as a handler or command)."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Get active season
        active_season = get_active_state("season")
        
        if not active_season:
            await interaction.followup.send(
                "⚠️ No active season found. Database may need initialization.",
                ephemeral=True
            )
            return
        
        state_id = active_season.get("state_id", "unknown")
        label = active_season.get("label", "Unknown")
        canon_ref = active_season.get("canon_ref", "N/A")
        start = active_season.get("start_at")
        end = active_season.get("end_at")
        activated_at = active_season.get("activated_at")
        
        embed = discord.Embed(
            title="🌍 Current System State",
            description="Platform-wide canonical state",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Active Season",
            value=f"**{label}**\n`{state_id}`",
            inline=False
        )
        
        if isinstance(start, datetime) and isinstance(end, datetime):
            start_str = start.strftime("%b %d, %Y")
            end_str = end.strftime("%b %d, %Y")
            embed.add_field(
                name="Valid Period",
                value=f"{start_str} – {end_str}",
                inline=False
            )
        
        embed.add_field(
            name="Canon Reference",
            value=f"`{canon_ref}`",
            inline=False
        )
        
        if isinstance(activated_at, datetime):
            activated_str = activated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            embed.add_field(
                name="Activated At",
                value=activated_str,
                inline=False
            )
        
        effects = active_season.get("effects", {})
        effects_list = [k for k, v in effects.items() if v]
        if effects_list:
            embed.add_field(
                name="Active Effects",
                value=", ".join(effects_list),
                inline=False
            )
        
        embed.add_field(
            name="Seasonal XP Reset",
            value="✅ Enabled\nXP resets each season. Levels are permanent.",
            inline=False
        )
        
        embed.set_footer(text="Use buttons below to view schedule or manage seasons")
        
        view = SystemStateOperatorView()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    except Exception as e:
        logger.error(f"[🌍] Failed to view system state: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ Error retrieving system state: {e}",
            ephemeral=True
        )


# Standalone helper to query season at a specific date
async def inspect_season_for_date(interaction: discord.Interaction, date_str: Optional[str] = None):
    """Inspect which season covers a specific date (for historical lookups)."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        if date_str:
            try:
                target_date = datetime.fromisoformat(date_str)
            except ValueError:
                await interaction.followup.send(
                    f"❌ Invalid date format. Use ISO format: YYYY-MM-DD",
                    ephemeral=True
                )
                return
        else:
            target_date = datetime.utcnow()
        
        season = get_season_for_date(target_date)
        
        if not season:
            await interaction.followup.send(
                f"❌ No season found for date: {target_date.date()}",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📅 Season Lookup",
            description=f"Season covering {target_date.date()}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Season",
            value=season.get("label", "Unknown"),
            inline=False
        )
        
        embed.add_field(
            name="State ID",
            value=f"`{season.get('state_id', 'unknown')}`",
            inline=False
        )
        
        start = season.get("start_at")
        end = season.get("end_at")
        if isinstance(start, datetime) and isinstance(end, datetime):
            start_str = start.strftime("%b %d, %Y")
            end_str = end.strftime("%b %d, %Y")
            embed.add_field(
                name="Valid Period",
                value=f"{start_str} – {end_str}",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    except Exception as e:
        logger.error(f"[🌍] Failed to lookup season: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ Error: {e}",
            ephemeral=True
        )

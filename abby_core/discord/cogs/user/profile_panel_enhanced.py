"""
Enhanced /profile - Universal User Profile Panel via Users Collection

Displays and manages:
- Universal user profile from Users collection
- Artist profile (stage name, bio, website)
- Social accounts (YouTube, Twitter, Twitch, Instagram, TikTok)
- Creative accounts (Spotify, Apple Music, SoundCloud, Bandcamp)
- Collaborations with other artists
- Account linkages

Routes through Users collection module (not discord_profiles directly).
This is the E2E test for the new universal user profile architecture.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from abby_core.database.collections.users import (
    ensure_user_from_discord,
    ensure_user_guild_entry,
    get_user
)
from abby_core.services.user_service import get_user_service
from abby_core.database.mongodb import get_database
from abby_core.discord.cogs.user.release_manager import ReleaseManagerView
from datetime import datetime
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


class UniversalProfilePanel(commands.Cog):
    """Universal user profile with social/creative account integration."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_service = get_user_service()
        logger.debug("[👤] Universal Profile Panel loaded")
    
    @app_commands.command(
        name="profile",
        description="View your universal profile with social & creative accounts"
    )
    async def profile_panel(self, interaction: discord.Interaction):
        """Display universal user profile via Users collection."""
        user_id = str(interaction.user.id)  # Use string for consistency with memory service
        guild_id = str(interaction.guild.id) if interaction.guild else None
        
        # Ensure user profile through canonical database function
        # This enforces universal schema automatically
        ensure_user_from_discord(interaction.user, interaction.guild)
        
        # Add/update current guild if in a guild
        if guild_id and interaction.guild:
            member = interaction.guild.get_member(interaction.user.id)
            nickname = member.nick if member else None
            joined_at = member.joined_at if member else None
            ensure_user_guild_entry(
                user_id=user_id,
                guild_id=guild_id,
                guild_name=interaction.guild.name,
                nickname=nickname,
                joined_at=joined_at,
                last_seen=datetime.utcnow()
            )

        # Get profile via collection helper
        user_profile = get_user(user_id)
        
        # Ensure user_profile is a dict (fallback to empty dict if None)
        if user_profile is None:
            user_profile = {}
        
        # Get Discord info for display (use Discord display_name, never guild nickname)
        discord_info = user_profile.get("discord", {})
        
        # Always use Discord display name, never guild nickname
        # Guild nickname should only appear in guild-specific contexts
        display_name = discord_info.get('display_name') or interaction.user.display_name
        
        # Create main embed
        embed = discord.Embed(
            title=f"👤 {display_name}'s Universal Profile",
            description="Manage your social, creative, and artist profiles",
            color=discord.Color.blurple()
        )
        
        embed.set_thumbnail(url=discord_info.get("avatar_url", interaction.user.display_avatar.url))
        
        # === Discord Account Section ===
        embed.add_field(
            name="🎮 Discord Account",
            value=f"{interaction.user.mention}\nID: `{user_id}`\nUsername: `{discord_info.get('username', 'N/A')}`",
            inline=False
        )
        
        # === Artist Profile Section ===
        artist_profile = user_profile.get("artist_profile", {})
        is_artist = artist_profile.get("is_artist", False)
        
        if is_artist:
            stage_name = artist_profile.get("stage_name", "Unknown")
            bio = artist_profile.get("bio", "No bio yet")
            website = artist_profile.get("website", "No website")
            
            embed.add_field(
                name="🎨 Artist Profile",
                value=f"**{stage_name}**\n{bio}\n🌐 {website}",
                inline=False
            )
        else:
            embed.add_field(
                name="🎨 Artist Profile",
                value="Not enabled - Use `/artist profile` to set up",
                inline=False
            )
        
        # === Social Accounts Section ===
        social_accounts = user_profile.get("social_accounts", [])
        if social_accounts:
            socials_text = "\n".join([
                f"• **{acc['platform'].title()}**: [{acc['handle']}]({acc['url']})"
                for acc in social_accounts[:5]
            ])
            if len(social_accounts) > 5:
                socials_text += f"\n... and {len(social_accounts) - 5} more"
            
            embed.add_field(
                name=f"📱 Social Accounts ({len(social_accounts)})",
                value=socials_text,
                inline=False
            )
        else:
            embed.add_field(
                name="📱 Social Accounts",
                value="No social accounts linked - Use buttons below to add",
                inline=False
            )
        
        # === Creative Accounts Section ===
        creative_accounts = user_profile.get("creative_accounts", [])
        if creative_accounts:
            creatives_text = "\n".join([
                f"• **{acc['platform'].title()}**: {acc['display_name']}"
                for acc in creative_accounts[:5]
            ])
            if len(creative_accounts) > 5:
                creatives_text += f"\n... and {len(creative_accounts) - 5} more"
            
            embed.add_field(
                name=f"🎵 Creative Accounts ({len(creative_accounts)})",
                value=creatives_text,
                inline=False
            )
        else:
            embed.add_field(
                name="🎵 Creative Accounts",
                value="No music platforms linked - Use buttons below to add",
                inline=False
            )
        
        # === Collaborations Section ===
        collaborations = user_profile.get("collaborations", [])
        if collaborations:
            active_collabs = [c for c in collaborations if c.get("status") == "active"]
            embed.add_field(
                name=f"🤝 Collaborations ({len(active_collabs)}/{len(collaborations)})",
                value=f"{len(active_collabs)} active collaboration(s)",
                inline=False
            )
        else:
            embed.add_field(
                name="🤝 Collaborations",
                value="No collaborations yet",
                inline=False
            )
        
        # === Music Releases Section ===
        releases = user_profile.get("releases", [])
        if releases:
            embed.add_field(
                name=f"🎵 Music Releases ({len(releases)})",
                value=f"You have {len(releases)} release(s) - Click **Music Releases** button to manage",
                inline=False
            )
        else:
            embed.add_field(
                name="🎵 Music Releases",
                value="No releases yet - Click **Music Releases** to add your first release!",
                inline=False
            )
        
        # === Memories Section (from creative_profile) ===
        creative_profile = user_profile.get("creative_profile", {})
        memorable_facts = creative_profile.get("memorable_facts", [])
        if memorable_facts:
            facts_preview = "\n".join([
                f"• {fact.get('text', fact.get('fact', 'Unknown'))[:50]}{'...' if len(fact.get('text', fact.get('fact', ''))) > 50 else ''}"
                for fact in memorable_facts[:3]
            ])
            if len(memorable_facts) > 3:
                facts_preview += f"\n... and {len(memorable_facts) - 3} more memories"
            embed.add_field(
                name=f"🧠 Memories ({len(memorable_facts)})",
                value=facts_preview,
                inline=False
            )
        else:
            embed.add_field(
                name="🧠 Memories",
                value="Start chatting to build memories together!",
                inline=False
            )
        
        embed.set_footer(text="Use buttons below to manage your profile • Routes through universal Users collection")
        
        # Create button view
        view = UniversalProfilePanelView(self, user_id, guild_id, user_profile)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class UniversalProfilePanelView(discord.ui.View):
    """Navigation buttons for universal profile."""
    
    def __init__(self, profile_cog: UniversalProfilePanel, user_id: str, guild_id: Optional[str], user_profile: dict):
        super().__init__(timeout=None)
        self.profile_cog = profile_cog
        self.user_id = user_id
        self.guild_id = guild_id or ""  # Default to empty string if None
        self.user_profile = user_profile or {}  # Ensure it's always a dict
        self.user_profile = user_profile
    
    @discord.ui.button(label="Discord Account", emoji="🎮", style=discord.ButtonStyle.secondary)
    async def view_discord(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View Discord account details."""
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="🎮 Discord Account",
            color=discord.Color.blurple()
        )
        
        embed.add_field(
            name="User ID",
            value=f"`{self.user_id}`",
            inline=False
        )
        
        embed.add_field(
            name="Username",
            value=interaction.user.name,
            inline=True
        )
        
        embed.add_field(
            name="Display Name",
            value=interaction.user.display_name,
            inline=True
        )
        
        embed.add_field(
            name="Account Created",
            value=interaction.user.created_at.strftime("%Y-%m-%d"),
            inline=True
        )
        
        # Guild info
        if self.guild_id:
            guild = interaction.guild
            if guild:
                embed.add_field(
                    name="Current Guild",
                    value=f"{guild.name}",
                    inline=False
                )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Artist Profile", emoji="🎨", style=discord.ButtonStyle.primary)
    async def artist_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Manage artist profile."""
        await interaction.response.defer()
        
        artist_profile = self.user_profile.get("artist_profile", {})
        is_artist = artist_profile.get("is_artist", False)
        
        embed = discord.Embed(
            title="🎨 Artist Profile",
            color=discord.Color.purple()
        )
        
        if is_artist:
            stage_name = artist_profile.get("stage_name", "Unknown")
            bio = artist_profile.get("bio", "")
            website = artist_profile.get("website", "")
            established_at = artist_profile.get("established_at", "")
            
            embed.add_field(name="Stage Name", value=stage_name, inline=False)
            embed.add_field(name="Bio", value=bio or "No bio set", inline=False)
            embed.add_field(name="Website", value=website or "No website set", inline=False)
            if established_at:
                embed.add_field(name="Established", value=str(established_at)[:10], inline=False)
        else:
            embed.description = "Artist profile not yet enabled"
            embed.add_field(
                name="Enable Artist Profile",
                value="Use `/artist profile` command to set up your artist profile",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Social Accounts", emoji="📱", style=discord.ButtonStyle.success)
    async def social_accounts(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Manage social account links."""
        await interaction.response.defer()
        
        social_accounts = self.user_profile.get("social_accounts", [])
        
        embed = discord.Embed(
            title="📱 Social Accounts",
            description="Your linked social profiles",
            color=discord.Color.green()
        )
        
        if social_accounts:
            for acc in social_accounts:
                platform = acc.get("platform", "unknown").title()
                handle = acc.get("handle", "Unknown")
                verified = "✅ Verified" if acc.get("verified") else "⏳ Pending"
                embed.add_field(
                    name=f"{platform}",
                    value=f"**@{handle}**\n{verified}",
                    inline=False
                )
        else:
            embed.description = "No social accounts linked yet\nUse `/social link` to add accounts"
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Creative Accounts", emoji="🎵", style=discord.ButtonStyle.success)
    async def creative_accounts(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Manage creative account links."""
        await interaction.response.defer()
        
        creative_accounts = self.user_profile.get("creative_accounts", [])
        
        embed = discord.Embed(
            title="🎵 Creative Accounts",
            description="Your connected music & streaming platforms",
            color=discord.Color.green()
        )
        
        if creative_accounts:
            for acc in creative_accounts:
                platform = acc.get("platform", "unknown").title()
                display_name = acc.get("display_name", "Connected")
                verified = "✅ Connected" if acc.get("verified") else "⏳ Pending"
                embed.add_field(
                    name=f"{platform}",
                    value=f"**{display_name}**\n{verified}",
                    inline=False
                )
        else:
            embed.description = "No creative accounts linked yet\nUse `/creative link` to add accounts"
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Music Releases", emoji="🎵", style=discord.ButtonStyle.blurple)
    async def music_releases(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Manage music releases - Add, view, and edit releases."""
        try:
            # Create release manager view with release management buttons
            release_view = ReleaseManagerView(self.user_id)
            
            embed = discord.Embed(
                title="🎵 Music Release Manager",
                description="Add your releases, view your discography, or schedule distributions with Abby",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="🎵 Multi-Label Support",
                value="Manage releases from any distributor:\n" +
                      "• **Cool Breeze** - Our primary label\n" +
                      "• **Self-Released** - Independent releases\n" +
                      "• **Royalty Free** - Royalty-free tracks\n" +
                      "• **WIP** - Works in progress\n" +
                      "• **Other** - Any other distributor",
                inline=False
            )
            
            embed.add_field(
                name="📝 Features",
                value="• ➕ Add Release - Add past, current, or upcoming releases\n" +
                      "• 📋 My Releases - View and edit all your releases\n" +
                      "• ⏰ Schedule Release - Self-released only (label releases scheduled by admins)",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, view=release_view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"[profile_panel] Error in music_releases: {e}")
            await interaction.response.send_message(
                "❌ Error opening music release manager",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Setup universal profile panel cog."""
    await bot.add_cog(UniversalProfilePanel(bot))
    logger.debug("[👤] Universal Profile Panel loaded - Routes through Users collection")

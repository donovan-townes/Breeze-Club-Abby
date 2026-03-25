"""
Release Manager - Integrated Music Release Management for /profile

ARCHITECTURE:
- Subview within /profile → Music Releases tab
- Handles three release pathways:
  1. Auto-Detected: User shares link → Bot verifies → Cached
  2. User-Curated: Manual entry via Modal → Stored
  3. Distribution: Proton scheduled → Auto-synced (Phase 3)

COMPONENTS:
- ReleaseManagerView: Main buttons (Add Release, My Releases, Schedule Release)
- AddReleaseModal: Form for manual release entry (title, date, label, links)
- ReleaseListView: Display and edit user's releases with pagination
- LabelSelectView: Dropdown for dynamically managed labels

LABEL SYSTEM:
- Cool Breeze: Primary label (builtin)
- Self-Released: Independent artist (builtin)
- Royalty Free: Royalty-free tracks (builtin)
- WIP: Work in progress (builtin)
- Other: Catch-all for other distributors (builtin)
- NEW LABELS: Admin can add more via labels collection without code changes
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List, Callable, Dict, Any
from datetime import datetime
from enum import Enum

from abby_core.database.collections.users import get_collection as get_users_collection
from abby_core.database.collections.labels import (
    get_active_labels, 
    initialize_collection as init_labels
)
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════

class Platform(Enum):
    """Supported music platforms."""
    SPOTIFY = "spotify"
    APPLE_MUSIC = "apple_music"
    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"
    BANDCAMP = "bandcamp"
    TIDAL = "tidal"
    BEATPORT = "beatport"
    
    def display_name(self) -> str:
        names = {
            "spotify": "🎵 Spotify",
            "apple_music": "🍎 Apple Music",
            "youtube": "📺 YouTube",
            "soundcloud": "☁️ SoundCloud",
            "bandcamp": "🎹 Bandcamp",
            "tidal": "🌊 Tidal",
            "beatport": "🎚️ Beatport"
        }
        return names.get(self.value, self.value.title())


# ═══════════════════════════════════════════════════════════════
# MODALS
# ═══════════════════════════════════════════════════════════════

class AddReleaseModal(discord.ui.Modal, title="🎵 Add Your Release"):
    """Modal for manual release entry - integrated in /profile."""
    
    release_title = discord.ui.TextInput(
        label="Release Title",
        placeholder="e.g., Neon Visions, Ethereal Dreams",
        max_length=200,
        required=True
    )
    
    release_date = discord.ui.TextInput(
        label="Release Date (YYYY-MM-DD)",
        placeholder="2026-01-30",
        max_length=10,
        required=True
    )
    
    spotify_url = discord.ui.TextInput(
        label="Spotify Link (optional)",
        placeholder="https://open.spotify.com/track/...",
        max_length=500,
        required=False
    )
    
    apple_music_url = discord.ui.TextInput(
        label="Apple Music Link (optional)",
        placeholder="https://music.apple.com/...",
        max_length=500,
        required=False
    )
    
    youtube_url = discord.ui.TextInput(
        label="YouTube Link (optional)",
        placeholder="https://www.youtube.com/watch?v=...",
        max_length=500,
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission - show label selection."""
        try:
            # Validate release date format
            try:
                release_dt = datetime.strptime(self.release_date.value, "%Y-%m-%d")
            except ValueError:
                await interaction.response.send_message(
                    "❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2026-01-30)",
                    ephemeral=True
                )
                return
            
            # Get active labels from database
            labels = get_active_labels()
            if not labels:
                await interaction.response.send_message(
                    "❌ No labels available. Please try again later.",
                    ephemeral=True
                )
                logger.error("[release_manager] No labels found in database")
                return
            
            # Store data temporarily in view
            view = LabelSelectView(
                user_id=str(interaction.user.id),
                title=self.release_title.value,
                release_date=release_dt,
                spotify_url=self.spotify_url.value or None,
                apple_music_url=self.apple_music_url.value or None,
                youtube_url=self.youtube_url.value or None,
                labels=labels
            )
            
            embed = discord.Embed(
                title="🏷️ Select a Label",
                description="Choose the label or distributor for this release",
                color=discord.Color.gold()
            )
            
            for label in labels:
                embed.add_field(
                    name=label.get("display_name", "Unknown"),
                    value=label.get("description", "No description"),
                    inline=False
                )
            
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"[release_manager] Error in AddReleaseModal: {e}")
            await interaction.response.send_message(
                "❌ Error processing release. Please try again.",
                ephemeral=True
            )


class ScheduleReleaseModal(discord.ui.Modal, title="⏰ Schedule Indie Release"):
    """Schedule a self-released (indie) release for future announcement."""

    release_title = discord.ui.TextInput(
        label="Release Title",
        placeholder="e.g., Neon Visions (Indie)",
        max_length=200,
        required=True
    )

    release_date = discord.ui.TextInput(
        label="Release Date (YYYY-MM-DD)",
        placeholder="2026-02-15",
        max_length=10,
        required=True
    )

    spotify_url = discord.ui.TextInput(
        label="Spotify Link (optional)",
        placeholder="https://open.spotify.com/track/...",
        max_length=500,
        required=False
    )

    apple_music_url = discord.ui.TextInput(
        label="Apple Music Link (optional)",
        placeholder="https://music.apple.com/...",
        max_length=500,
        required=False
    )

    youtube_url = discord.ui.TextInput(
        label="YouTube Link (optional)",
        placeholder="https://www.youtube.com/watch?v=...",
        max_length=500,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle scheduled indie release creation (self-released only)."""
        try:
            try:
                release_dt = datetime.strptime(self.release_date.value, "%Y-%m-%d")
            except ValueError:
                await interaction.response.send_message(
                    "❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2026-02-15)",
                    ephemeral=True
                )
                return

            platforms = []
            if self.spotify_url.value:
                platforms.append({
                    "platform": "spotify",
                    "url": self.spotify_url.value,
                    "platform_id": None
                })
            if self.apple_music_url.value:
                platforms.append({
                    "platform": "apple_music",
                    "url": self.apple_music_url.value,
                    "platform_id": None
                })
            if self.youtube_url.value:
                platforms.append({
                    "platform": "youtube",
                    "url": self.youtube_url.value,
                    "platform_id": None
                })

            release_doc = {
                "title": self.release_title.value,
                "release_date": release_dt,
                "source": "user_curated",
                "label": "self_released",
                "status": "scheduled",
                "platforms": platforms,
                "metadata": {
                    "genre": "Unknown",
                    "verified": False,
                    "promotional": False
                },
                "distribution_release_id": None,
                "added_date": datetime.utcnow(),
                "scheduled_at": datetime.utcnow(),
                "scheduled_by": str(interaction.user.id)
            }

            collection = get_users_collection()
            result = collection.update_one(
                {"user_id": str(interaction.user.id)},
                {
                    "$push": {"releases": release_doc},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

            if result.modified_count > 0:
                embed = discord.Embed(
                    title="✅ Scheduled!",
                    description=f"**{self.release_title.value}** is scheduled for {release_dt.strftime('%Y-%m-%d')}",
                    color=discord.Color.green()
                )
                embed.add_field(name="Label", value="👤 Self-Released", inline=True)
                embed.add_field(name="Platforms", value=f"{len(platforms)} platform(s)", inline=True)

                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"[release_manager] Scheduled indie release for {interaction.user.id}: {self.release_title.value}")
            else:
                await interaction.response.send_message(
                    "❌ Could not schedule release. Please try again.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"[release_manager] Error scheduling release: {e}")
            await interaction.response.send_message(
                "❌ Error scheduling release. Please try again.",
                ephemeral=True
            )


# ═══════════════════════════════════════════════════════════════
# VIEWS
# ═══════════════════════════════════════════════════════════════

class LabelSelectView(discord.ui.View):
    """Select label/distributor for release - dynamically loaded from database."""
    
    def __init__(self, user_id: str, title: str, release_date: datetime,
                 spotify_url: Optional[str], apple_music_url: Optional[str],
                 youtube_url: Optional[str], labels: List[Dict]):
        super().__init__()
        self.user_id = user_id
        self.title = title
        self.release_date = release_date
        self.spotify_url = spotify_url
        self.apple_music_url = apple_music_url
        self.youtube_url = youtube_url
        self.labels = labels
        
        # Create buttons dynamically for each label
        self._create_label_buttons()
    
    def _create_label_buttons(self):
        """Create a button for each active label."""
        for label in self.labels:
            label_id = label.get("label_id")
            display_name = label.get("display_name", label_id)
            
            # Extract emoji and text
            emoji_and_name = display_name.split(" ", 1)
            emoji = emoji_and_name[0] if len(emoji_and_name) > 1 else "📌"
            button_label = emoji_and_name[1] if len(emoji_and_name) > 1 else display_name
            
            # Truncate button label to fit Discord's 80 char limit
            button_label = button_label[:75]
            
            # Create button with callback
            button = discord.ui.Button(
                label=button_label,
                style=discord.ButtonStyle.grey,
                custom_id=f"label_{label_id}"
            )
            button.callback = self._make_label_callback(label_id)
            self.add_item(button)
    
    def _make_label_callback(self, label_id: str):
        """Create a callback function for a specific label."""
        async def callback(interaction: discord.Interaction):
            await self.save_release(interaction, label_id)
        return callback
    
    async def save_release(self, interaction: discord.Interaction, label_id: str):
        """Save release to user profile."""
        try:
            collection = get_users_collection()
            
            # Build platforms array
            platforms = []
            if self.spotify_url:
                platforms.append({
                    "platform": "spotify",
                    "url": self.spotify_url,
                    "platform_id": None
                })
            if self.apple_music_url:
                platforms.append({
                    "platform": "apple_music",
                    "url": self.apple_music_url,
                    "platform_id": None
                })
            if self.youtube_url:
                platforms.append({
                    "platform": "youtube",
                    "url": self.youtube_url,
                    "platform_id": None
                })
            
            # Create release document
            release_doc = {
                "title": self.title,
                "release_date": self.release_date,
                "source": "user_curated",
                "label": label_id,
                "status": "released",
                "platforms": platforms,
                "metadata": {
                    "genre": "Unknown",
                    "verified": False,
                    "promotional": False
                },
                "distribution_release_id": None,
                "added_date": datetime.utcnow()
            }
            
            # Add to user's releases array
            result = collection.update_one(
                {"user_id": self.user_id},
                {
                    "$push": {"releases": release_doc},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            if result.modified_count > 0:
                # Find label display name
                label_doc = next((l for l in self.labels if l.get("label_id") == label_id), None)
                label_name = label_doc.get("display_name", label_id) if label_doc else label_id
                
                embed = discord.Embed(
                    title="✅ Release Added!",
                    description=f"**{self.title}** has been added to your profile",
                    color=discord.Color.green()
                )
                embed.add_field(name="Label", value=label_name, inline=True)
                embed.add_field(name="Release Date", value=self.release_date.strftime("%Y-%m-%d"), inline=True)
                embed.add_field(name="Platforms", value=f"{len(platforms)} platform(s)", inline=True)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"[release_manager] Added release for {self.user_id}: {self.title}")
            else:
                await interaction.response.send_message(
                    "❌ Could not save release. Please try again.",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"[release_manager] Error saving release: {e}")
            await interaction.response.send_message(
                f"❌ Error saving release: {str(e)}",
                ephemeral=True
            )


class ReleaseManagerView(discord.ui.View):
    """Main release management buttons - integrated in /profile Music tab."""
    
    def __init__(self, user_id: str, on_add_release: Optional[Callable] = None,
                 on_list_releases: Optional[Callable] = None):
        super().__init__()
        self.user_id = user_id
        self.on_add_release = on_add_release
        self.on_list_releases = on_list_releases
    
    @discord.ui.button(label="+ Add Release", style=discord.ButtonStyle.success, emoji="🎵")
    async def add_release(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to add new release."""
        try:
            await interaction.response.send_modal(AddReleaseModal())
        except Exception as e:
            logger.error(f"[release_manager] Error opening add release modal: {e}")
            await interaction.response.send_message(
                "❌ Error opening release form",
                ephemeral=True
            )
    
    @discord.ui.button(label="My Releases", style=discord.ButtonStyle.primary, emoji="📋")
    async def list_releases(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show user's releases with pagination."""
        try:
            collection = get_users_collection()
            user = collection.find_one({"user_id": self.user_id})
            
            if not user or not user.get("releases"):
                await interaction.response.send_message(
                    "📭 You don't have any releases yet. Add one with the **+ Add Release** button!",
                    ephemeral=True
                )
                return
            
            releases = user.get("releases", [])
            
            # Create paginated view
            view = ReleaseListView(releases)
            embed = view.get_embed(0)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"[release_manager] Error listing releases: {e}")
            await interaction.response.send_message(
                "❌ Error fetching releases",
                ephemeral=True
            )
    
    @discord.ui.button(label="Schedule Release", style=discord.ButtonStyle.blurple, emoji="⏰")
    async def schedule_release(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Schedule indie release (self-released only)."""
        try:
            await interaction.response.send_modal(ScheduleReleaseModal())
        except Exception as e:
            logger.error(f"[release_manager] Error in schedule release: {e}")
            await interaction.response.send_message(
                "❌ Error",
                ephemeral=True
            )


class ReleaseListView(discord.ui.View):
    """Display paginated list of user's releases."""
    
    def __init__(self, releases: List[dict]):
        super().__init__()
        self.releases = releases
        self.current_page = 0
        self.items_per_page = 5
        self.update_buttons()
    
    def update_buttons(self):
        """Update pagination buttons based on current page."""
        total_pages = (len(self.releases) + self.items_per_page - 1) // self.items_per_page
        
        self.previous.disabled = self.current_page == 0
        self.next.disabled = self.current_page >= total_pages - 1
    
    def get_embed(self, page: int) -> discord.Embed:
        """Generate embed for a specific page."""
        start_idx = page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_releases = self.releases[start_idx:end_idx]
        
        total_pages = (len(self.releases) + self.items_per_page - 1) // self.items_per_page
        
        embed = discord.Embed(
            title="🎵 Your Releases",
            description=f"Page {page + 1} of {total_pages}",
            color=discord.Color.blurple()
        )
        
        for i, release in enumerate(page_releases, start=start_idx + 1):
            title = release.get("title", "Unknown")
            label = release.get("label", "unknown").replace("_", " ").title()
            release_date = release.get("release_date")
            platforms = len(release.get("platforms", []))
            status = release.get("status", "released").replace("_", " ").title()
            
            if isinstance(release_date, datetime):
                date_str = release_date.strftime("%Y-%m-%d")
            else:
                date_str = str(release_date)
            
            value = f"📅 {date_str} | 🏷️ {label} | 📌 {status} | 📱 {platforms} platform(s)"
            embed.add_field(name=f"{i}. {title}", value=value, inline=False)
        
        embed.set_footer(text=f"Total releases: {len(self.releases)}")
        return embed
    
    @discord.ui.button(label="← Previous", style=discord.ButtonStyle.grey)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page."""
        self.current_page -= 1
        self.update_buttons()
        embed = self.get_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Next →", style=discord.ButtonStyle.grey)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        self.current_page += 1
        self.update_buttons()
        embed = self.get_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)


# ═══════════════════════════════════════════════════════════════
# COG SETUP
# ═══════════════════════════════════════════════════════════════

async def setup(bot: commands.Bot):
    """Load release manager cog - initialize labels collection."""
    try:
        # Initialize labels collection (seeds builtin labels on first run)
        init_labels()
        logger.debug("[🎵] Release Manager loaded - Labels collection initialized")
    except Exception as e:
        logger.error(f"[release_manager] Error during setup: {e}")


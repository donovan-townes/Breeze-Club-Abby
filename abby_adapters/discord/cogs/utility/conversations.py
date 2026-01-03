"""
Conversation Management Commands for Users and Admins

User commands:
- /conversation clear - Delete own sessions
- /conversation view - View own sessions history
- /conversation export - Export own sessions as JSON

Admin commands:
- /conversation admin clear_user - Delete specific user's sessions
- /conversation admin clear_guild - Delete all guild sessions
- /conversation admin stats - View guild conversation statistics
- /conversation admin toggle_storage - Enable/disable session storage for guild
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from typing import Optional
import json
from io import BytesIO

try:
    from abby_core.database.mongodb import connect_to_mongodb, get_db
    from abby_core.database.memory_settings import get_guild_setting, set_guild_setting
    from abby_core.observability.logging import logging
except ImportError:
    logging = None

logger = logging.getLogger(__name__) if logging else None


class ConversationCommands(commands.GroupCog, name="conversation"):
    """Manage conversation history."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()
        if logger:
            logger.info("[💬] Conversation Management Commands loaded")
    
    @app_commands.command(name="clear", description="Delete your conversation history with Abby")
    async def clear_own_conversations(self, interaction: discord.Interaction):
        """Delete all of the user's sessions."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            db = get_db()
            sessions_collection = db["chat_sessions"]
            
            # Build query
            query = {"user_id": user_id}
            if guild_id:
                query["guild_id"] = guild_id
            
            result = sessions_collection.delete_many(query)
            
            await interaction.followup.send(
                f"✅ Deleted {result.deleted_count} conversation session(s).",
                ephemeral=True
            )
            
            if logger:
                logger.info(f"[💬] User {user_id} deleted {result.deleted_count} sessions")
        
        except Exception as e:
            if logger:
                logger.error(f"[💬] Failed to delete conversations: {e}")
            await interaction.followup.send(
                "❌ Failed to delete conversations. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="view", description="View your conversation history with Abby")
    async def view_own_conversations(self, interaction: discord.Interaction):
        """View paginated list of user's past sessions."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            db = get_db()
            sessions_collection = db["chat_sessions"]
            
            # Build query
            query = {"user_id": user_id}
            if guild_id:
                query["guild_id"] = guild_id
            
            # Get sessions, sorted by most recent
            sessions = list(sessions_collection.find(query).sort("created_at", -1).limit(10))
            
            if not sessions:
                await interaction.followup.send(
                    "📭 No conversation history found.",
                    ephemeral=True
                )
                return
            
            # Create embed
            embed = discord.Embed(
                title="Your Conversations with Abby",
                description=f"Showing {len(sessions)} recent session(s)",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            for i, session in enumerate(sessions, 1):
                created_at = session.get("created_at", datetime.utcnow())
                closed_at = session.get("closed_at", None)
                summary = session.get("summary", "No summary")[:100]
                
                time_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "Unknown"
                status = "Closed" if closed_at else "Open"
                
                embed.add_field(
                    name=f"Session {i} - {time_str} ({status})",
                    value=f"Summary: {summary}...",
                    inline=False
                )
            
            embed.set_footer(text="Use /conversation export to download your full history")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            if logger:
                logger.info(f"[💬] User {user_id} viewed {len(sessions)} sessions")
        
        except Exception as e:
            if logger:
                logger.error(f"[💬] Failed to view conversations: {e}")
            await interaction.followup.send(
                "❌ Failed to load conversations. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="export", description="Download your conversation history as JSON")
    async def export_own_conversations(self, interaction: discord.Interaction):
        """Export user's sessions as JSON file."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            db = get_db()
            sessions_collection = db["chat_sessions"]
            
            # Build query
            query = {"user_id": user_id}
            if guild_id:
                query["guild_id"] = guild_id
            
            sessions = list(sessions_collection.find(query))
            
            if not sessions:
                await interaction.followup.send(
                    "📭 No conversation history to export.",
                    ephemeral=True
                )
                return
            
            # Convert to JSON-serializable format
            export_data = {
                "user_id": user_id,
                "guild_id": guild_id,
                "export_date": datetime.utcnow().isoformat(),
                "session_count": len(sessions),
                "sessions": []
            }
            
            for session in sessions:
                # Remove MongoDB ObjectId
                session.pop("_id", None)
                # Convert datetime objects
                if "created_at" in session:
                    session["created_at"] = session["created_at"].isoformat()
                if "closed_at" in session:
                    session["closed_at"] = session["closed_at"].isoformat() if session["closed_at"] else None
                
                export_data["sessions"].append(session)
            
            # Create JSON file
            json_str = json.dumps(export_data, indent=2)
            json_bytes = BytesIO(json_str.encode('utf-8'))
            
            # Send as file
            file = discord.File(json_bytes, filename=f"abby_conversations_{user_id}.json")
            await interaction.followup.send(
                content="📥 Here's your conversation history:",
                file=file,
                ephemeral=True
            )
            
            if logger:
                logger.info(f"[💬] User {user_id} exported {len(sessions)} sessions")
        
        except Exception as e:
            if logger:
                logger.error(f"[💬] Failed to export conversations: {e}")
            await interaction.followup.send(
                "❌ Failed to export conversations. Please try again later.",
                ephemeral=True
            )


class ConversationAdmin(commands.GroupCog, name="admin"):
    """Admin commands for conversation management."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()
    
    @app_commands.command(name="clear_user", description="Delete a user's conversation history")
    @app_commands.default_permissions(administrator=True)
    async def admin_clear_user(self, interaction: discord.Interaction, user: discord.User):
        """Delete all sessions for a specific user."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(user.id)
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            db = get_db()
            sessions_collection = db["chat_sessions"]
            
            # Build query
            query = {"user_id": user_id}
            if guild_id:
                query["guild_id"] = guild_id
            
            result = sessions_collection.delete_many(query)
            
            await interaction.followup.send(
                f"✅ Deleted {result.deleted_count} conversation(s) for {user.mention}.",
                ephemeral=True
            )
            
            if logger:
                logger.info(f"[💬] Admin deleted {result.deleted_count} sessions for user {user_id}")
        
        except Exception as e:
            if logger:
                logger.error(f"[💬] Failed to delete user conversations: {e}")
            await interaction.followup.send(
                "❌ Failed to delete conversations. Please try again later.",
                ephemeral=True
            )


    @app_commands.command(name="clear_guild", description="Delete all conversation history for this server")
    @app_commands.default_permissions(administrator=True)
    async def admin_clear_guild(self, interaction: discord.Interaction):
        """Delete all sessions in the guild with confirmation."""
        
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.confirmed = False
            
            @discord.ui.button(label="Confirm Deletion", style=discord.ButtonStyle.danger)
            async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.confirmed = True
                await interaction.response.defer()
                self.stop()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.defer()
                self.stop()
        
        try:
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            view = ConfirmView()
            await interaction.response.send_message(
                f"⚠️ This will permanently delete ALL conversation history for this server. Are you sure?",
                view=view,
                ephemeral=True
            )
            
            await view.wait()
            
            if not view.confirmed:
                await interaction.followup.send("❌ Deletion cancelled.", ephemeral=True)
                return
            
            db = get_db()
            sessions_collection = db["chat_sessions"]
            
            query = {"guild_id": guild_id} if guild_id else {}
            result = sessions_collection.delete_many(query)
            
            await interaction.followup.send(
                f"✅ Deleted {result.deleted_count} conversation(s) for this server.",
                ephemeral=True
            )
            
            if logger:
                logger.info(f"[💬] Admin deleted {result.deleted_count} guild sessions")
        
        except Exception as e:
            if logger:
                logger.error(f"[💬] Failed to delete guild conversations: {e}")
            await interaction.followup.send(
                "❌ Failed to delete conversations. Please try again later.",
                ephemeral=True
            )


    @app_commands.command(name="stats", description="View conversation statistics for this server")
    @app_commands.default_permissions(administrator=True)
    async def admin_stats(self, interaction: discord.Interaction):
        """Show guild conversation statistics."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            db = get_db()
            sessions_collection = db["chat_sessions"]
            
            query = {"guild_id": guild_id} if guild_id else {}
            
            # Get stats
            total_sessions = sessions_collection.count_documents(query)
            closed_sessions = sessions_collection.count_documents({**query, "status": "closed"})
            
            # Get unique users
            pipeline = [
                {"$match": query},
                {"$group": {"_id": "$user_id", "session_count": {"$sum": 1}}},
                {"$count": "unique_users"}
            ]
            unique_users_result = list(sessions_collection.aggregate(pipeline))
            unique_users = unique_users_result[0]["unique_users"] if unique_users_result else 0
            
            # Calculate average sessions per user
            avg_per_user = total_sessions / unique_users if unique_users > 0 else 0
            
            embed = discord.Embed(
                title="📊 Conversation Statistics",
                description=f"Statistics for {interaction.guild.name}",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="Total Sessions", value=str(total_sessions), inline=True)
            embed.add_field(name="Closed Sessions", value=str(closed_sessions), inline=True)
            embed.add_field(name="Unique Users", value=str(unique_users), inline=True)
            embed.add_field(name="Avg Sessions/User", value=f"{avg_per_user:.2f}", inline=True)
            
            embed.set_footer(text="Use /conversation admin toggle_storage to disable storage")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            if logger:
                logger.info(f"[💬] Admin viewed stats: {total_sessions} sessions, {unique_users} users")
        
        except Exception as e:
            if logger:
                logger.error(f"[💬] Failed to get conversation stats: {e}")
            await interaction.followup.send(
                "❌ Failed to retrieve statistics. Please try again later.",
                ephemeral=True
            )


    @app_commands.command(name="toggle_storage", description="Enable/disable conversation storage for this server")
    @app_commands.default_permissions(administrator=True)
    async def admin_toggle_storage(self, interaction: discord.Interaction):
        """Toggle conversation storage for guild."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = int(interaction.guild.id) if interaction.guild else 0
            
            current_setting = get_guild_setting(guild_id, "conversation_storage_enabled", True)
            new_setting = not current_setting
            
            set_guild_setting(guild_id, "conversation_storage_enabled", new_setting)
            
            status = "enabled" if new_setting else "disabled"
            await interaction.followup.send(
                f"✅ Conversation storage {status} for this server.",
                ephemeral=True
            )
            
            if logger:
                logger.info(f"[💬] Guild {guild_id} conversation storage set to {new_setting}")
        
        except Exception as e:
            if logger:
                logger.error(f"[💬] Failed to toggle storage: {e}")
            await interaction.followup.send(
                "❌ Failed to update storage setting. Please try again later.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ConversationCommands(bot))
    await bot.add_cog(ConversationAdmin(bot))

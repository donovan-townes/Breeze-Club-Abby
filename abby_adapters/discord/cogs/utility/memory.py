"""
Memory Management Commands for Users and Admins

User commands:
- /memory view - View own stored memories
- /memory forget - Delete specific memories
- /memory export - Export memories as JSON
- /memory opt_out - Disable memory collection
- /memory terms - View/manage privacy terms

Admin commands:
- /memory admin stats - Guild-wide memory statistics
- /memory admin inspect - View specific user's memory
- /memory admin maintenance - Run maintenance on memories
- /memory admin purge_user - GDPR deletion of user memories
- /memory admin export_guild - Bulk export all guild memories
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from typing import Optional
import json
from io import BytesIO

try:
    from abby_core.database.mongodb import get_db
    from abby_core.database.memory_settings import get_guild_setting, set_guild_setting
    from abby_core.observability.logging import logging
    import tdos_memory as memory
    from tdos_memory.maintenance import run_maintenance
    from tdos_memory.service import create_memory_service
    from tdos_memory.storage import MongoMemoryStore
except ImportError:
    logging = None

logger = logging.getLogger(__name__) if logging else None


class MemoryCommands(commands.GroupCog, name="memory"):
    """View and manage your memories with Abby."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()
        
        # Initialize memory service
        try:
            from abby_core.database.mongodb import connect_to_mongodb
            mongo_client = connect_to_mongodb()
            self.memory_store = MongoMemoryStore(
                storage_client=mongo_client,
                profile_collection="discord_profiles",
                session_collection="chat_sessions",
                narrative_collection="shared_narratives"
            )
            self.memory_service = create_memory_service(
                store=self.memory_store,
                source_id="discord",
                logger=logger
            )
        except Exception as e:
            if logger:
                logger.error(f"[🧠] Failed to initialize memory service: {e}")
            self.memory_service = None
        
        if logger:
            logger.info("[🧠] Memory Management Commands loaded")
    
    @app_commands.command(name="view", description="View your stored memories")
    async def view_memories(self, interaction: discord.Interaction):
        """Display user's stored memories."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if not self.memory_service:
                await interaction.followup.send("❌ Memory system temporarily unavailable.", ephemeral=True)
                return
            
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            # Check opt-out status
            opted_out = get_guild_setting(int(guild_id) if guild_id else 0, f"user_opted_out_{user_id}", False)
            if opted_out:
                await interaction.followup.send(
                    "❌ You've opted out of memory collection. No memories are stored.",
                    ephemeral=True
                )
                return
            
            # Get profile
            profile = self.memory_service.get_profile(user_id, guild_id)
            if not profile:
                await interaction.followup.send(
                    "📭 No memories found. Chat with me to start building memories!",
                    ephemeral=True
                )
                return
            
            facts = profile.get("creative_profile", {}).get("memorable_facts", [])
            if not facts:
                await interaction.followup.send(
                    "📭 No memories found. Chat with me to start building memories!",
                    ephemeral=True
                )
                return
            
            # Create paginated embed
            embed = discord.Embed(
                title="🧠 Your Memories with Abby",
                description=f"Total memories: {len(facts)}",
                color=discord.Color.purple(),
                timestamp=datetime.utcnow()
            )
            
            for i, fact in enumerate(facts[:5], 1):  # Show first 5
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
            
            embed.set_footer(text="Use /memory forget to remove memories • Use /memory export for full list")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            if logger:
                logger.info(f"[🧠] User {user_id} viewed {len(facts)} memories")
        
        except Exception as e:
            if logger:
                logger.error(f"[🧠] Failed to view memories: {e}")
            await interaction.followup.send(
                "❌ Failed to load memories. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="forget", description="Delete a specific memory")
    async def forget_memory(self, interaction: discord.Interaction):
        """Remove a specific memory via modal input."""
        
        class ForgetModal(discord.ui.Modal, title="Forget Memory"):
            memory_text = discord.ui.TextInput(
                label="Memory to forget (exact text)",
                placeholder="Enter the exact memory text...",
                required=True,
                max_length=500
            )
            
            async def on_submit(self, modal_interaction: discord.Interaction):
                await modal_interaction.response.defer(ephemeral=True)
                
                try:
                    if not self.view.memory_service:
                        await modal_interaction.followup.send(
                            "❌ Memory system temporarily unavailable.",
                            ephemeral=True
                        )
                        return
                    
                    user_id = str(modal_interaction.user.id)
                    guild_id = str(modal_interaction.guild.id) if modal_interaction.guild else None
                    memory_to_forget = str(self.memory_text).strip()
                    
                    db = get_db()
                    profiles_collection = db["discord_profiles"]
                    
                    # Find and update profile
                    result = profiles_collection.update_one(
                        {"user_id": user_id, "guild_id": guild_id},
                        {
                            "$pull": {
                                "creative_profile.memorable_facts": {
                                    "text": {"$regex": f"^{memory_to_forget}$", "$options": "i"}
                                }
                            }
                        }
                    )
                    
                    if result.modified_count > 0:
                        # Invalidate cache
                        memory.invalidate_cache(user_id, guild_id, source_id="discord")
                        
                        await modal_interaction.followup.send(
                            f"✅ Forgot: \"{memory_to_forget}\"",
                            ephemeral=True
                        )
                        if logger:
                            logger.info(f"[🧠] User {user_id} forgot memory: {memory_to_forget}")
                    else:
                        await modal_interaction.followup.send(
                            "❌ Memory not found. Check exact text and try again.",
                            ephemeral=True
                        )
                
                except Exception as e:
                    if logger:
                        logger.error(f"[🧠] Failed to forget memory: {e}")
                    await modal_interaction.followup.send(
                        "❌ Failed to forget memory. Please try again later.",
                        ephemeral=True
                    )
        
        modal = ForgetModal()
        modal.view = self  # Attach cog to modal for access to memory_service
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="export", description="Download all your memories as JSON")
    async def export_memories(self, interaction: discord.Interaction):
        """Export user's memories as JSON file."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if not self.memory_service:
                await interaction.followup.send("❌ Memory system temporarily unavailable.", ephemeral=True)
                return
            
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            profile = self.memory_service.get_profile(user_id, guild_id)
            if not profile:
                await interaction.followup.send(
                    "📭 No memories to export.",
                    ephemeral=True
                )
                return
            
            # Prepare export data
            export_data = {
                "user_id": user_id,
                "guild_id": guild_id,
                "export_date": datetime.utcnow().isoformat(),
                "profile": {
                    "username": profile.get("username"),
                    "nickname": profile.get("nickname"),
                    "memorable_facts": profile.get("creative_profile", {}).get("memorable_facts", [])
                }
            }
            
            # Convert datetime objects to ISO format
            for fact in export_data["profile"]["memorable_facts"]:
                if "added_at" in fact:
                    fact["added_at"] = fact["added_at"].isoformat() if hasattr(fact["added_at"], "isoformat") else str(fact["added_at"])
                if "last_confirmed" in fact:
                    fact["last_confirmed"] = fact["last_confirmed"].isoformat() if hasattr(fact["last_confirmed"], "isoformat") else str(fact["last_confirmed"])
            
            # Create JSON file
            json_str = json.dumps(export_data, indent=2)
            json_bytes = BytesIO(json_str.encode('utf-8'))
            
            # Send as file
            file = discord.File(json_bytes, filename=f"abby_memories_{user_id}.json")
            await interaction.followup.send(
                content="📥 Here's all your memories:",
                file=file,
                ephemeral=True
            )
            
            if logger:
                logger.info(f"[🧠] User {user_id} exported memories")
        
        except Exception as e:
            if logger:
                logger.error(f"[🧠] Failed to export memories: {e}")
            await interaction.followup.send(
                "❌ Failed to export memories. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="opt_out", description="Disable memory collection")
    async def opt_out_memory(self, interaction: discord.Interaction):
        """Toggle memory collection opt-out status."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            guild_id = int(interaction.guild.id) if interaction.guild else 0
            
            # Check current opt-out status
            opted_out = get_guild_setting(guild_id, f"user_opted_out_{user_id}", False)
            new_status = not opted_out
            
            # Update setting
            set_guild_setting(guild_id, f"user_opted_out_{user_id}", new_status)
            
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
                logger.info(f"[🧠] User {user_id} opted out: {new_status}")
        
        except Exception as e:
            if logger:
                logger.error(f"[🧠] Failed to update opt-out status: {e}")
            await interaction.followup.send(
                "❌ Failed to update setting. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="terms", description="View privacy terms and consent status")
    async def memory_terms(self, interaction: discord.Interaction):
        """Show privacy policy and manage consent."""
        
        class TermsView(discord.ui.View):
            def __init__(self, bot):
                super().__init__()
                self.bot = bot
                self.user_accepted = False
            
            @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
            async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                user_id = str(interaction.user.id)
                guild_id = int(interaction.guild.id) if interaction.guild else 0
                set_guild_setting(guild_id, f"terms_accepted_{user_id}", True)
                await interaction.response.defer()
                self.user_accepted = True
                self.stop()
            
            @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
            async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                user_id = str(interaction.user.id)
                guild_id = int(interaction.guild.id) if interaction.guild else 0
                set_guild_setting(guild_id, f"terms_accepted_{user_id}", False)
                await interaction.response.defer()
                self.stop()
        
        try:
            user_id = str(interaction.user.id)
            guild_id = int(interaction.guild.id) if interaction.guild else 0
            
            # Check acceptance status
            accepted = get_guild_setting(guild_id, f"terms_accepted_{user_id}", None)
            
            embed = discord.Embed(
                title="🔐 Privacy & Memory Terms",
                description="Abby uses memories to provide better conversations. Here's how:",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="What memories are stored",
                value="• Facts about you (interests, preferences, experiences)\n• Conversation summaries\n• How we interact together",
                inline=False
            )
            
            embed.add_field(
                name="How long memories last",
                value="• Memories naturally decay over time (90-day default)\n• You can delete any memory anytime\n• You can request full export or deletion",
                inline=False
            )
            
            embed.add_field(
                name="Your control",
                value="• Use `/memory opt_out` to disable collection\n• Use `/memory forget` to remove specific memories\n• Use `/memory export` for your data\n• All memories are encrypted at rest",
                inline=False
            )
            
            if accepted is None:
                embed.add_field(
                    name="📋 Consent Status",
                    value="You haven't responded to this policy yet.",
                    inline=False
                )
            elif accepted:
                embed.add_field(
                    name="✅ Consent Status",
                    value="You've accepted memory storage.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="❌ Consent Status",
                    value="You've declined memory storage. Use buttons below to change.",
                    inline=False
                )
            
            view = TermsView(self.bot)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            if logger:
                logger.info(f"[🧠] User {user_id} viewed privacy terms")
        
        except Exception as e:
            if logger:
                logger.error(f"[🧠] Failed to show terms: {e}")
            await interaction.response.send_message(
                "❌ Failed to load privacy terms. Please try again later.",
                ephemeral=True
            )


class MemoryAdmin(commands.GroupCog, name="memory_admin"):
    """Admin commands for memory management."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()
    @app_commands.command(name="stats", description="View guild memory statistics")
    @app_commands.default_permissions(administrator=True)
    async def admin_stats(self, interaction: discord.Interaction):
        """Show guild memory statistics."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            db = get_db()
            profiles_collection = db["discord_profiles"]
            
            # Get stats
            total_profiles = profiles_collection.count_documents({"guild_id": guild_id})
            
            # Get average facts per profile
            pipeline = [
                {"$match": {"guild_id": guild_id}},
                {"$addFields": {
                    "fact_count": {"$size": {"$ifNull": ["$creative_profile.memorable_facts", []]}}
                }},
                {"$group": {
                    "_id": None,
                    "total_facts": {"$sum": "$fact_count"},
                    "avg_facts": {"$avg": "$fact_count"}
                }}
            ]
            stats_result = list(profiles_collection.aggregate(pipeline))
            
            total_facts = 0
            avg_facts = 0
            if stats_result:
                total_facts = int(stats_result[0]["total_facts"])
                avg_facts = stats_result[0]["avg_facts"]
            
            embed = discord.Embed(
                title="🧠 Guild Memory Statistics",
                description=f"Memory statistics for {interaction.guild.name}",
                color=discord.Color.purple(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="Total Profiles", value=str(total_profiles), inline=True)
            embed.add_field(name="Total Facts", value=str(total_facts), inline=True)
            embed.add_field(name="Avg Facts/User", value=f"{avg_facts:.1f}", inline=True)
            
            embed.set_footer(text="Use /memory admin maintenance to run system checks")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            if logger:
                logger.info(f"[🧠] Admin viewed stats: {total_profiles} profiles, {total_facts} facts")
        
        except Exception as e:
            if logger:
                logger.error(f"[🧠] Failed to get stats: {e}")
            await interaction.followup.send(
                "❌ Failed to retrieve statistics. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="inspect", description="View a user's memory profile")
    @app_commands.default_permissions(administrator=True)
    async def admin_inspect(self, interaction: discord.Interaction, user: discord.User):
        """Show detailed memory profile for a user."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            db = get_db()
            profiles_collection = db["discord_profiles"]
            
            profile = profiles_collection.find_one({"user_id": str(user.id), "guild_id": guild_id})
            if not profile:
                await interaction.followup.send(
                    f"❌ No memory profile found for {user.mention}.",
                    ephemeral=True
                )
                return
            
            facts = profile.get("creative_profile", {}).get("memorable_facts", [])
            
            embed = discord.Embed(
                title=f"🧠 Memory Profile: {user.display_name}",
                description=f"ID: {str(user.id)}",
                color=discord.Color.purple(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="Total Facts", value=str(len(facts)), inline=True)
            
            # Show confidence distribution
            high_conf = len([f for f in facts if f.get("confidence", 0) >= 0.8])
            med_conf = len([f for f in facts if 0.5 <= f.get("confidence", 0) < 0.8])
            low_conf = len([f for f in facts if f.get("confidence", 0) < 0.5])
            
            embed.add_field(name="High Confidence (≥0.8)", value=str(high_conf), inline=True)
            embed.add_field(name="Medium Confidence (0.5-0.8)", value=str(med_conf), inline=True)
            embed.add_field(name="Low Confidence (<0.5)", value=str(low_conf), inline=True)
            
            if facts:
                embed.add_field(
                    name="Sample Facts",
                    value="\n".join([f"• {f.get('text', 'Unknown')[:100]}" for f in facts[:3]]),
                    inline=False
                )
            
            embed.set_footer(text="Use /memory admin purge_user to delete this user's memories")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            if logger:
                logger.info(f"[🧠] Admin inspected {str(user.id)}'s profile: {len(facts)} facts")
        
        except Exception as e:
            if logger:
                logger.error(f"[🧠] Failed to inspect user memory: {e}")
            await interaction.followup.send(
                "❌ Failed to load memory profile. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="maintenance", description="Run memory system maintenance")
    @app_commands.default_permissions(administrator=True)
    async def admin_maintenance(self, interaction: discord.Interaction):
        """Trigger manual maintenance on memory system."""
        
        class MaintenanceModal(discord.ui.Modal, title="Memory Maintenance"):
            decay_threshold = discord.ui.TextInput(
                label="Decay threshold (days)",
                placeholder="7",
                default="7",
                required=True
            )
            prune_threshold = discord.ui.TextInput(
                label="Prune confidence threshold",
                placeholder="0.2",
                default="0.2",
                required=True
            )
            
            async def on_submit(self, modal_interaction: discord.Interaction):
                await modal_interaction.response.defer(ephemeral=True, thinking=True)
                
                try:
                    decay_days = int(self.decay_threshold)
                    prune_conf = float(self.prune_threshold)
                    guild_id = str(modal_interaction.guild.id) if modal_interaction.guild else None
                    
                    db = get_db()
                    
                    # Run maintenance
                    stats = run_maintenance(
                        storage_client=db.client,
                        db_name="Abby_Database",
                        decay_days_threshold=decay_days,
                        confidence_prune_threshold=prune_conf,
                        logger=logger
                    )
                    
                    # Create result embed
                    embed = discord.Embed(
                        title="✅ Maintenance Complete",
                        description="Memory system maintenance finished",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )
                    
                    embed.add_field(name="Profiles Processed", value=str(stats.get("profiles_processed", 0)), inline=True)
                    embed.add_field(name="Facts Decayed", value=str(stats.get("facts_decayed", 0)), inline=True)
                    embed.add_field(name="Facts Pruned", value=str(stats.get("facts_pruned", 0)), inline=True)
                    embed.add_field(name="Sessions Archived", value=str(stats.get("sessions_archived", 0)), inline=True)
                    embed.add_field(name="Caches Invalidated", value=str(stats.get("caches_invalidated", 0)), inline=True)
                    
                    if stats.get("errors"):
                        embed.add_field(
                            name="⚠️ Errors",
                            value=f"{len(stats['errors'])} error(s) occurred",
                            inline=False
                        )
                    
                    await modal_interaction.followup.send(embed=embed, ephemeral=True)
                    
                    if logger:
                        logger.info(f"[🧠] Maintenance completed: {stats}")
                
                except ValueError:
                    await modal_interaction.followup.send(
                        "❌ Invalid input. Please enter valid numbers.",
                        ephemeral=True
                    )
                except Exception as e:
                    if logger:
                        logger.error(f"[🧠] Maintenance failed: {e}")
                    await modal_interaction.followup.send(
                        "❌ Maintenance failed. Please try again later.",
                        ephemeral=True
                    )
        
        modal = MaintenanceModal()
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="purge_user", description="GDPR deletion of user memories")
    @app_commands.default_permissions(administrator=True)
    async def admin_purge_user(self, interaction: discord.Interaction, user: discord.User):
        """Permanently delete all memories for a user (GDPR)."""
        
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.confirmed = False
            
            @discord.ui.button(label="Permanently Delete", style=discord.ButtonStyle.danger)
            async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.confirmed = True
                await interaction.response.defer()
                self.stop()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.defer()
                self.stop()
        
        try:
            user_id = str(user.id)
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            view = ConfirmView()
            await interaction.response.send_message(
                f"⚠️ This will permanently delete ALL memories for {user.mention}. This cannot be undone. Are you sure?",
                view=view,
                ephemeral=True
            )
            
            await view.wait()
            
            if not view.confirmed:
                await interaction.followup.send("❌ Deletion cancelled.", ephemeral=True)
                return
            
            db = get_db()
            profiles_collection = db["discord_profiles"]
            
            # Delete all memories for user
            result = profiles_collection.update_one(
                {"user_id": user_id, "guild_id": guild_id},
                {"$set": {"creative_profile.memorable_facts": []}}
            )
            
            if result.modified_count > 0:
                # Invalidate cache
                memory.invalidate_cache(user_id, guild_id, source_id="discord")
                
                await interaction.followup.send(
                    f"✅ All memories for {user.mention} have been permanently deleted.",
                    ephemeral=True
                )
                
                if logger:
                    logger.info(f"[🧠] Admin permanently deleted memories for {user_id}")
            else:
                await interaction.followup.send(
                    f"ℹ️ No memories found for {user.mention}.",
                    ephemeral=True
                )
        
        except Exception as e:
            if logger:
                logger.error(f"[🧠] Failed to purge user memory: {e}")
            await interaction.followup.send(
                "❌ Failed to delete memories. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="export_guild", description="Export all guild memories")
    @app_commands.default_permissions(administrator=True)
    async def admin_export_guild(self, interaction: discord.Interaction):
        """Bulk export all memories in the guild."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            db = get_db()
            profiles_collection = db["discord_profiles"]
            
            profiles = list(profiles_collection.find({"guild_id": guild_id}))
            
            if not profiles:
                await interaction.followup.send(
                    "📭 No memory profiles found for this guild.",
                    ephemeral=True
                )
                return
            
            # Prepare export data
            export_data = {
                "guild_id": guild_id,
                "export_date": datetime.utcnow().isoformat(),
                "profile_count": len(profiles),
                "profiles": []
            }
            
            for profile in profiles:
                profile.pop("_id", None)
                facts = profile.get("creative_profile", {}).get("memorable_facts", [])
                
                export_data["profiles"].append({
                    "user_id": profile.get("user_id"),
                    "username": profile.get("username"),
                    "fact_count": len(facts),
                    "facts": facts
                })
            
            # Create JSON file
            json_str = json.dumps(export_data, indent=2, default=str)
            json_bytes = BytesIO(json_str.encode('utf-8'))
            
            file = discord.File(json_bytes, filename=f"abby_guild_memories_{guild_id}.json")
            await interaction.followup.send(
                content="📥 Guild memory export (confidential):",
                file=file,
                ephemeral=True
            )
            
            if logger:
                logger.info(f"[🧠] Admin exported {len(profiles)} profiles from guild {guild_id}")
        
        except Exception as e:
            if logger:
                logger.error(f"[🧠] Failed to export guild memories: {e}")
            await interaction.followup.send(
                "❌ Failed to export memories. Please try again later.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(MemoryCommands(bot))
    await bot.add_cog(MemoryAdmin(bot))

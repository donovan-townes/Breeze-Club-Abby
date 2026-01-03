"""
Server Configuration Commands

Admins can configure:
- Memory system (enable/disable, decay, extraction, storage)
- Channels (mod notifications, announcements)
- Personality (personality_number slider, active persona)
- Chat modes (one-shot vs multi-turn, mention vs slash summoning)
- Conversation settings (exchange ceiling, timeout)
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

try:
    from abby_core.database.mongodb import get_db
    from abby_core.database.memory_settings import get_memory_settings, set_memory_settings, get_guild_setting, set_guild_setting
    from abby_core.observability.logging import logging
except ImportError:
    logging = None

logger = logging.getLogger(__name__) if logging else None


class ServerConfig(commands.GroupCog, name="config"):
    """Configure Abby settings for your server."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()
        if logger:
            logger.info("[⚙️] Server Config Commands loaded")
    
    @app_commands.command(name="memory", description="[Admin] Configure memory system settings")
    @app_commands.default_permissions(administrator=True)
    async def config_memory(self, interaction: discord.Interaction):
        """Configure memory system via interactive view."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = int(interaction.guild.id) if interaction.guild else 0
            settings = get_memory_settings(guild_id)
            
            class MemoryConfigView(discord.ui.View):
                def __init__(self, parent):
                    super().__init__()
                    self.parent = parent
                
                @discord.ui.button(label="Enable Memory", style=discord.ButtonStyle.green if settings.get("enabled") else discord.ButtonStyle.grey)
                async def toggle_enabled(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer()
                    new_value = not settings.get("enabled", True)
                    set_memory_settings(guild_id, {"enabled": new_value})
                    await interaction.followup.send(
                        f"✅ Memory system {'enabled' if new_value else 'disabled'}",
                        ephemeral=True
                    )
                
                @discord.ui.button(label="Enable Decay", style=discord.ButtonStyle.green if settings.get("decay_enabled") else discord.ButtonStyle.grey)
                async def toggle_decay(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer()
                    new_value = not settings.get("decay_enabled", True)
                    set_memory_settings(guild_id, {"decay_enabled": new_value})
                    await interaction.followup.send(
                        f"✅ Memory decay {'enabled' if new_value else 'disabled'}",
                        ephemeral=True
                    )
                
                @discord.ui.button(label="Enable Extraction", style=discord.ButtonStyle.green if settings.get("extraction_enabled") else discord.ButtonStyle.grey)
                async def toggle_extraction(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer()
                    new_value = not settings.get("extraction_enabled", True)
                    set_memory_settings(guild_id, {"extraction_enabled": new_value})
                    await interaction.followup.send(
                        f"✅ Memory extraction {'enabled' if new_value else 'disabled'}",
                        ephemeral=True
                    )
                
                @discord.ui.button(label="Enable Storage", style=discord.ButtonStyle.green if settings.get("conversation_storage_enabled") else discord.ButtonStyle.grey)
                async def toggle_storage(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer()
                    new_value = not settings.get("conversation_storage_enabled", True)
                    set_memory_settings(guild_id, {"conversation_storage_enabled": new_value})
                    await interaction.followup.send(
                        f"✅ Conversation storage {'enabled' if new_value else 'disabled'}",
                        ephemeral=True
                    )
            
            embed = discord.Embed(
                title="⚙️ Memory System Configuration",
                description="Click buttons to toggle memory features",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="Current Settings",
                value=f"**Enabled:** {settings.get('enabled', True)}\n"
                      f"**Decay:** {settings.get('decay_enabled', True)}\n"
                      f"**Extraction:** {settings.get('extraction_enabled', True)}\n"
                      f"**Storage:** {settings.get('conversation_storage_enabled', True)}\n"
                      f"**Retention Days:** {settings.get('retention_days', 90)}\n"
                      f"**Confidence Threshold:** {settings.get('confidence_threshold', 0.3)}\n"
                      f"**Max Exchanges:** {settings.get('max_conversation_exchanges', 10)}",
                inline=False
            )
            
            embed.set_footer(text="Use other /config commands to adjust thresholds")
            
            view = MemoryConfigView(self)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            if logger:
                logger.info(f"[⚙️] Guild {guild_id} opened memory config")
        
        except Exception as e:
            if logger:
                logger.error(f"[⚙️] Config memory failed: {e}")
            await interaction.followup.send(
                "❌ Failed to load configuration. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="channels", description="[Admin] Configure notification channels")
    @app_commands.default_permissions(administrator=True)
    async def config_channels(self, interaction: discord.Interaction, mod_channel: discord.TextChannel = None, announcement_channel: discord.TextChannel = None):
        """Set mod and announcement channels."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = int(interaction.guild.id) if interaction.guild else 0
            updates = {}
            
            if mod_channel:
                updates["mod_channel_id"] = mod_channel.id
            
            if announcement_channel:
                updates["announcement_channel_id"] = announcement_channel.id
            
            if updates:
                set_memory_settings(guild_id, updates)
                
                message = "✅ Channels configured:\n"
                if mod_channel:
                    message += f"• Mod Channel: {mod_channel.mention}\n"
                if announcement_channel:
                    message += f"• Announcement Channel: {announcement_channel.mention}"
                
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.followup.send("ℹ️ No channels specified. Use the parameters to update channels.", ephemeral=True)
            
            if logger:
                logger.info(f"[⚙️] Guild {guild_id} updated channels: {updates}")
        
        except Exception as e:
            if logger:
                logger.error(f"[⚙️] Config channels failed: {e}")
            await interaction.followup.send(
                "❌ Failed to update channels. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="personality", description="[Admin] Adjust Abby's personality slider")
    @app_commands.default_permissions(administrator=True)
    async def config_personality(self, interaction: discord.Interaction, value: float = None):
        """Set personality number (0.0-1.0)."""
        
        if value is not None:
            if not 0.0 <= value <= 1.0:
                await interaction.response.send_message(
                    "❌ Personality value must be between 0.0 and 1.0",
                    ephemeral=True
                )
                return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = int(interaction.guild.id) if interaction.guild else 0
            db = get_db()
            bot_settings = db["bot_settings"]
            
            if value is not None:
                # Update personality
                bot_settings.update_one(
                    {"_id": "personality"},
                    {"$set": {"personality_number": value}},
                    upsert=True
                )
                
                await interaction.followup.send(
                    f"✅ Personality set to **{value}** (0=predictable, 1=random)",
                    ephemeral=True
                )
                
                if logger:
                    logger.info(f"[⚙️] Personality updated to {value}")
            else:
                # Show current value
                doc = bot_settings.find_one({"_id": "personality"})
                current = doc.get("personality_number", 0.6) if doc else 0.6
                
                await interaction.followup.send(
                    f"📊 Current personality: **{current}**\n"
                    f"(0.0 = predictable, 1.0 = very random)\n\n"
                    f"Use `/config personality value:<new_value>` to change",
                    ephemeral=True
                )
        
        except Exception as e:
            if logger:
                logger.error(f"[⚙️] Config personality failed: {e}")
            await interaction.followup.send(
                "❌ Failed to update personality. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="persona", description="[Admin] Switch active persona")
    @app_commands.default_permissions(administrator=True)
    async def config_persona(self, interaction: discord.Interaction):
        """Switch Abby's persona with interactive selector."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            db = get_db()
            bot_settings = db["bot_settings"]
            
            # Get all personas
            personas_docs = list(bot_settings.find({"_id": {"$in": ["bunny", "kiki", "owl", "fox", "squirrel", "panda"]}}))
            personas = [doc.get("_id") for doc in personas_docs]
            
            if not personas:
                personas = ["bunny", "kiki"]  # Fallback
            
            class PersonaSelect(discord.ui.Select):
                def __init__(self, cog):
                    super().__init__(
                        placeholder="Select a persona...",
                        min_values=1,
                        max_values=1,
                        options=[
                            discord.SelectOption(label=p.capitalize(), value=p)
                            for p in personas
                        ]
                    )
                    self.cog = cog
                
                async def callback(self, interaction: discord.Interaction):
                    selected_persona = self.values[0]
                    
                    # Update active persona
                    bot_settings.update_one(
                        {"_id": "active_persona"},
                        {"$set": {"active_persona": selected_persona}},
                        upsert=True
                    )
                    
                    await interaction.response.defer()
                    await interaction.followup.send(
                        f"✅ Active persona changed to **{selected_persona.upper()}**\n\n"
                        f"💡 *Note: Memories persist across persona switches. "
                        f"Your facts about users remain valid regardless of which persona Abby is using.*",
                        ephemeral=True
                    )
                    
                    if logger:
                        logger.info(f"[⚙️] Persona switched to {selected_persona}")
            
            # Get current persona
            current_doc = bot_settings.find_one({"_id": "active_persona"})
            current = current_doc.get("active_persona", "bunny") if current_doc else "bunny"
            
            embed = discord.Embed(
                title="🎭 Select Active Persona",
                description=f"Current: **{current.upper()}**\n\n"
                           f"Memories persist across personas - personality switches but facts remain.",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            view = discord.ui.View()
            view.add_item(PersonaSelect(self))
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            if logger:
                logger.info(f"[⚙️] Guild opened persona selector, current: {current}")
        
        except Exception as e:
            if logger:
                logger.error(f"[⚙️] Config persona failed: {e}")
            await interaction.followup.send(
                "❌ Failed to load personas. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="timeouts", description="[Admin] Configure conversation timeouts and exchanges")
    @app_commands.default_permissions(administrator=True)
    async def config_timeouts(self, interaction: discord.Interaction, exchange_ceiling: int = None, retention_days: int = None):
        """Configure conversation timing."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = int(interaction.guild.id) if interaction.guild else 0
            settings = get_memory_settings(guild_id)
            updates = {}
            
            if exchange_ceiling is not None:
                if exchange_ceiling < 1 or exchange_ceiling > 50:
                    await interaction.followup.send(
                        "❌ Exchange ceiling must be between 1 and 50",
                        ephemeral=True
                    )
                    return
                updates["max_conversation_exchanges"] = exchange_ceiling
            
            if retention_days is not None:
                if retention_days < 7 or retention_days > 365:
                    await interaction.followup.send(
                        "❌ Retention days must be between 7 and 365",
                        ephemeral=True
                    )
                    return
                updates["retention_days"] = retention_days
            
            if updates:
                set_memory_settings(guild_id, updates)
                
                message = "✅ Timeouts configured:\n"
                if exchange_ceiling is not None:
                    message += f"• Max Exchanges: {exchange_ceiling}\n"
                if retention_days is not None:
                    message += f"• Retention: {retention_days} days"
                
                await interaction.followup.send(message, ephemeral=True)
            else:
                message = f"📊 Current Configuration:\n" \
                         f"• Max Exchanges: {settings.get('max_conversation_exchanges', 10)}\n" \
                         f"• Retention Days: {settings.get('retention_days', 90)}\n" \
                         f"• Conversation Timeout: 60 seconds (fixed)\n\n" \
                         f"Use parameters to change settings."
                await interaction.followup.send(message, ephemeral=True)
            
            if logger:
                logger.info(f"[⚙️] Guild {guild_id} updated timeouts: {updates}")
        
        except Exception as e:
            if logger:
                logger.error(f"[⚙️] Config timeouts failed: {e}")
            await interaction.followup.send(
                "❌ Failed to update timeouts. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="summoning", description="[Admin] Configure how Abby is summoned")
    @app_commands.default_permissions(administrator=True)
    async def config_summoning(self, interaction: discord.Interaction):
        """Configure summoning mode (mention vs slash)."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = int(interaction.guild.id) if interaction.guild else 0
            settings = get_memory_settings(guild_id)
            current_mode = settings.get("summon_mode", "both")
            
            class SummonModeSelect(discord.ui.Select):
                def __init__(self, cog):
                    super().__init__(
                        placeholder="Select summoning method...",
                        min_values=1,
                        max_values=1,
                        options=[
                            discord.SelectOption(label="Mention Only (hey abby)", value="mention_only"),
                            discord.SelectOption(label="Slash Only (/chat)", value="slash_only"),
                            discord.SelectOption(label="Both Methods", value="both"),
                        ]
                    )
                    self.cog = cog
                
                async def callback(self, interaction: discord.Interaction):
                    mode = self.values[0]
                    set_memory_settings(guild_id, {"summon_mode": mode})
                    
                    mode_names = {
                        "mention_only": "Mention Only (hey abby)",
                        "slash_only": "Slash Only (/chat)",
                        "both": "Both Methods"
                    }
                    
                    await interaction.response.defer()
                    await interaction.followup.send(
                        f"✅ Summoning mode changed to **{mode_names[mode]}**",
                        ephemeral=True
                    )
                    
                    if logger:
                        logger.info(f"[⚙️] Summoning mode changed to {mode}")
            
            embed = discord.Embed(
                title="🔔 Summoning Configuration",
                description=f"Current Mode: **{current_mode.replace('_', ' ').title()}**\n\n"
                           f"Choose how users can summon Abby:",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="Mention Only",
                value="Users say 'hey abby' in chat\n(natural, discoverable)",
                inline=True
            )
            
            embed.add_field(
                name="Slash Only",
                value="Users use /chat command\n(explicit, official)",
                inline=True
            )
            
            embed.add_field(
                name="Both",
                value="Both methods available\n(most flexible)",
                inline=True
            )
            
            view = discord.ui.View()
            view.add_item(SummonModeSelect(self))
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            if logger:
                logger.info(f"[⚙️] Guild {guild_id} opened summoning config")
        
        except Exception as e:
            if logger:
                logger.error(f"[⚙️] Config summoning failed: {e}")
            await interaction.followup.send(
                "❌ Failed to load summoning config. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="chat_mode", description="[Admin] Configure default chat behavior")
    @app_commands.default_permissions(administrator=True)
    async def config_chat_mode(self, interaction: discord.Interaction):
        """Configure default chat mode (one-shot vs multi-turn)."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = int(interaction.guild.id) if interaction.guild else 0
            settings = get_memory_settings(guild_id)
            current_mode = settings.get("default_chat_mode", "multi_turn")
            
            class ChatModeSelect(discord.ui.Select):
                def __init__(self, cog):
                    super().__init__(
                        placeholder="Select chat behavior...",
                        min_values=1,
                        max_values=1,
                        options=[
                            discord.SelectOption(label="One-Shot (Single Response)", value="one_shot"),
                            discord.SelectOption(label="Multi-Turn (Conversation Loop)", value="multi_turn"),
                        ]
                    )
                    self.cog = cog
                
                async def callback(self, interaction: discord.Interaction):
                    mode = self.values[0]
                    set_memory_settings(guild_id, {"default_chat_mode": mode})
                    
                    mode_names = {
                        "one_shot": "One-Shot (Single Response)",
                        "multi_turn": "Multi-Turn (Conversation Loop)",
                    }
                    
                    await interaction.response.defer()
                    await interaction.followup.send(
                        f"✅ Default chat mode changed to **{mode_names[mode]}**",
                        ephemeral=True
                    )
                    
                    if logger:
                        logger.info(f"[⚙️] Chat mode changed to {mode}")
            
            embed = discord.Embed(
                title="💬 Chat Mode Configuration",
                description=f"Current Mode: **{current_mode.replace('_', ' ').title()}**",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="One-Shot Mode",
                value="**Abby responds once and stops.**\n"
                     "• Single response per message\n"
                     "• Quick Q&A style\n"
                     "• Best for quick questions",
                inline=True
            )
            
            embed.add_field(
                name="Multi-Turn Mode",
                value="**Abby engages in conversation.**\n"
                     "• Continues until user dismisses\n"
                     "• Build on previous messages\n"
                     "• Best for discussions",
                inline=True
            )
            
            view = discord.ui.View()
            view.add_item(ChatModeSelect(self))
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            if logger:
                logger.info(f"[⚙️] Guild {guild_id} opened chat mode config")
        
        except Exception as e:
            if logger:
                logger.error(f"[⚙️] Config chat mode failed: {e}")
            await interaction.followup.send(
                "❌ Failed to load chat mode config. Please try again later.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerConfig(bot))

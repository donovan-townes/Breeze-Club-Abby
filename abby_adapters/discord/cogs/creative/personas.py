"""
Slash command for persona/character management
Enables users to switch between different bot personas (Abby, Kiki, etc.)
"""
import discord
from discord.ext import commands
from discord import app_commands
from abby_core.llm.persona import (
    update_persona,
    get_persona,
    get_persona_by_name,
    get_all_personas
)
from abby_core.personality import reload_persona
from abby_core.observability.logging import logging
from abby_core.database import mongodb as mongo_db
from pathlib import Path

logger = logging.getLogger(__name__)


class PersonaCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.persona_config = {
            'bunny': {'nick': '🐰 Abby', 'emoji': '🐰', 'color': discord.Color.blue()},
            'kiki': {'nick': '🐱 Kiki', 'emoji': '🐱', 'color': discord.Color.from_rgb(255, 182, 193)},
            'kitten': {'nick': '🐱 Kiki', 'emoji': '🐱', 'color': discord.Color.from_rgb(255, 182, 193)},
            'felix': {'nick': '🦊 Felix', 'emoji': '🦊', 'color': discord.Color.orange()},
            'owl': {'nick': '🦉 Oliver', 'emoji': '🦉', 'color': discord.Color.from_rgb(139, 69, 19)},
            'squirrel': {'nick': '🐿️ Sammy', 'emoji': '🐿️', 'color': discord.Color.from_rgb(160, 82, 45)},
            'panda': {'nick': '🐼 Paddy', 'emoji': '🐼', 'color': discord.Color.dark_gray()}
        }
        logger.info("[🎭] Persona slash commands loaded")
    
    async def cog_unload(self):
        """Called when cog is unloaded - remove command group from tree."""
        self.bot.tree.remove_command(self.persona_group.name)
        logger.info("[🎭] Persona command group removed from tree")
    
    def ensure_persona_exists(self, persona_name: str) -> bool:
        """Ensure a persona exists in the database. Create stub if missing."""
        existing = get_persona_by_name(persona_name)
        if existing is not None:
            return True
        
        # Check if persona directory exists in filesystem
        persona_dir = Path(__file__).parent.parent.parent.parent.parent / "abby_core" / "personality" / persona_name
        if not persona_dir.exists():
            logger.warning(f"[⚠️] Persona directory not found: {persona_dir}")
            return False
        
        # Load personality description from response_patterns.json if it exists
        config = self.persona_config.get(persona_name, {'nick': persona_name.capitalize(), 'emoji': '🤖'})
        persona_description = f"{config['emoji']} {config['nick']}"
        
        # Try to load traits from response_patterns.json
        response_patterns_file = persona_dir / "response_patterns.json"
        if response_patterns_file.exists():
            try:
                import json
                with open(response_patterns_file, 'r', encoding='utf-8') as f:
                    patterns = json.load(f)
                    # Build rich personality description
                    traits = patterns.get('personality_traits', {})
                    if traits:
                        trait_desc = traits.get('description', '')
                        if trait_desc:
                            persona_description = trait_desc
                        else:
                            # Fallback: generate from traits
                            persona_description = f"{config['emoji']} {config['nick']} - A playful {persona_name} assistant!"
                    else:
                        persona_description = f"{config['emoji']} {config['nick']} - A friendly {persona_name} assistant"
            except Exception as e:
                logger.warning(f"[⚠️] Could not load personality traits from {response_patterns_file}: {e}")
                persona_description = f"{config['emoji']} {config['nick']} - A friendly assistant persona"
        
        # Create entry in MongoDB with loaded personality
        try:
            client = mongo_db.connect_to_mongodb()
            db = client["Abby_Database"]
            collection = db["bot_settings"]
            collection.insert_one({
                "_id": persona_name,
                "persona_message": persona_description,
                "created_at": "auto-generated",
                "status": "active"
            })
            logger.info(f"[🎭] Auto-created persona entry for '{persona_name}' with personality from config files")
            return True
        except Exception as e:
            logger.error(f"[❌] Failed to create persona stub: {e}")
            return False

    persona_group = app_commands.Group(name="persona", description="Manage bot personas")

    @persona_group.command(name="list", description="List all available personas")
    @app_commands.checks.has_permissions(administrator=True)
    async def persona_list(self, interaction: discord.Interaction):
        """List all available personas."""
        await interaction.response.defer()
        personas = get_all_personas()
        
        if personas:
            persona_list = []
            current_persona = get_persona()
            current_id = current_persona.get('active_persona') if current_persona else None
            
            for p in personas:
                persona_id = p.get('_id', 'unknown')
                if persona_id != 'active_persona':
                    config = self.persona_config.get(persona_id, {'emoji': '🤖'})
                    is_current = "✨ " if persona_id == current_id else ""
                    persona_list.append(f"{is_current}{config['emoji']} **{persona_id.capitalize()}**")
            
            embed = discord.Embed(
                title="🎭 Available Personas",
                description="\n".join(persona_list) if persona_list else "No personas found",
                color=discord.Color.purple()
            )
            embed.set_footer(text="Use /persona switch to change persona")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ No personas found in database.")

    @persona_group.command(name="switch", description="Switch to a different persona")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(persona="Select a persona to switch to")
    @app_commands.choices(persona=[
        app_commands.Choice(name="🐰 Abby (Bunny)", value="bunny"),
        app_commands.Choice(name="🐱 Kiki (Kitten)", value="kiki"),
        app_commands.Choice(name="🦊 Felix (Fox)", value="felix"),
        app_commands.Choice(name="🦉 Oliver (Owl)", value="owl"),
        app_commands.Choice(name="🐿️ Sammy (Squirrel)", value="squirrel"),
        app_commands.Choice(name="🐼 Paddy (Panda)", value="panda"),
    ])
    async def persona_switch(self, interaction: discord.Interaction, persona: str):
        """Switch to a different persona."""
        await interaction.response.defer()
        
        persona_name = persona.lower()
        
        # Ensure persona exists (auto-create stub if missing)
        if not self.ensure_persona_exists(persona_name):
            config = self.persona_config.get(persona_name, {'nick': persona_name, 'emoji': '🤖'})
            await interaction.followup.send(
                f"❌ {config['emoji']} **{config['nick']}** is not available yet.\n"
                f"The personality files may not be set up. Please check `abby_core/personality/{persona_name}/`",
                ephemeral=True
            )
            return
        
        # Check if already active
        current_persona = get_persona()
        if current_persona and current_persona.get('active_persona') == persona_name:
            config = self.persona_config.get(persona_name, {'nick': persona_name})
            await interaction.followup.send(f"✅ Already using **{config['nick']}**!", ephemeral=True)
            return
        
        # Update persona in database
        update_persona(persona_name)
        
        # Reload personality config in-memory
        reload_persona(persona_name)
        
        # Get persona configuration
        config = self.persona_config.get(persona_name, {'nick': persona_name, 'emoji': '🤖', 'color': discord.Color.default()})
        
        try:
            # Update bot nickname in guild
            await interaction.guild.me.edit(nick=config['nick'])
            logger.info(f"[🎭] Updated bot nickname to '{config['nick']}'")
        except discord.Forbidden:
            logger.warning(f"[⚠️] Cannot update bot nickname - missing permissions")
        except Exception as e:
            logger.error(f"[❌] Error updating bot nickname: {e}")
        
        # Send confirmation
        embed = discord.Embed(
            title="🎭 Persona Updated",
            description=f"Successfully switched to **{config['nick']}**!",
            color=config['color']
        )
        embed.set_footer(text=f"Persona: {persona_name}")
        await interaction.followup.send(embed=embed)
        
        logger.info(f"[🎭] Persona switched to '{persona_name}' by {interaction.user.name}")

    @persona_group.command(name="current", description="Show the currently active persona")
    @app_commands.checks.has_permissions(administrator=True)
    async def persona_current(self, interaction: discord.Interaction):
        """Show currently active persona."""
        await interaction.response.defer()
        current = get_persona()
        
        if current:
            persona_name = current.get('active_persona', 'unknown')
            config = self.persona_config.get(persona_name, {'nick': persona_name, 'emoji': '🤖', 'color': discord.Color.default()})
            
            embed = discord.Embed(
                title=f"🎭 Active Persona",
                description=f"{config['emoji']} **{config['nick']}**",
                color=config['color']
            )
            embed.add_field(name="Persona ID", value=f"`{persona_name}`", inline=True)
            embed.set_footer(text="Use /persona switch to change")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ No active persona found.", ephemeral=True)
    
    @persona_group.command(name="refresh", description="Refresh a persona's database entry from config files")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(persona="Select a persona to refresh")
    @app_commands.choices(persona=[
        app_commands.Choice(name="🐰 Abby (Bunny)", value="bunny"),
        app_commands.Choice(name="🐱 Kiki (Kitten)", value="kiki"),
        app_commands.Choice(name="🦊 Felix (Fox)", value="felix"),
        app_commands.Choice(name="🦉 Oliver (Owl)", value="owl"),
        app_commands.Choice(name="🐿️ Sammy (Squirrel)", value="squirrel"),
        app_commands.Choice(name="🐼 Paddy (Panda)", value="panda"),
    ])
    async def persona_refresh(self, interaction: discord.Interaction, persona: str):
        """Refresh a persona's database entry from config files."""
        await interaction.response.defer(ephemeral=True)
        
        persona_name = persona.lower()
        config = self.persona_config.get(persona_name, {'nick': persona_name, 'emoji': '🤖'})
        
        # Check if persona directory exists
        persona_dir = Path(__file__).parent.parent.parent.parent.parent / "abby_core" / "personality" / persona_name
        if not persona_dir.exists():
            await interaction.followup.send(
                f"❌ Persona directory not found: `abby_core/personality/{persona_name}/`",
                ephemeral=True
            )
            return
        
        # Load personality from response_patterns.json
        response_patterns_file = persona_dir / "response_patterns.json"
        persona_description = f"{config['emoji']} {config['nick']} - A friendly {persona_name} assistant"
        
        if response_patterns_file.exists():
            try:
                import json
                with open(response_patterns_file, 'r', encoding='utf-8') as f:
                    patterns = json.load(f)
                    traits = patterns.get('personality_traits', {})
                    if traits and 'description' in traits:
                        persona_description = traits['description']
                    logger.info(f"[🎭] Loaded personality for {persona_name}: {persona_description[:100]}...")
            except Exception as e:
                logger.error(f"[❌] Error loading personality: {e}")
                await interaction.followup.send(f"❌ Error loading personality: {e}", ephemeral=True)
                return
        
        # Update or create in MongoDB
        try:
            client = mongo_db.connect_to_mongodb()
            db = client["Abby_Database"]
            collection = db["bot_settings"]
            
            # Delete old entry if exists
            collection.delete_one({"_id": persona_name})
            
            # Insert new entry with full personality
            collection.insert_one({
                "_id": persona_name,
                "persona_message": persona_description,
                "created_at": "refreshed",
                "status": "active"
            })
            
            embed = discord.Embed(
                title="🔄 Persona Refreshed",
                description=f"Successfully refreshed **{config['nick']}** from config files!",
                color=discord.Color.green()
            )
            embed.add_field(name="Personality Loaded", value=persona_description[:200] + "...", inline=False)
            embed.set_footer(text=f"Persona: {persona_name}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            logger.info(f"[🎭] Refreshed persona '{persona_name}' in database")
            
        except Exception as e:
            logger.error(f"[❌] Failed to refresh persona: {e}")
            await interaction.followup.send(f"❌ Failed to refresh: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Load the persona commands cog."""
    await bot.add_cog(PersonaCommands(bot))

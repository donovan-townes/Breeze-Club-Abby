# Cogs Directory Structure

This directory contains all Discord bot commands organized by feature category.

## Directory Organization

```
cogs/
├── admin/          # Server & bot management (requires elevated permissions)
├── economy/        # XP, levels, and economy features
├── entertainment/  # Games, giveaways, polls, fun content
├── creative/       # AI-powered features (chatbot, images, personas)
├── community/      # Social features (welcomes, announcements, MOTD)
├── integrations/   # External service integrations (Twitch, Twitter, etc.)
├── music/          # Audio and voice features (radio, music playback)
└── utility/        # General utility commands (help, profile, status)
```

## Cog Categories

### Admin (`cogs/admin/`)

**Purpose:** Server and bot management commands requiring elevated permissions

**Files:**

- `rag.py` - RAG (Retrieval Augmented Generation) system management
- `shutdown.py` - Bot shutdown and restart commands
- `reload.py` - Hot-reload cogs without restart
- `moderation.py` - User moderation tools

**Key Commands:**

- `/rag add`, `/rag search`, `/rag stats` - Manage knowledge base
- `!shutdown`, `!restart` - Bot control (prefix commands)
- `!reload <cog>` - Reload specific cog
- Moderation commands (kick, ban, timeout, etc.)

### Economy (`cogs/economy/`)

**Purpose:** XP, leveling, and economy features

**Files:**

- `experience.py` - Unified XP/level system (formerly exp_commands.py)
- `xp_gain.py` - Automatic XP gain from messages

**Key Commands:**

- `/exp` - Check your XP and level
- `/level` - View detailed level progress
- `/leaderboard` - Server XP rankings
- `/exp-admin give/take/set/reset` - Admin XP management

### Entertainment (`cogs/entertainment/`)

**Purpose:** Games, giveaways, polls, and fun interactive features

**Files:**

- `games.py` - Interactive games with button UI
- `giveaways.py` - Giveaway system with button entry
- `polls.py` - Poll creation and voting
- `memes.py` - Meme generation
- `reddit.py` - Reddit content integration
- `generators.py` - Random content generators

**Key Commands:**

- `/game emoji` - Emoji guessing game (daily at 8 AM)
- `/giveaway create/end/list` - Manage giveaways
- `/poll create` - Create interactive polls

### Creative (`cogs/creative/`)

**Purpose:** AI-powered creative features

**Files:**

- `images.py` - AI image generation (DALL-E)
- `chatbot.py` - Conversational AI integration
- `analyze.py` - Message sentiment and content analysis
- `personas.py` - AI personality switching

**Key Commands:**

- `/imagine` - Generate images from prompts
- `/persona list/select` - Switch AI personalities
- Natural conversation with @mentions

### Community (`cogs/community/`)

**Purpose:** Social features and server engagement

**Files:**

- `welcome.py` - Welcome messages for new members
- `motd.py` - Message of the Day system
- `announcements.py` - Server announcements

**Key Commands:**

- Automatic welcome messages
- `/motd` - View/set message of the day
- `/announce` - Create announcements

### Integrations (`cogs/integrations/`)

**Purpose:** External service integrations

**Files:**

- `twitch.py` - Twitch stream notifications
- `twitter.py` - Twitter feed integration

**Key Commands:**

- `/twitch track/untrack/list` - Monitor Twitch streams
- Twitter auto-posting and monitoring

### Music (`cogs/music/`)

**Purpose:** Audio and voice channel features

**Files:**

- (To be migrated from commands/Radio/ and commands/Music/)

**Planned Commands:**

- Radio streaming
- Music playback
- Voice channel utilities

### Utility (`cogs/utility/`)

**Purpose:** General utility commands for all users

**Files:**

- `user_commands.py` - User-facing utilities
- `reminders.py` - Reminder system
- `info.py` - Server and user info commands
- `status.py` - Bot status and uptime

**Key Commands:**

- `/suggest` - Submit suggestions via modal
- `/help` - Interactive help menu
- `/profile` - View user profile
- `/remind` - Set reminders
- `/info server/user` - View information
- `/status` - Bot status and stats

## Adding New Cogs

### 1. Choose the Right Category

Place your cog in the category that best matches its primary function:

- **Admin** - Requires elevated permissions, bot/server management
- **Economy** - XP, currency, trading, leveling
- **Entertainment** - Games, fun activities, giveaways
- **Creative** - AI features, content generation
- **Community** - Social engagement, welcomes, events
- **Integrations** - External APIs and services
- **Music** - Audio, voice, streaming
- **Utility** - General tools, information commands

### 2. Create Your Cog File

```python
from discord.ext import commands
from discord import app_commands
import discord

class MyCog(commands.Cog):
    """Description of your cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="mycommand")
    async def my_command(self, interaction: discord.Interaction):
        """Command description"""
        await interaction.response.send_message("Hello!")

async def setup(bot: commands.Bot):
    await bot.add_cog(MyCog(bot))
```

### 3. Reload Automatically

The command loader (`handlers/command_loader.py`) automatically discovers and loads all cogs in subdirectories. No manual registration required!

## Migration Notes

### Old Structure → New Structure

```
commands/Admin/exp.py          → cogs/economy/experience.py (DEPRECATED)
cogs/Exp/exp_cog.py            → cogs/economy/experience.py (CONSOLIDATED)
cogs/Exp/leaderboard.py        → cogs/economy/experience.py (CONSOLIDATED)
cogs/Fun/giveaway.py           → cogs/entertainment/giveaways.py (MODERNIZED)
cogs/Fun/emoji.py              → cogs/entertainment/games.py (MODERNIZED)
commands/User/user_commands.py → cogs/utility/user_commands.py (MODERNIZED)
```

### Deprecated Folders

The following folders are deprecated and will be removed after verification:

- `commands/` - All modern commands moved to `cogs/`
- Old scattered files in `cogs/` root - Moved to category subdirectories

## Best Practices

### 1. Use Modern Slash Commands

```python
@app_commands.command(name="example")
async def example(self, interaction: discord.Interaction):
    await interaction.response.send_message("Modern!")
```

### 2. Leverage Discord UI Components

- **Modals** for forms and multi-field input
- **Buttons** for confirmations and interactions
- **Select Menus** for multiple choice selections
- **Embeds** for rich, formatted output

### 3. Import from Config

```python
from abby_adapters.discord.config import BotConfig

config = BotConfig.from_env()
# Use config.discord.channels.log_channel_id, etc.
```

### 4. Use Type Hints

```python
async def my_command(
    self,
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int
) -> None:
    ...
```

### 5. Handle Errors Gracefully

```python
try:
    await interaction.response.send_message("Success!")
except discord.errors.NotFound:
    # Interaction expired
    pass
```

## Testing New Cogs

1. **Reload Without Restart:**

   ```
   !reload cog_name
   ```

2. **Sync Slash Commands:**

   ```
   !sync ~
   ```

3. **Check Logs:**
   - Look in `logs/` directory for errors
   - Check console output for stack traces

## Architecture Notes

### Why Categories?

- **Maintainability:** Easier to find and update related features
- **Team Collaboration:** Clear ownership boundaries
- **Loading Performance:** Can lazy-load categories if needed
- **Mental Model:** Logical grouping matches user expectations

### Why Cogs Over Functions?

- **State Management:** Cogs can maintain instance variables
- **Event Handlers:** Can listen to Discord events (on_message, on_member_join)
- **Lifecycle Hooks:** setup() and teardown() for initialization
- **Hot Reload:** Can reload individual cogs without bot restart

### Command Loader Magic

The command loader in `handlers/command_loader.py` recursively scans the `cogs/` directory and loads any Python file with a `setup()` function. This means:

- No manual cog registration
- Add files and they're automatically discovered
- Subdirectories are fully supported
- Old structure still works during migration

## See Also

- [COMMAND_MODERNIZATION.md](../../../COMMAND_MODERNIZATION.md) - Full command audit and migration status
- [MODERNIZATION_GUIDE.md](../../../MODERNIZATION_GUIDE.md) - Quick reference for modernizing commands
- [config.py](../config.py) - Centralized configuration system

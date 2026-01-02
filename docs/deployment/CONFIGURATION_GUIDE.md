# Configuration Migration Guide

## Overview

Abby's configuration system has been centralized and externalized for easier deployment to new servers. This guide explains how to customize Abby for your own Discord server.

## Quick Start for New Owners

### 1. Environment Variables (.env)

Copy `.env.example` to `.env` and configure:

```env
# Discord Bot Token (REQUIRED)
ABBY_TOKEN=your_discord_bot_token_here

# API Keys
OPENAI_API_KEY=your_openai_key
STABILITY_API_KEY=your_stability_key

# MongoDB (if using database features)
MONGODB_URI=mongodb://localhost:27017
MONGODB_USER=admin
MONGODB_PASS=password
```

### 2. Channel IDs (config.py)

Update [config.py](abby_adapters/discord/config.py) with your server's channel IDs:

```python
@dataclass
class DiscordChannels:
    """Discord Channel IDs - Customize for your server"""
    # Main channels
    breeze_lounge: int = 802512963519905852  # ← Change this
    abby_chat: int = 1103490012500201632     # ← Change this
    breeze_memes: int = 1111136459072753664  # ← Change this
    gust_channel: int = 802461884091465748   # ← Change this
    # ... more channels ...
```

**How to get Channel IDs:**

1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click any channel → Copy ID
3. Paste into config.py

### 3. Role IDs (config.py)

Update role IDs for your server:

```python
@dataclass
class DiscordRoles:
    """Discord Role IDs - Customize for your server"""
    musician: int = 808129993460023366     # ← Change this
    streamer: int = 1131231727675768953    # ← Change this
    gamer: int = 1131920998350995548       # ← Change this
    # ... more roles ...
```

**How to get Role IDs:**

1. Type `\@RoleName` in Discord (with backslash)
2. Copy the number from the output: `<@&808129993460023366>`
3. Paste into config.py

### 4. Welcome Messages (welcome_phrases.json)

Customize welcome messages for your community:

**File:** [abby_adapters/discord/data/welcome_phrases.json](abby_adapters/discord/data/welcome_phrases.json)

```json
{
  "phrases": [
    "Welcome to OurServer! We're happy to have you here!",
    "Hey there! Feel free to introduce yourself!",
    "Great to meet you! Jump into the conversation!"
  ]
}
```

Replace "Z8phyR" references with your server owner's name.

### 5. Custom Emojis (config.py)

Update custom emoji IDs for your server:

```python
@dataclass
class DiscordEmojis:
    """Discord Custom Emojis - Customize for your server"""
    leaf_heart: str = "<a:z8_leafheart_excited:806057904431693824>"  # ← Change this
    up_arrow: str = "⬆️"     # Standard emoji
    down_arrow: str = "⬇️"   # Standard emoji
```

**How to get Custom Emoji IDs:**

1. Type `\:emojiname:` in Discord
2. Copy the full string: `<a:name:123456789>`
3. Paste into config.py

---

## Configuration Structure

### Centralized Config (config.py)

All configuration is now in one place:

```python
from abby_adapters.discord.config import config

# Access channels
channel_id = config.channels.breeze_lounge

# Access roles
role_id = config.roles.musician

# Access emojis
emoji = config.emojis.leaf_heart

# Access API keys
api_key = config.api.openai_key

# Load welcome phrases
phrases = config.load_welcome_phrases()
```

### Configuration Classes

| Class             | Purpose                 | Example                                |
| ----------------- | ----------------------- | -------------------------------------- |
| `DiscordChannels` | Channel IDs             | `config.channels.breeze_lounge`        |
| `DiscordRoles`    | Role IDs                | `config.roles.musician`                |
| `DiscordEmojis`   | Custom emojis           | `config.emojis.leaf_heart`             |
| `APIKeys`         | External API keys       | `config.api.openai_key`                |
| `DatabaseConfig`  | MongoDB/Qdrant          | `config.database.mongodb_uri`          |
| `StorageConfig`   | File storage            | `config.storage.max_global_storage_mb` |
| `FeatureFlags`    | Enable/disable features | `config.features.rag_enabled`          |

---

## Migration from Hardcoded Values

### Before (Hardcoded in cog files)

```python
# Old way - hardcoded
DAILY_GUST = 802461884091465748
roles = {
    "Musician": 808129993460023366,
    "Streamer": 1131231727675768953
}
phrases = ["Welcome!", "Hello!"]
```

### After (Centralized config)

```python
# New way - centralized
from abby_adapters.discord.config import config

channel = config.channels.gust_channel
role = config.roles.musician
phrases = config.load_welcome_phrases()
```

---

## Logging Changes

### JSONL-Only Output

Abby now outputs **structured JSONL logs only** (no more text logs):

**File:** `logs/abby.jsonl`

Each line is a JSON object:

```json
{
  "timestamp": "2026-01-01T23:18:50Z",
  "level": "INFO",
  "logger": "Main",
  "message": "Startup complete",
  "phase": "COMPLETE",
  "metrics": { "cog_count": 28, "startup_duration_seconds": 0.5 }
}
```

### Moving to Shared Events

To integrate with TDOS telemetry, symlink or move logs:

```bash
# Linux/Mac
ln -s /path/to/abby/logs/abby.jsonl /opt/tdos/shared/logs/abby.jsonl

# Windows (PowerShell as Admin)
New-Item -ItemType SymbolicLink -Path "C:\opt\tdos\shared\logs\abby.jsonl" -Target "C:\Abby_Discord_Latest\logs\abby.jsonl"
```

Or update `config.py`:

```python
@dataclass
class PathConfig:
    # Redirect logs to shared folder
    tdos_events_path: Path = Path("C:/opt/tdos/shared/logs/events.jsonl")
```

---

## Testing Your Configuration

Run the configuration validator:

```bash
python -m abby_adapters.discord.config
```

Output will show:

```
🐰 ABBY DISCORD BOT CONFIGURATION
============================
📂 Paths:
  Working Dir: C:\Abby_Discord_Latest
  ...
✅ Configuration Valid
```

Or check for issues:

```python
from abby_adapters.discord.config import config

issues = config.validate()
if issues:
    for issue in issues:
        print(issue)
```

---

## Common Customizations

### Changing Server Name

1. Update [welcome_phrases.json](abby_adapters/discord/data/welcome_phrases.json)
2. Replace "Breeze Club" with your server name
3. Replace "Z8phyR" with your owner name

### Adding New Channels

```python
# In config.py
@dataclass
class DiscordChannels:
    # ... existing channels ...

    # Add your new channel
    my_custom_channel: int = 123456789012345
```

Then use in cogs:

```python
channel = guild.get_channel(config.channels.my_custom_channel)
```

### Adding New Roles

```python
# In config.py
@dataclass
class DiscordRoles:
    # ... existing roles ...

    # Add your new role
    my_custom_role: int = 987654321098765
```

### Disabling Features

```python
# In .env or config.py
RAG_CONTEXT_ENABLED=false
NUDGE_ENABLED=false
IMAGE_AUTO_MOVE_ENABLED=false
```

---

## Benefits of Centralized Config

✅ **No hardcoded values in cog files**  
✅ **Easy to customize for new servers**  
✅ **Change channel IDs without editing code**  
✅ **Version control friendly** (`.env` in `.gitignore`)  
✅ **Validation on startup**  
✅ **Type-safe with dataclasses**

---

## Troubleshooting

### "Channel not found" errors

Check that channel IDs in `config.py` match your server:

```python
config.print_summary()  # Shows all configured channels
```

### "Role not found" errors

Verify role IDs are correct for your server. Remember: role IDs are server-specific.

### Welcome messages not loading

Ensure `welcome_phrases.json` exists at:

```
abby_adapters/discord/data/welcome_phrases.json
```

### Bot can't start

Run configuration validator:

```bash
python -m abby_adapters.discord.config
```

Check for `❌ CRITICAL` errors.

---

## Support

For questions or issues with configuration:

1. Check `logs/abby.jsonl` for structured error logs
2. Run `config.print_summary()` to verify settings
3. Ensure all channel/role IDs match your Discord server

Happy customizing! 🐰

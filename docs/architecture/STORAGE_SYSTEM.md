## Storage System Design & Implementation Guide

### Overview

The storage system has been redesigned to address the critical issues identified in the architectural audit:

- ✅ **Centralized path management** (no more hard-coded `/home/Discord/Images/`)
- ✅ **Per-user storage quotas** (prevent individual users from hoarding)
- ✅ **Global capacity limits** (prevent server HD bloat)
- ✅ **Automatic cleanup policies** (remove old temp files)
- ✅ **Rate limiting** (limit generations per user per day)

---

## Architecture

### Core Modules (abby_core/)

#### 1. **abby_core/storage/**

Handles all file operations and quota management.

**StorageManager** (`storage_manager.py`):

```python
from abby_core.storage import StorageManager
from pathlib import Path

# Initialize (uses config paths)
storage = StorageManager(
    storage_root=Path("shared"),
    max_global_storage_mb=5000,
    max_user_storage_mb=500,
    max_user_daily_gens=5,
    cleanup_days=7,
)

# Save image with quota checks
success, message, file_path = await storage.save_image(
    image_data=image_bytes,
    user_id="123456789",
    image_name="generated.png",
    is_temp=False,  # User storage, not temp
)

# Get quota status
status = storage.get_quota_status("123456789")
print(f"User storage: {status['user']['percentage']}% used")
print(f"Daily remaining: {status['daily']['remaining']} generations")

# List user images
images = storage.get_user_images("123456789")

# Cleanup old temp files
deleted, freed_mb = storage.cleanup_old_files()
```

#### 2. **abby_core/generation/**

Handles image generation logic (API integration, no Discord-specific code).

**ImageGenerator** (`image_generator.py`):

```python
from abby_core.generation import ImageGenerator

# Initialize
generator = ImageGenerator(
    api_key="stability_api_key",
    api_host="https://api.stability.ai"
)

# Text-to-image
success, image_bytes, message = await generator.text_to_image(
    prompt="A cute rabbit in a meadow",
    style_preset="fantasy-art",
    width=1024,
    height=1024,
)

# Image-to-image
success, image_bytes, message = await generator.image_to_image(
    image_data=existing_image_bytes,
    prompt="Make it more mystical",
    style_preset="fantasy-art",
    strength=0.35,
)

# Upscale
success, image_bytes, message = await generator.upscale_image(
    image_data=image_bytes,
    width=2048,
)

# Get available styles
styles = ImageGenerator.get_available_styles()
```

### Discord Adapter (abby_adapters/discord/)

#### Configuration

Add to `.env`:

```env
# Storage paths (relative to working directory)
STORAGE_ROOT=shared

# Storage quotas
MAX_GLOBAL_STORAGE_MB=5000      # Server limit
MAX_USER_STORAGE_MB=500         # Per-user limit
MAX_USER_DAILY_GENS=5           # Daily generation cap

# Cleanup policy
STORAGE_CLEANUP_DAYS=7          # Delete temp files older than 7 days
IMAGE_GEN_SIZE_MB=1.5           # Estimated size per generation
```

Access config:

```python
from abby_adapters.discord.config import config

storage_root = config.storage.storage_root  # Path
user_limit = config.storage.max_user_storage_mb  # MB
daily_limit = config.storage.max_user_daily_gens  # count
```

---

## Migration Steps

### Step 1: Update Image Generation Cog (Django-style)

**Before** (`cogs/creative/images.py`):

```python
# Hard-coded path - WRONG
with open(f"/home/Discord/Images/generate_image.png", "wb") as f:
    f.write(base64.b64decode(image["base64"]))
```

**After** (New pattern):

```python
from abby_core.storage import StorageManager
from abby_core.generation import ImageGenerator
from abby_adapters.discord.config import config

class ImageGenerateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.storage = StorageManager(
            storage_root=config.storage.storage_root,
            max_global_storage_mb=config.storage.max_global_storage_mb,
            max_user_storage_mb=config.storage.max_user_storage_mb,
            max_user_daily_gens=config.storage.max_user_daily_gens,
        )
        self.generator = ImageGenerator(
            api_key=config.api.stability_key,
            api_host=config.api.stability_api_host,
        )

    @app_commands.command(name="imagine")
    async def imagine(self, interaction: discord.Interaction, text: str, style: str = "enhance"):
        await interaction.response.defer()

        # Generate image (generic core function)
        success, image_data, message = await self.generator.text_to_image(
            prompt=text,
            style_preset=style,
        )

        if not success:
            return await interaction.followup.send(f"❌ {message}")

        # Save with quota checks (generic storage function)
        saved, save_msg, file_path = await self.storage.save_image(
            image_data=image_data,
            user_id=str(interaction.user.id),
            image_name="generated.png",
            is_temp=False,
        )

        if not saved:
            return await interaction.followup.send(f"❌ {save_msg}")

        # Discord-specific UI
        file = discord.File(file_path)
        embed = discord.Embed(
            title="Image Generated",
            description=f"**Prompt:** {text}\n**Style:** {style}",
            color=discord.Color.random(),
        )

        # Show quota status
        status = self.storage.get_quota_status(str(interaction.user.id))
        embed.add_field(
            name="📊 Your Quota",
            value=f"{status['user']['percentage']}% used ({status['user']['used_mb']}MB / {status['user']['limit_mb']}MB)\n"
                  f"📅 Today: {status['daily']['limit'] - status['daily']['remaining']}/{status['daily']['limit']} generations",
            inline=False
        )

        await interaction.followup.send(embed=embed, file=file)
```

### Step 2: Update Cog Initialization in Main Bot

In `main.py`, make sure StorageManager is initialized once:

```python
class Abby(commands.Bot):
    def __init__(self):
        super().__init__()
        self.config = config

        # Initialize storage once
        self.storage = StorageManager(
            storage_root=config.storage.storage_root,
            max_global_storage_mb=config.storage.max_global_storage_mb,
            max_user_storage_mb=config.storage.max_user_storage_mb,
            max_user_daily_gens=config.storage.max_user_daily_gens,
        )

        # Initialize generator
        self.generator = ImageGenerator(
            api_key=config.api.stability_key,
            api_host=config.api.stability_api_host,
        )

# Pass to cogs
await bot.add_cog(ImageGenerateCog(bot))
```

Then in cogs:

```python
class ImageGenerateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Use bot's shared instances
        self.storage = bot.storage
        self.generator = bot.generator
```

### Step 3: Test Quota System

```python
# Check quotas before generating
user_id = str(interaction.user.id)
status = self.storage.get_quota_status(user_id)

if not status['daily']['allowed']:
    return await interaction.followup.send(
        f"⏰ Daily limit reached! Try again tomorrow.\n"
        f"Remaining: {status['daily']['remaining']}/{status['daily']['limit']}"
    )

if status['user']['percentage'] > 95:
    return await interaction.followup.send(
        f"💾 Storage quota nearly full! Delete some images first.\n"
        f"Usage: {status['user']['used_mb']}MB / {status['user']['limit_mb']}MB"
    )
```

### Step 4: Implement Cleanup Command

```python
@app_commands.command(name="storage_cleanup")
@commands.is_owner()
async def cleanup_storage(interaction: discord.Interaction):
    """Admin command to cleanup old temp files."""
    await interaction.response.defer()

    deleted, freed = self.bot.storage.cleanup_old_files()

    embed = discord.Embed(
        title="🧹 Storage Cleanup Complete",
        color=discord.Color.green(),
    )
    embed.add_field(
        name="Results",
        value=f"Files deleted: {deleted}\nSpace freed: {freed:.2f}MB",
    )

    await interaction.followup.send(embed=embed)
```

---

## Directory Structure

After implementation, the directory structure will be:

```
shared/
├── images/
│   ├── users/
│   │   ├── 123456789/
│   │   │   ├── generated.png
│   │   │   ├── transformed.png
│   │   │   └── ...
│   │   ├── 987654321/
│   │   │   └── ...
│   │   └── ...
│   └── [deprecated old files]
├── temp/
│   ├── temp_image_1.png
│   ├── temp_image_2.png
│   └── ...
└── logs/
    └── events.jsonl
```

---

## Environment Variables

Add to `.env` file:

```env
# ========== STORAGE CONFIGURATION ==========
STORAGE_ROOT=shared

# Storage quotas (in MB)
MAX_GLOBAL_STORAGE_MB=5000      # Total server storage limit
MAX_USER_STORAGE_MB=500         # Per-user storage limit
MAX_USER_DAILY_GENS=5           # Max images per user per day

# Cleanup policy
STORAGE_CLEANUP_DAYS=7          # Days before temp files deleted
IMAGE_GEN_SIZE_MB=1.5           # Est. size per generation (for quota pre-check)

# ========== STABILITY AI (Image Generation) ==========
STABILITY_API_KEY=sk_xxxxx
API_HOST=https://api.stability.ai

# Optional: For local testing
# API_HOST=http://localhost:7860  # Local Stable Diffusion
```

---

## Quota System Details

### Global Limits

- **Max Total Storage**: 5GB default
- **Per-User Storage**: 500MB default
- **Daily Generations**: 5 per user per day
- **Temp File Cleanup**: 7 days default

### Enforcement

1. **Pre-generation check**: Verify user + global quotas before calling API
2. **Post-generation check**: Verify final size before saving to disk
3. **Daily reset**: Counter resets at 00:00 UTC each day
4. **Overflow prevention**: Reject if would exceed quota

### Quota Status Response

```python
{
    'global': {
        'used_mb': 1234.56,
        'total_mb': 5000,
        'percentage': 24.7,
        'status': 'OK',  # 'OK' | 'WARNING' (>80%) | 'CRITICAL' (>95%)
    },
    'user': {
        'used_mb': 45.23,
        'limit_mb': 500,
        'percentage': 9.0,
        'status': 'OK',
    },
    'daily': {
        'allowed': True,
        'remaining': 3,
        'limit': 5,
    }
}
```

---

## Advantages

### 1. ✅ Separation of Concerns

- **Core** (`abby_core/`): Generic image generation and storage logic
- **Adapter** (`abby_adapters/discord/`): Discord-specific UI and interactions
- Could reuse for Web UI, API, CLI, etc.

### 2. ✅ Prevents Server Bloat

- Per-user quotas prevent power users from hogging storage
- Global limits prevent overall bloat
- Automatic cleanup removes stale temp files

### 3. ✅ Fair Resource Usage

- Daily generation limits prevent abuse
- Quota tracking prevents unfair usage
- Admin visibility into storage usage

### 4. ✅ Configuration-Driven

- All paths and limits in `.env` or `config.py`
- No hard-coded values scattered in code
- Easy to adjust per deployment

### 5. ✅ Proper Error Messages

- Users see quotas are full, not generic "error"
- Admin can see exactly what's consuming storage
- Clear feedback for rate limiting

---

## Troubleshooting

### "Server storage is full"

- Check `config.storage.max_global_storage_mb`
- Run cleanup: `storage.cleanup_old_files()`
- Check disk space with `storage.get_global_usage()`

### "Your storage quota is full"

- User has used up their 500MB
- They need to delete old images
- Admin can delete on their behalf if needed

### "Daily generation limit reached"

- User hit their 5 generations/day
- They can try again tomorrow
- Admin can reset per user if needed

### Images not saving

- Check `shared/` directory exists and is writable
- Check `STORAGE_ROOT` env var is set correctly
- Check logs for specific error messages

---

## Performance Notes

- **Quota checks**: O(1) for daily limit, O(n) for storage size
- **Cleanup**: O(n) where n = files in temp directory
- **First call slower**: StorageManager walks filesystem on first usage
- **Recommendation**: Call cleanup periodically (daily cron or admin command)

---

## Future Enhancements

1. **Database-backed quotas**: Move tracking to MongoDB for persistence
2. **Quota tiers**: Different limits based on user role/level
3. **Image compression**: Auto-compress to JPEG if over size limit
4. **Archive system**: Move old images to archive, not delete
5. **Usage analytics**: Track per-user and per-feature usage
6. **Quota marketplace**: Let users "buy" more quota with in-game currency

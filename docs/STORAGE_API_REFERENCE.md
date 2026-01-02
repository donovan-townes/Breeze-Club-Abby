## Quick Reference: Storage System API

### Initialize (Do This Once)

```python
from abby_core.storage import StorageManager
from abby_core.generation import ImageGenerator
from abby_adapters.discord.config import config

# In bot __init__ or main.py
bot.storage = StorageManager(
    storage_root=config.storage.storage_root,
    max_global_storage_mb=config.storage.max_global_storage_mb,
    max_user_storage_mb=config.storage.max_user_storage_mb,
    max_user_daily_gens=config.storage.max_user_daily_gens,
)

bot.generator = ImageGenerator(
    api_key=config.api.stability_key,
    api_host=config.api.stability_api_host,
)
```

---

## StorageManager API

### Save Image

```python
# Save with quota enforcement
success, message, file_path = await storage.save_image(
    image_data=image_bytes,      # bytes
    user_id="123456789",         # str
    image_name="generated.png",  # str
    is_temp=False,               # bool
)

if not success:
    print(message)  # "Your storage quota is full"
    return
```

### Get Quota Status

```python
status = storage.get_quota_status("123456789")

print(f"Global: {status['global']['used_mb']}MB / {status['global']['total_mb']}MB")
print(f"User: {status['user']['used_mb']}MB / {status['user']['limit_mb']}MB")
print(f"Daily: {status['daily']['limit'] - status['daily']['remaining']}/{status['daily']['limit']} used")

# Quick checks
if status['global']['status'] == 'CRITICAL':
    print("Server storage critical!")

if not status['daily']['allowed']:
    print("User hit daily limit")
```

### Get Image Path

```python
path = storage.get_image_path("123456789", "generated.png")
if path:
    file = discord.File(path)
```

### List User Images

```python
images = storage.get_user_images("123456789")
# Returns: ["generated.png", "upscaled.png", ...]
```

### Delete Image

```python
success, message = storage.delete_image("123456789", "old.png")
```

### Cleanup Old Files

```python
# Remove files older than 7 days
deleted, freed_mb = storage.cleanup_old_files()
print(f"Deleted {deleted} files, freed {freed_mb:.2f}MB")
```

---

## ImageGenerator API

### Text to Image

```python
success, image_bytes, message = await generator.text_to_image(
    prompt="A cute rabbit",
    style_preset="fantasy-art",  # Optional
    width=1024,                  # Optional
    height=1024,                 # Optional
    steps=50,                    # Optional (quality)
    seed=0,                      # Optional
    cfg_scale=7.0,              # Optional
)

if not success:
    print(f"Error: {message}")
    return

# Use image_bytes
```

### Image to Image

```python
success, image_bytes, message = await generator.image_to_image(
    image_data=input_image_bytes,
    prompt="Make it more mystical",
    style_preset="enhance",     # Optional
    strength=0.35,              # Optional (0-1)
    steps=30,                   # Optional
)
```

### Upscale Image

```python
success, image_bytes, message = await generator.upscale_image(
    image_data=image_bytes,
    width=2048,  # 2x from 1024
)
```

### Get Available Styles

```python
styles = ImageGenerator.get_available_styles()
# Returns: {"3d-model": "3d-model", "anime": "anime", ...}
```

---

## Common Patterns

### Pattern 1: Generate and Save with Quota Check

```python
# Check before spending API credits
user_id = str(interaction.user.id)
status = storage.get_quota_status(user_id)

if not status['daily']['allowed']:
    return await interaction.followup.send("Daily limit reached!")

if status['user']['percentage'] > 90:
    return await interaction.followup.send("Storage quota nearly full!")

# Generate
success, image_bytes, msg = await generator.text_to_image(prompt)
if not success:
    return await interaction.followup.send(f"❌ {msg}")

# Save
success, save_msg, path = await storage.save_image(
    image_data=image_bytes,
    user_id=user_id,
)
if not success:
    return await interaction.followup.send(f"❌ {save_msg}")

# Show result
file = discord.File(path)
await interaction.followup.send(file=file)
```

### Pattern 2: Check All Quotas

```python
status = storage.get_quota_status(user_id)

# Descriptive status messages
if not status['daily']['allowed']:
    raise QuotaExceeded(f"Daily: {status['daily']['limit']}/day")

if status['user']['percentage'] > 95:
    raise QuotaExceeded(f"User storage: {status['user']['used_mb']}MB used")

if status['global']['percentage'] > 95:
    raise QuotaExceeded(f"Server storage critical!")
```

### Pattern 3: Show Quota Status to User

```python
status = storage.get_quota_status(user_id)

embed = discord.Embed(title="📊 Your Storage")
embed.add_field(
    "💾 User Storage",
    f"{status['user']['used_mb']}MB / {status['user']['limit_mb']}MB ({status['user']['percentage']:.1f}%)",
    inline=False,
)
embed.add_field(
    "📅 Daily Generations",
    f"{status['daily']['limit'] - status['daily']['remaining']}/{status['daily']['limit']}",
    inline=False,
)
embed.color = {
    'OK': discord.Color.green(),
    'WARNING': discord.Color.yellow(),
    'CRITICAL': discord.Color.red(),
}[status['user']['status']]

await interaction.followup.send(embed=embed)
```

### Pattern 4: Admin Cleanup Command

```python
@app_commands.command()
@commands.is_owner()
async def cleanup_storage(interaction: discord.Interaction):
    await interaction.response.defer()

    deleted, freed = bot.storage.cleanup_old_files()

    embed = discord.Embed(
        title="🧹 Storage Cleanup",
        color=discord.Color.green(),
    )
    embed.add_field("Files Deleted", str(deleted))
    embed.add_field("Space Freed", f"{freed:.2f}MB")

    await interaction.followup.send(embed=embed)
```

---

## Configuration

### Environment Variables

```env
STORAGE_ROOT=shared                    # Directory for images/temp
MAX_GLOBAL_STORAGE_MB=5000            # Server limit
MAX_USER_STORAGE_MB=500               # Per-user limit
MAX_USER_DAILY_GENS=5                 # Daily gen limit
STORAGE_CLEANUP_DAYS=7                # Days before temp delete
IMAGE_GEN_SIZE_MB=1.5                 # Est. size per gen
STABILITY_API_KEY=sk_xxxxx            # Stability AI API key
API_HOST=https://api.stability.ai     # Stability API host
```

### Access in Code

```python
from abby_adapters.discord.config import config

storage_root = config.storage.storage_root
user_limit = config.storage.max_user_storage_mb
daily_limit = config.storage.max_user_daily_gens

api_key = config.api.stability_key
api_host = config.api.stability_api_host
```

---

## Error Messages

Common errors and solutions:

| Error                              | Cause                    | Solution                                      |
| ---------------------------------- | ------------------------ | --------------------------------------------- |
| "Server storage is full"           | Global quota exceeded    | Run cleanup, increase `MAX_GLOBAL_STORAGE_MB` |
| "Your storage quota is full"       | User quota exceeded      | User deletes old images                       |
| "Daily limit reached"              | User hit daily gen limit | User waits until tomorrow                     |
| "Error saving image: No such file" | `shared/` dir missing    | Create directory, check permissions           |
| "Non-200 response: 401"            | Bad API key              | Check `STABILITY_API_KEY`                     |
| "Connection timeout"               | API unreachable          | Check `API_HOST`, network                     |

---

## Testing

Quick test script:

```python
import asyncio
from abby_core.storage import StorageManager
from abby_core.generation import ImageGenerator

async def test():
    # Initialize
    storage = StorageManager()
    generator = ImageGenerator(api_key="your_key")

    # Generate
    success, img_bytes, msg = await generator.text_to_image("test")
    print(f"Generate: {success}")

    # Save
    success, msg, path = await storage.save_image(img_bytes, "999")
    print(f"Save: {success} - {path}")

    # Check quota
    status = storage.get_quota_status("999")
    print(f"Quota: {status['user']['percentage']}% used")

    # Cleanup
    deleted, freed = storage.cleanup_old_files()
    print(f"Cleanup: {deleted} files, {freed:.2f}MB freed")

asyncio.run(test())
```

---

## Directory Structure

```
shared/                     # STORAGE_ROOT
├── images/                 # All saved images
│   ├── users/
│   │   ├── 123456789/     # User ID directory
│   │   │   ├── generated.png
│   │   │   ├── upscaled.png
│   │   │   └── ...
│   │   ├── 987654321/
│   │   └── ...
│   └── ...
├── temp/                   # Temporary files (auto-cleaned)
│   ├── temp_001.png
│   └── ...
└── logs/
    └── events.jsonl
```

---

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md) - Architecture & design patterns
- [STORAGE_SYSTEM.md](STORAGE_SYSTEM.md) - Detailed implementation guide
- [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md) - Audit findings

## Abby Architecture Guide

### What This Document Is For

This guide explains how Abby is structured to separate concerns between general app logic and Discord-specific code. It's for developers who need to understand where code belongs and how to add new features without violating architectural boundaries.

---

## The Core Principle

**abby_core** = Everything that could work with any adapter  
**abby_adapters/discord** = Only Discord-specific code

---

## Layer Model

```
┌──────────────────────────────────────────────────────┐
│           Discord Adapter Layer                      │
│   (abby_adapters/discord/)                           │
│                                                       │
│   Slash commands, Embeds, Discord interactions       │
│   ├─ cogs/         (command implementations)         │
│   ├─ core/         (Discord-specific infrastructure) │
│   ├─ handlers/     (Discord event handlers)          │
│   └─ config.py     (Discord config)                 │
│                                                       │
│   ⚠️ Only: @app_commands, discord.Message/User,      │
│      interactions, embeds, buttons, modals            │
└──────────────────────────────────────────────────────┘
                            ↓ imports
┌──────────────────────────────────────────────────────┐
│            Application Core Layer                    │
│   (abby_core/)                                       │
│                                                       │
│   General logic: databases, AI, storage, etc.        │
│   ├─ database/    (MongoDB schemas & connection)     │
│   ├─ llm/         (LLM clients: OpenAI, Ollama)      │
│   ├─ rag/         (Vector DB: Qdrant, Chroma)       │
│   ├─ generation/  (Image/content generation)         │
│   ├─ storage/     (File management & quotas)         │
│   ├─ economy/     (XP, levels, banks)                │
│   ├─ personality/ (Bot personality & responses)      │
│   ├─ security/    (Encryption, auth)                 │
│   ├─ moderation/  (Moderation policies & rules)      │
│   └─ observability/ (Logging, telemetry)             │
│                                                       │
│   ✅ Contains: Pure Python, async functions,         │
│      generic business logic, API clients              │
└──────────────────────────────────────────────────────┘
```

---

## Current Status: What's in the Right Place

### ✅ Core Modules (Well-Separated)

| Module          | Purpose                    | Discord-Free? | Can Be Reused? |
| --------------- | -------------------------- | ------------- | -------------- | --- |
| database/       | MongoDB ops, schemas       | ✅ Yes        | ✅ Yes         |
| llm/            | LLM clients                | ✅ Yes        | ✅ Yes         |
| rag/            | Vector DB (Qdrant, Chroma) | ✅ Yes        | ✅ Yes         |
| economy/        | XP, leveling, bank         | ✅ Yes        | ✅ Yes         |
| personality/    | Bot responses, personas    | ✅ Yes        | ✅ Yes         |
| security/       | Encryption, utilities      | ✅ Yes        | ✅ Yes         |
| observability/  | Logging, telemetry         | ✅ Yes        | ✅ Yes         |
| **storage/**    | File ops, quotas           | ✅ Yes        | ✅ Yes         | NEW |
| **generation/** | Image generation API       | ✅ Yes        | ✅ Yes         | NEW |

### ✅ Discord Adapter (Properly Located)

| Component      | Location       | Purpose                          |
| -------------- | -------------- | -------------------------------- |
| Slash commands | cogs/          | Command implementations          |
| Event handlers | handlers/      | Discord events                   |
| Config         | config.py      | Discord channels, tokens, timing |
| Infrastructure | core/loader.py | Dynamic cog loading              |

---

## How It Works: A Complete Example

Let's walk through how image generation works with the new architecture:

### 1. **User runs `/imagine prompt="cute rabbit"`**

Discord Adapter (cogs/creative/images.py):

```python
from abby_adapters.discord.config import config
from abby_core.generation import ImageGenerator
from abby_core.storage import StorageManager

@app_commands.command(name="imagine")
async def imagine(self, interaction: discord.Interaction, prompt: str):
    # 1. Check quotas before spending API credits
    status = self.storage.get_quota_status(str(interaction.user.id))
    if not status['daily']['allowed']:
        return await interaction.followup.send("Daily limit reached!")

    # 2. Call generic core service (no Discord imports)
    success, image_bytes, msg = await self.generator.text_to_image(
        prompt=prompt,
        style_preset="enhance",
    )

    # 3. Store with quota enforcement
    saved, save_msg, path = await self.storage.save_image(
        image_data=image_bytes,
        user_id=str(interaction.user.id),
    )

    # 4. Respond with Discord-specific UI
    file = discord.File(path)
    embed = discord.Embed(title="Generated!", description=prompt)
    await interaction.followup.send(embed=embed, file=file)
```

### 2. **Core Services (No Discord Knowledge)**

**ImageGenerator** (abby_core/generation/image_generator.py):

```python
# Pure async Python
async def text_to_image(self, prompt: str, ...) -> Tuple[bool, Optional[bytes], str]:
    # Call Stability AI
    # Return raw image bytes
    # NO discord imports, NO Discord types
    return success, image_bytes, message
```

**StorageManager** (abby_core/storage/storage_manager.py):

```python
# Pure file operations
async def save_image(self, image_data: bytes, user_id: str, ...) -> Tuple[bool, str, Path]:
    # Check quotas
    # Validate size
    # Save to disk
    # Track usage
    # NO discord imports, NO Discord types
    return success, message, file_path
```

### 3. **Why This Matters**

If you wanted to create a **Web API** for image generation:

```python
# In new web_adapter/app.py
from abby_core.generation import ImageGenerator
from abby_core.storage import StorageManager

app = FastAPI()

@app.post("/api/generate")
async def api_generate(prompt: str, user_id: str):
    # USE THE SAME CORE SERVICES
    image_bytes = await generator.text_to_image(prompt)
    saved = await storage.save_image(image_bytes, user_id)

    return {"status": "ok", "path": str(saved)}
```

**No code duplication. Same logic for Discord, Web, API, CLI, etc.**

---

## Architecture Decisions: Why It's This Way

### Why Separate Core from Adapters?

**Problem**: Without separation, image generation code is tied to Discord

```python
# WRONG - couples API logic to Discord
async def imagine(self, interaction: discord.Interaction):  # <- Discord type
    with open(f"/home/Discord/Images/image.png", "wb") as f:  # <- Hard path
        # ...
```

**Solution**: Core handles logic, Discord adapter handles UI

```python
# Core: Pure logic
async def text_to_image(self, prompt: str) -> Tuple[bool, bytes, str]:
    # ...

# Adapter: Discord-specific
@app_commands.command()
async def imagine(self, interaction: discord.Interaction):  # <- Explicit dependency
    bytes = await generator.text_to_image(prompt)  # <- No knowledge of Discord
```

### Why Configuration-Driven?

**Problem**: Hard-coded values scattered everywhere

```python
# BAD
storage_path = "/home/Discord/Images/"  # What if we deploy to Windows?
max_storage = 5000  # What if we want different limits?
daily_limit = 5  # Can't change without code edit
```

**Solution**: All in config, environment-driven

```python
# GOOD
storage_path = config.storage.storage_root  # From env
max_storage = config.storage.max_global_storage_mb  # From env
daily_limit = config.storage.max_user_daily_gens  # From env
```

### Why Per-User Quotas?

**Problem Without**: One user generates 5000 images → server disk full → everyone fails

**Solution With**: Each user limited to 500MB → fair usage → server stable

---

## What Goes Where: Decision Matrix

When you add new code, ask these questions:

### Question 1: Does it import `discord.*`?

```
YES → Put in abby_adapters/discord/
NO  → Could go in abby_core/
```

### Question 2: Does it return Discord types?

```
YES → Put in abby_adapters/discord/
NO  → Could go in abby_core/
```

### Question 3: Is it Discord-specific? (e.g., "slash commands", "embeds")

```
YES → Put in abby_adapters/discord/
NO  → Could go in abby_core/
```

### Question 4: Could another adapter reuse it? (Web, CLI, API)

```
YES → Should go in abby_core/
NO  → Should go in abby_adapters/discord/
```

---

## Examples: Where Would You Put This?

### Example 1: "Slash command for user stats"

```python
@app_commands.command(name="stats")
async def stats(self, interaction: discord.Interaction):
    data = await get_user_stats(str(interaction.user.id))
    embed = discord.Embed(...)
    await interaction.response.send_message(embed=embed)
```

**Decision**: Discord adapter

- ✅ Uses @app_commands
- ✅ Returns discord.Embed
- ✅ Calls interaction.response
- 📍 Location: `cogs/community/user_stats.py`

### Example 2: "Function to calculate user XP"

```python
async def calculate_user_xp(messages: int, attachments: int) -> int:
    return messages * 10 + attachments * 25
```

**Decision**: Core

- ❌ No discord imports
- ❌ No Discord types
- ✅ Could be reused by Web API
- 📍 Location: `abby_core/economy/xp.py` or extend it

### Example 3: "Handler for image generation errors"

```python
async def handle_generation_error(error: str) -> str:
    if "quota exceeded" in error:
        return "You've hit your generation limit!"
    elif "api error" in error:
        return "Service temporarily unavailable"
    # ...
```

**Decision**: Depends on return type

- **If returns string**: Could go in core (generic error handling)
- **If returns discord.Embed**: Must go in adapter (Discord-specific)
- 📍 Location: `abby_core/generation/error_handler.py` OR `cogs/creative/error_handler.py`

---

## Migration Checklist: Updating Existing Code

When updating the old image generation code, follow this checklist:

- [ ] **Remove hard-coded paths**

  - ❌ `/home/Discord/Images/generate_image.png`
  - ✅ Use `config.storage.storage_root`

- [ ] **Use StorageManager for file operations**

  - ❌ `with open(path, "wb") as f:`
  - ✅ `await storage.save_image(bytes, user_id)`

- [ ] **Use ImageGenerator for API calls**

  - ❌ Direct `aiohttp.post()` to Stability API
  - ✅ `await generator.text_to_image(prompt)`

- [ ] **Add quota checks**

  - ❌ No limits on generation
  - ✅ Check `storage.get_quota_status(user_id)`

- [ ] **Keep Discord UI in adapter**

  - ✅ Keep embeds, buttons, modals here
  - ✅ Keep slash command handlers here

- [ ] **Move generic logic to core**
  - ✅ Image generation to `abby_core/generation/`
  - ✅ Storage management to `abby_core/storage/`

---

## Testing: How to Verify Structure

### Command 1: Check for Discord imports in core

```bash
grep -r "import discord" abby_core/
# Should return NOTHING
```

### Command 2: Check that core modules are imported by adapter

```bash
grep -r "from abby_core" abby_adapters/discord/
# Should return lots of results
```

### Command 3: Check that core DOESN'T import from adapter

```bash
grep -r "from abby_adapters" abby_core/
# Should return NOTHING
```

---

## Adding a New Feature: Step-by-Step

Let's say you want to add "User moderation warnings":

### Step 1: Create Core Logic

**abby_core/moderation/warning_system.py**:

```python
class WarningSystem:
    """Generic warning system - could be used by any adapter"""

    async def add_warning(self, user_id: str, reason: str) -> bool:
        # Database operation
        # No Discord code
        pass

    async def get_warnings(self, user_id: str) -> List[Warning]:
        # Query database
        # Return generic Warning objects
        pass
```

### Step 2: Create Discord Commands

**abby_adapters/discord/cogs/admin/moderation.py**:

```python
class ModerationCog(commands.Cog):
    @app_commands.command()
    async def warn(self, interaction: discord.Interaction, user: discord.User, reason: str):
        # Use core system
        success = await self.bot.warning_system.add_warning(str(user.id), reason)

        # Discord-specific response
        if success:
            embed = discord.Embed(title="User Warned", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)
```

### Step 3: Update Config If Needed

**abby_adapters/discord/config.py**:

```python
@dataclass
class ModerationConfig:
    max_warnings_before_ban: int = field(...)  # Discord setting
    warning_cooldown_days: int = field(...)    # Generic setting

# Add to BotConfig
moderation: ModerationConfig = field(default_factory=ModerationConfig)
```

---

## Common Mistakes (And How to Avoid Them)

### ❌ Mistake 1: Discord Code in Core

```python
# abby_core/economy/xp.py
def format_xp(xp: int) -> discord.Embed:  # WRONG - Discord import
    return discord.Embed(...)
```

✅ **Fix**: Return data, let adapter format

```python
# abby_core/economy/xp.py
def format_xp(xp: int) -> Dict:  # Return data
    return {"xp": xp, "level": calculate_level(xp)}

# abby_adapters/discord/cogs/economy/stats.py
data = await economy.format_xp(user_xp)  # Get data
embed = discord.Embed(...)  # Format for Discord
embed.add_field("XP", str(data['xp']))
```

### ❌ Mistake 2: Hard-Coded Values

```python
# WRONG
API_KEY = "sk_xxxxx"  # What if deployed elsewhere?
MAX_SIZE = 5000  # What if settings change?
```

✅ **Fix**: Use config

```python
# In config.py
api_key = os.getenv("STABILITY_API_KEY")
max_size = os.getenv("MAX_GLOBAL_STORAGE_MB")

# In code
api_key = config.api.stability_key
```

### ❌ Mistake 3: Importing from Adapter in Core

```python
# abby_core/generation/image_generator.py
from abby_adapters.discord.config import config  # WRONG - creates cycle
```

✅ **Fix**: Pass config to core service

```python
# abby_adapters/discord/cogs/creative/images.py
from abby_core.generation import ImageGenerator

# Pass config at initialization
generator = ImageGenerator(
    api_key=config.api.stability_key,  # Inject dependency
)

# In core - no imports from adapter
class ImageGenerator:
    def __init__(self, api_key: str):  # Accept parameters
        self.api_key = api_key
```

### ❌ Mistake 4: Tight Coupling to File Paths

```python
# WRONG
open(f"/home/Discord/Images/{user_id}/image.png")
```

✅ **Fix**: Use StorageManager

```python
# Use abstraction
await storage.save_image(bytes, user_id)
path = await storage.get_image_path(user_id)
```

---

## Summary Checklist

When reviewing code:

- [ ] Core modules have **zero** `import discord` statements
- [ ] Core modules return **generic types** (bytes, str, Dict, etc.)
- [ ] Discord adapter imports from core, **never** vice versa
- [ ] Configuration is **externalized** to `config.py` or `.env`
- [ ] New features go in core if **reusable**, adapter if **Discord-specific**
- [ ] No **hard-coded paths** - use `config` or parameters
- [ ] File operations use **StorageManager** abstraction
- [ ] API calls use **core service** abstractions (e.g., ImageGenerator)

---

## Questions? Examples?

Refer to:

- [STORAGE_SYSTEM.md](STORAGE_SYSTEM.md) - How the storage system works
- [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md) - Detailed audit of current structure
- [CONFIG_MODERNIZATION_GUIDE.md](CONFIG_MODERNIZATION_GUIDE.md) - Configuration patterns

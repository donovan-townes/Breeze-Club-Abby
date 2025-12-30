# Code Reorganization Progress

## Status: Partial - Infrastructure Ready, Manual File Moves Needed

The directory structure has been created and key files moved. However, due to Windows file locking and active processes, some moves need to be completed manually after bot shutdown.

---

## ✅ Completed

### 1. Directory Structure Created

- `abby-core/llm/` ✅ (already existed)
- `abby-core/rag/` ✅ (already existed)
- `abby-core/economy/` ✅ (created)
- `abby-core/moderation/` ✅ (created)
- `abby-core/utils/` ✅ (created)
- `abby-adapters/discord/cogs/` ✅ (created)
- `abby-adapters/discord/commands/` ✅ (created)
- `abby-adapters/discord/handlers/` ✅ (created)

### 2. Files Moved

- ✅ `utils/*.py` → `abby-core/utils/`
- ✅ `main.py` → `abby-adapters/discord/main.py`
- ✅ Created `launch.py` (root launcher)
- ✅ Updated imports in `abby-adapters/discord/main.py`

---

## ⏳ Needs Manual Completion

### Step 1: Stop the Bot

```bash
# Stop any running Abby process
```

### Step 2: Move Discord Cogs

```powershell
# From C:\Abby_Discord_Latest
Move-Item -Path "Chatbot" -Destination "abby-adapters\discord\cogs\" -Force
Move-Item -Path "Exp" -Destination "abby-adapters\discord\cogs\" -Force
Move-Item -Path "Fun" -Destination "abby-adapters\discord\cogs\" -Force
Move-Item -Path "Greetings" -Destination "abby-adapters\discord\cogs\" -Force
Move-Item -Path "Twitch" -Destination "abby-adapters\discord\cogs\" -Force
Move-Item -Path "Twitter" -Destination "abby-adapters\discord\cogs\" -Force
Move-Item -Path "Calender" -Destination "abby-adapters\discord\cogs\" -Force
```

### Step 3: Move Commands and Handlers

```powershell
Move-Item -Path "Commands\*" -Destination "abby-adapters\discord\commands\" -Recurse -Force
Move-Item -Path "handlers\*" -Destination "abby-adapters\discord\handlers\" -Recurse -Force
```

### Step 4: Move Economy Logic

```powershell
# Core logic to abby-core
Move-Item -Path "Exp\xp_handler.py" -Destination "abby-core\economy\" -Force
Move-Item -Path "Banking\bank_central.py" -Destination "abby-core\economy\" -Force

# Cogs stay in adapter (already moved in Step 2)
```

---

## 🔧 Import Path Updates Needed

After moves complete, update imports in these file categories:

### 1. All Cogs (in abby-adapters/discord/cogs/)

**Find:**

```python
from utils.log_config import setup_logging, logging
from utils.mongo_db import connect_to_mongodb
from Exp.xp_handler import increment_xp
```

**Replace with:**

```python
from abby_core.utils.log_config import setup_logging, logging
from abby_core.utils.mongo_db import connect_to_mongodb
from abby_core.economy.xp_handler import increment_xp
```

### 2. Command Files (in abby-adapters/discord/commands/)

Same replacements as above.

### 3. Handlers (in abby-adapters/discord/handlers/)

**command_loader.py needs special attention:**

```python
# Update WORKING_DIRECTORY to scan adapter structure
# Change from: for root, dirs, files in os.walk('Commands'):
# To: for root, dirs, files in os.walk('abby-adapters/discord/commands'):
```

---

## 📁 New Structure (Target)

```
Abby_Discord_Latest/
├── launch.py                          # NEW: Root launcher
├── abby-core/                         # Domain logic (no Discord deps)
│   ├── llm/                          # ✅ LLM abstraction
│   ├── rag/                          # ✅ RAG system
│   ├── economy/                       # ⏳ XP/economy logic
│   │   ├── xp_handler.py             # ⏳ Core XP logic
│   │   └── bank_central.py            # ⏳ Core banking logic
│   ├── moderation/                    # 🔜 Future: content decisions
│   └── utils/                         # ✅ Shared utilities
│       ├── log_config.py              # ✅ Logging setup
│       ├── mongo_db.py                # ✅ MongoDB client
│       ├── tdos_events.py             # ✅ TDOS event emission
│       ├── bdcrypt.py                 # ✅ Encryption
│       ├── chat_openai.py             # ✅ OpenAI wrapper
│       └── rag_qdrant.py              # ✅ Qdrant wrapper
│
├── abby-adapters/                     # Interface implementations
│   └── discord/                       # Discord-specific I/O
│       ├── main.py                    # ✅ Bot entry point
│       ├── cogs/                      # ⏳ Discord cogs
│       │   ├── Chatbot/              # ⏳ Chat interactions
│       │   ├── Exp/                  # ⏳ XP display commands
│       │   ├── Fun/                  # ⏳ Fun commands
│       │   ├── Greetings/            # ⏳ Welcome/announcements
│       │   ├── Twitch/               # ⏳ Twitch integration
│       │   └── Twitter/              # ⏳ Twitter integration
│       ├── commands/                  # ⏳ Slash commands
│       │   ├── Admin/                # ⏳ Admin commands
│       │   ├── User/                 # ⏳ User commands
│       │   └── ...                   # ⏳ Other categories
│       └── handlers/                  # ⏳ Event handlers
│           ├── command_loader.py      # ⏳ Cog/command loader
│           ├── moderation.py          # ✅ Moderation handler
│           ├── nudge_handler.py       # ✅ Nudge handler
│           └── url_handler.py         # ⏳ URL parsing
│
└── legacy-outdated/                   # Old structure (keep for reference)
```

---

## 🚀 How to Complete

### Option A: Manual Move (Recommended)

1. Stop bot
2. Run PowerShell commands above
3. Update imports (find/replace in VSCode)
4. Test with `python launch.py`

### Option B: Script-Assisted

Create `scripts/complete_reorganization.py`:

```python
import shutil
from pathlib import Path

moves = [
    ("Chatbot", "abby-adapters/discord/cogs/Chatbot"),
    ("Exp", "abby-adapters/discord/cogs/Exp"),
    # ... etc
]

for src, dst in moves:
    if Path(src).exists():
        shutil.move(src, dst)
        print(f"Moved {src} -> {dst}")
```

---

## 🧪 Testing Checklist

After reorganization:

- [ ] Bot starts: `python launch.py`
- [ ] Cogs load without ImportError
- [ ] Commands work: `/help`, `/xp status`
- [ ] TDOS events emit to `shared/logs/events.jsonl`
- [ ] Chatbot responds
- [ ] RAG commands work: `/rag stats`

---

## 🔄 Rollback Plan

If issues arise:

1. Git stash/commit current state
2. Use original `main.py` in root
3. Revert to old imports
4. File issue for troubleshooting

---

## 📝 Next Steps After Completion

1. Update `.env` paths if needed
2. Update `requirements.txt` if import changes break deps
3. Archive old folders: `mkdir legacy-outdated; mv Chatbot Exp ... legacy-outdated/`
4. Update documentation with new structure
5. Test all commands and cogs systematically

---

## Notes

- **Python paths**: `launch.py` adds `abby-core/` to sys.path automatically
- **Import convention**: Use `abby_core.utils.X` (underscore, not hyphen)
- **Adapter isolation**: Discord adapter can now import from core, but core NEVER imports from adapter
- **Future adapters**: Can be added as `abby-adapters/web/`, `abby-adapters/cli/` with same core access

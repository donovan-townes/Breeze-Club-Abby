# Local Development Quick Start

**Goal:** Set up Abby development environment on your Windows machine, develop locally with full Docker parity to production, deploy only tested code.

## 5-Minute Setup

### 1. Create Environment File

```powershell
cd c:\TDOS\apps\abby_bot\docker
Copy-Item .env.dev.example .env.dev
```

### 2. Edit .env.dev

```powershell
notepad .env.dev
```

**Fill in these fields (minimum):**

- `DISCORD_TOKEN=<your-test-bot-token>`
  - Create test bot at https://discord.com/developers/applications
  - Copy token from Bot section
  - **NOT your production token!**

- `GUILD_IDS=<your-test-server-id>`
  - Join a test Discord server
  - Right-click server name → "Copy Server ID"
  - Need Developer Mode enabled in Discord User Settings

- `OPENAI_API_KEY=<your-openai-key>`
  - Get from https://platform.openai.com/api-keys
  - Can use dev key with limited quota

### 3. Start Local Environment

```powershell
cd c:\TDOS\apps\abby_bot\docker

# Option A: Using helper script (easier)
.\dev-compose-helper.ps1 up

# Option B: Using docker compose directly
docker compose -f docker-compose.dev.yml up
```

**Wait for output:**

```
abby-dev | [✓] System operational - 33 cogs, 27 commands
abby-dev | [💚] Health: MongoDB: OK | Storage: OK
```

### 4. Test It Works

- Open your test Discord server
- Type `/help` or `!dev help` (depends on bot prefix)
- Bot should respond

### 5. Deploy to Production

```powershell
# Once tested locally
.\docker\docker-build-push.ps1 -RegistryHost "registry.tdos.internal"

ssh tserver
cd /srv/tserver/compose
docker compose pull abby && docker compose up -d abby
```

---

## Daily Development Workflow

### Start Day

```powershell
cd c:\TDOS\apps\abby_bot\docker
.\dev-compose-helper.ps1 up
```

### Make Changes

```
1. Edit code in c:\TDOS\apps\abby_bot\abby_core\...
2. Container sees changes immediately (volume mount)
3. If cog needs reload: type /reload <cog> in Discord
4. If major change: Ctrl+C, run .\dev-compose-helper.ps1 up again
```

### View Logs

```powershell
.\dev-compose-helper.ps1 logs -Service abby
```

### End Day

```powershell
.\dev-compose-helper.ps1 down
# Data persists in ./dev-state/ directory
```

---

## Common Commands

### Check Status

```powershell
.\dev-compose-helper.ps1 status
```

### View Logs

```powershell
# Last 50 lines
docker compose -f docker-compose.dev.yml logs abby --tail 50

# Follow logs in real-time
docker compose -f docker-compose.dev.yml logs -f abby

# All services
.\dev-compose-helper.ps1 logs -Service all
```

### Access MongoDB

```powershell
# Open MongoDB shell
.\dev-compose-helper.ps1 db

# Or directly
docker compose -f docker-compose.dev.yml exec mongo mongosh localhost:27017/abby

# Run queries
db.users.find()
db.guilds.findOne()
```

### Open Container Shell

```powershell
.\dev-compose-helper.ps1 shell

# Now inside container
python
exit()
```

### Clean Up Everything

```powershell
# Stop containers
.\dev-compose-helper.ps1 down

# Delete all local data (start fresh next time)
.\dev-compose-helper.ps1 clean
```

---

## Troubleshooting

### "Connection refused" to MongoDB

**Problem:** Abby can't connect to MongoDB  
**Solution:**

```powershell
# Check MongoDB is running
.\dev-compose-helper.ps1 status

# Should show: mongo STATUS: Up X minutes (healthy)

# If not healthy, restart
docker compose -f docker-compose.dev.yml restart mongo

# Check MongoDB logs
docker compose -f docker-compose.dev.yml logs mongo
```

### "Discord login failed"

**Problem:** Bot can't connect to Discord  
**Check:**

- `DISCORD_TOKEN` is correct in `.env.dev`
- Token is from TEST bot, not production
- Bot is invited to test guild with permissions

**Solution:**

```powershell
# Stop and restart
.\dev-compose-helper.ps1 down
.\dev-compose-helper.ps1 up
```

### "Module not found" errors

**Problem:** Python can't find a dependency  
**Solution:**

```powershell
# Rebuild image (installs dependencies)
.\dev-compose-helper.ps1 build

# Or full restart
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml up --build
```

### Changes not taking effect

**Problem:** Edited code but container still uses old version  
**Solution:**

```powershell
# Option 1: Restart container
docker compose -f docker-compose.dev.yml restart abby

# Option 2: Full restart (rebuilds if Dockerfile changed)
.\dev-compose-helper.ps1 down
.\dev-compose-helper.ps1 up

# If requirements.txt changed, force rebuild
docker compose -f docker-compose.dev.yml up --build
```

### "Port 27017 already in use"

**Problem:** Another MongoDB instance running  
**Solution:**

```powershell
# Kill process using port
Get-Process | Where-Object {$_.ProcessName -like "*mongo*"} | Stop-Process

# Or use different port in docker-compose.dev.yml
# Change: - "27017:27017" to - "27018:27017"
```

### Out of disk space

**Problem:** `docker/dev-state/` taking too much space  
**Solution:**

```powershell
# See what's taking space
ls -la docker/dev-state/

# Clean up old data
.\dev-compose-helper.ps1 clean

# Or manually
rm -r docker/dev-state/mongo/data/*
rm -r docker/dev-state/abby/logs/*
```

---

## Architecture: How This Works

### Local Dev vs Production Comparison

```
┌─ Your Windows Machine ──────────────────────────────┐
│                                                     │
│  c:\TDOS\apps\abby_bot\                            │
│  ├── Dockerfile (same in dev & prod)               │
│  ├── requirements.txt (same in dev & prod)         │
│  ├── abby_core/ (your code)                        │
│  │                                                 │
│  └── docker/                                        │
│      ├── docker-compose.dev.yml ← You run this    │
│      ├── .env.dev ← Your local config              │
│      └── dev-state/ ← Local data persists here     │
│          ├── mongo/data                            │
│          └── abby/logs                             │
│                                                     │
│  Image built: Exactly same as production           │
│  Config loaded: .env.dev (local)                   │
│  MongoDB: Runs in Docker on your machine           │
└─────────────────────────────────────────────────────┘

         PUSH TESTED IMAGE
              ↓ ↓ ↓

┌─ TSERVER (Ubuntu Linux) ───────────────────────────┐
│                                                     │
│  /srv/tserver/compose/                             │
│  ├── docker-compose.yml ← Services orchestrated    │
│  ├── abby.env ← Production config                  │
│  ├── coredns/ ← Internal DNS                       │
│  └── state/                                         │
│      ├── mongo/data ← Shared DB                    │
│      └── abby/ ← Bot data                          │
│                                                     │
│  /srv/tserver/state/registry/                      │
│  └── abby/ ← Your pushed image stored here         │
│                                                     │
│  Image pulled: Same image you tested locally       │
│  Config loaded: abby.env (production)              │
│  MongoDB: Shared service (no auth)                 │
└─────────────────────────────────────────────────────┘
```

### The Key Insight

**Same Dockerfile + Different .env = Confidence**

```
1. Local: docker-compose.dev.yml + .env.dev
   ↓ Test everything locally

2. Works locally?
   ↓ Build image

3. Push: docker push registry.tdos.internal:5000/abby:latest
   ↓ Image now available to TSERVER

4. TSERVER: docker-compose.yml + abby.env
   ↓ Same image, different config

5. Result: Identical application behavior (different environment)
```

---

## Next Steps

### Once You're Comfortable

**1. Try infrastructure experiments locally:**

```yaml
# In docker-compose.dev.yml, try adding Redis:
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - abby_dev_net
```

**2. Test code changes before pushing:**

- Always iterate locally first
- Deploy only tested code
- Keep production stable

**3. Monitor logs while testing:**

```powershell
# Terminal 1: Keep logs visible
.\dev-compose-helper.ps1 logs -Service abby

# Terminal 2: Make changes, test
cd c:\TDOS\apps\abby_bot
# Edit code...
```

**4. Use version tags for releases:**

```powershell
# After testing locally and pushing
# In TSERVER docker-compose.yml, use specific version
image: registry.tdos.internal:5000/abby:1.2.3

# Later, easy rollback
image: registry.tdos.internal:5000/abby:1.2.2
```

---

## Questions?

**Check these files:**

- `../DOCKER_MIGRATION_GUIDE.md` - Complete architecture guide
- `docker-compose.dev.yml` - Configuration details
- `.env.dev.example` - Environment variable documentation

**Common operations:**

- View full logs: `.\dev-compose-helper.ps1 logs -Service all`
- Check disk usage: `.\dev-compose-helper.ps1 status`
- Backup data: `copy -r docker/dev-state docker/dev-state.backup`

---

**Last Updated:** February 9, 2026  
**For Production:** See DOCKER_MIGRATION_GUIDE.md → Operational Guide section

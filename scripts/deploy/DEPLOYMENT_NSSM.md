## TSERVER Deployment Plan

### What Needs to Live on TSERVER:

**Required:**
```
C:\abby_bot\
├── launch.py                    # Entry point
├── requirements.txt             # Dependencies
├── .env                         # PRODUCTION environment vars
├── abby_core/                   # All core modules
├── abby_adapters/               # All adapters
├── scripts/                     # Utility scripts
├── logs/                        # Created on first run
└── .venv\                       # Python virtual environment (create on TSERVER)
```

**NOT needed on TSERVER:**
```
❌ .git/                         # Keep version control local
❌ __pycache__/                  # Auto-generated
❌ tests/                        # Development only
❌ docs/                         # Optional (can skip)
❌ REFACTORING_PLAN.md           # Development artifact
❌ memory_docs/                  # Optional
❌ dump/                         # MongoDB backup (separate process)
```

### TSERVER Setup Steps:

**1. Initial File Transfer:**
```powershell
# From your local machine
scp -r C:\Abby_Discord_Latest\abby_core tserver@100.108.120.82:"C:\abby_bot\"
scp -r C:\Abby_Discord_Latest\abby_adapters tserver@100.108.120.82:"C:\abby_bot\"
scp -r C:\Abby_Discord_Latest\scripts tserver@100.108.120.82:"C:\abby_bot\"
scp C:\Abby_Discord_Latest\launch.py tserver@100.108.120.82:"C:\abby_bot\"
scp C:\Abby_Discord_Latest\requirements.txt tserver@100.108.120.82:"C:\abby_bot\"
scp C:\Abby_Discord_Latest\.env tserver@100.108.120.82:"C:\abby_bot\.env.production"
```

**2. SSH into TSERVER and Setup:**
```powershell
ssh tserver@100.108.120.82

# On TSERVER:
cd C:\abby_bot

# Create production .env (edit for TSERVER environment)
copy .env.production .env
notepad .env  # Update MONGODB_URI, DISCORD_TOKEN, etc. for production

# Create virtual environment
python -m venv .venv

# Activate venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Test launch manually first
python launch.py
# Ctrl+C to stop once you confirm it works
```

**3. Install NSSM Service:**
```powershell
# Still on TSERVER, run as Administrator:

# Install service
nssm install AbbyBot "C:\abby_bot\.venv\Scripts\python.exe" "C:\abby_bot\launch.py"

# Configure service
nssm set AbbyBot AppDirectory "C:\abby_bot"
nssm set AbbyBot DisplayName "Abby Discord Bot"
nssm set AbbyBot Description "Abby - Breeze Club Discord Assistant (24/7)"
nssm set AbbyBot Start SERVICE_AUTO_START

# Set up logging
nssm set AbbyBot AppStdout "C:\abby_bot\logs\service_stdout.log"
nssm set AbbyBot AppStderr "C:\abby_bot\logs\service_stderr.log"
nssm set AbbyBot AppRotateFiles 1
nssm set AbbyBot AppRotateOnline 1
nssm set AbbyBot AppRotateBytes 1048576  # 1MB log rotation

# Set restart policy (auto-restart on failure)
nssm set AbbyBot AppExit Default Restart
nssm set AbbyBot AppRestartDelay 5000    # 5 seconds

# Start the service
nssm start AbbyBot

# Check status
nssm status AbbyBot
```

**4. Service Management Commands:**
```powershell
# Check service status
nssm status AbbyBot

# Stop service
nssm stop AbbyBot

# Start service
nssm start AbbyBot

# Restart service
nssm restart AbbyBot

# View service logs
type C:\abby_bot\logs\service_stdout.log
type C:\abby_bot\logs\service_stderr.log

# Remove service (if needed)
nssm remove AbbyBot confirm
```

### Development → Production Workflow:

**Local Development:**
```powershell
# Work on your local machine
cd C:\Abby_Discord_Latest
.venv\Scripts\activate
# Make changes, test with: python launch.py
```

**Deploy Updates to TSERVER:**
```powershell
# Option 1: Full sync (after major changes)
ssh tserver@100.108.120.82 "nssm stop AbbyBot"
scp -r C:\Abby_Discord_Latest\abby_core tserver@100.108.120.82:"C:\abby_bot\"
scp -r C:\Abby_Discord_Latest\abby_adapters tserver@100.108.120.82:"C:\abby_bot\"
ssh tserver@100.108.120.82 "nssm start AbbyBot"

# Option 2: Specific file updates
ssh tserver@100.108.120.82 "nssm stop AbbyBot"
scp C:\Abby_Discord_Latest\abby_core\llm\client.py tserver@100.108.120.82:"C:\abby_bot\abby_core\llm\"
ssh tserver@100.108.120.82 "nssm start AbbyBot"

# Option 3: Use rsync (if installed) for smart sync
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='.env' C:\Abby_Discord_Latest\ tserver@100.108.120.82:"C:\abby_bot\"
```

### Environment Configuration:

**Local .env (development):**
```ini
DISCORD_TOKEN=your_dev_bot_token_here
MONGODB_URI=mongodb://localhost:27017
OPENAI_API_KEY=sk-...
OLLAMA_BASE_URL=http://localhost:11434
# ... other dev settings
```

**TSERVER .env (production):**
```ini
DISCORD_TOKEN=your_production_bot_token_here
MONGODB_URI=mongodb://your_production_db:27017
OPENAI_API_KEY=sk-...
OLLAMA_BASE_URL=http://tserver-ip:11434  # If Ollama on TSERVER
# ... other production settings
```

### MongoDB Considerations:

**Option A: MongoDB on TSERVER**
- Abby connects to local MongoDB on TSERVER
- Fastest, no network latency
- Backup: `mongodump` on TSERVER regularly

**Option B: Remote MongoDB (Atlas/Shared)**
- Both local dev and TSERVER connect to same DB
- Easier development (shared data)
- Set `MONGODB_URI` to remote connection string in both environments

**Current Setup (Local MongoDB):**
```powershell
# Restore your backup to TSERVER MongoDB
scp -r C:\Abby_Discord_Latest\dump tserver@100.108.120.82:"C:\temp\"
ssh tserver@100.108.120.82
mongorestore C:\temp\dump
```

### Quick Reference Card:

```
📋 TSERVER Service Quick Commands:
├─ Start:   nssm start AbbyBot
├─ Stop:    nssm stop AbbyBot
├─ Restart: nssm restart AbbyBot
├─ Status:  nssm status AbbyBot
└─ Logs:    type C:\abby_bot\logs\service_stdout.log

🔄 Deploy Updates:
1. Stop service on TSERVER
2. SCP files to C:\abby_bot\
3. Start service on TSERVER

🚨 Emergency Access:
ssh tserver@100.108.120.82
cd C:\abby_bot
.venv\Scripts\activate
python launch.py  # Manual mode for debugging
```
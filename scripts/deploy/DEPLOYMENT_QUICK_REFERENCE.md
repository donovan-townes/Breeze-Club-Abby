# Abby Bot Deployment & Service Management Quick Reference

## 🚀 Local Machine Deployment (Windows PowerShell)

### Deploy Updates to TSERVER

```powershell
cd C:\Abby_Discord_Latest

# Quick deploy (abby_core + abby_adapters only) - RECOMMENDED for code changes
.\scripts\deploy-to-tserver.ps1 -Mode quick

# Full deploy (everything including scripts and requirements)
.\scripts\deploy-to-tserver.ps1 -Mode full

# Test mode (shows what would be deployed without actually deploying)
.\scripts\deploy-to-tserver.ps1 -Mode test
```

**What each mode does:**
- `quick` - ~30 seconds, syncs code changes, restarts service
- `full` - ~45 seconds, full deployment including dependencies
- `test` - Dry run, shows what would happen

---

## 🔧 Remote Service Management (SSH to TSERVER)

### Connect to TSERVER

```powershell
ssh tserver@100.108.120.82
```

### Once SSH'd in, run service commands:

```powershell
cd C:\abby_bot

# Check service status
.\scripts\abby-service.ps1 -Action status

# Restart the bot (when deploying updates)
.\scripts\abby-service.ps1 -Action restart

# Stop the bot temporarily
.\scripts\abby-service.ps1 -Action stop

# Start the bot again
.\scripts\abby-service.ps1 -Action start

# View last 50 lines of logs
.\scripts\abby-service.ps1 -Action logs

# Follow logs in real-time (like tail -f on Linux)
.\scripts\abby-service.ps1 -Action logs-tail

# Clear old logs
.\scripts\abby-service.ps1 -Action clear-logs

# Launch debug mode (manual Python execution for testing)
.\scripts\abby-service.ps1 -Action debug

# Open the bot directory in Explorer
.\scripts\abby-service.ps1 -Action deploy-local
```

---

## 📋 Typical Development Workflow

### Scenario 1: Quick Bug Fix

```powershell
# On LOCAL machine
cd C:\Abby_Discord_Latest
# Edit the file, test locally
python launch.py
# Kill with Ctrl+C when satisfied

# Deploy to TSERVER
.\scripts\deploy-to-tserver.ps1 -Mode quick
# Automatic! Service restarts and loads new code
```

### Scenario 2: Debugging on TSERVER

```powershell
# SSH into TSERVER
ssh tserver@100.108.120.82

# Check what's happening
.\scripts\abby-service.ps1 -Action logs-tail

# If something's broken, launch debug mode
.\scripts\abby-service.ps1 -Action debug
# (runs Python interactively so you can see errors)
# Ctrl+C to exit

# Restart when fixed
.\scripts\abby-service.ps1 -Action restart
```

### Scenario 3: Adding Dependencies

```powershell
# On LOCAL machine
cd C:\Abby_Discord_Latest
# Update requirements.txt with new package

# On TSERVER (SSH'd in)
cd C:\abby_bot
.venv\Scripts\activate
pip install -r requirements.txt

# Restart service
.\scripts\abby-service.ps1 -Action restart
```

---

## 🚨 Emergency/Troubleshooting

### Service won't start

```powershell
# SSH to TSERVER
ssh tserver@100.108.120.82
cd C:\abby_bot

# Launch manual mode to see actual errors
.\scripts\abby-service.ps1 -Action debug

# Look for Python errors in output
# Once fixed, exit (Ctrl+C) and restart
.\scripts\abby-service.ps1 -Action restart
```

### View recent errors

```powershell
# SSH to TSERVER
ssh tserver@100.108.120.82
cd C:\abby_bot

# View last 100 lines of both logs
Get-Content logs\service_stdout.log -Tail 100
Get-Content logs\service_stderr.log -Tail 100
```

### Manually manage service (without script)

```powershell
# SSH to TSERVER
ssh tserver@100.108.120.82

# Direct NSSM commands
nssm status AbbyBot           # Check status
nssm start AbbyBot            # Start service
nssm stop AbbyBot             # Stop service
nssm restart AbbyBot          # Restart service
nssm edit AbbyBot             # Edit service config in GUI
```

---

## 📂 Directory Structure on TSERVER

```
C:\abby_bot\
├── launch.py                 # Entry point
├── requirements.txt          # Python dependencies
├── .env                      # Production environment variables
├── .venv\                    # Virtual environment (created during setup)
├── logs\                     # Service logs (auto-created)
│   ├── service_stdout.log
│   └── service_stderr.log
├── abby_core\                # Core modules
├── abby_adapters\            # Adapter modules
├── scripts\                  # Helper scripts (including these!)
└── [other directories]
```

---

## 🔑 Key Files for Reference

- **deploy-to-tserver.ps1** - Local deployment script (run from your machine)
- **abby-service.ps1** - Remote service management script (run on TSERVER)
- **launch.py** - Bot entry point
- **.env** - Production settings (NEVER commit to git)

---

## 💡 Pro Tips

1. **Always test locally first** before deploying to TSERVER
   ```powershell
   cd C:\Abby_Discord_Latest
   python launch.py
   ```

2. **Quick deploy is your friend** - 30 seconds vs manual process
   ```powershell
   .\scripts\deploy-to-tserver.ps1 -Mode quick
   ```

3. **Tail the logs while testing**
   ```powershell
   # SSH to TSERVER in another terminal
   .\scripts\abby-service.ps1 -Action logs-tail
   ```

4. **Service auto-restarts on failure** - Check logs if it keeps restarting
   ```powershell
   .\scripts\abby-service.ps1 -Action logs
   ```

5. **Keep .env files local** - Never commit production keys to git
   - Local: `C:\Abby_Discord_Latest\.env`
   - TSERVER: `C:\abby_bot\.env` (different values!)

---

## 🔗 Related Documentation

- `DEPLOYMENT_NSSM.md` - NSSM service setup documentation
- `REFACTORING_PLAN.md` - Code organization notes
- `requirements.txt` - Python dependencies

---

**Last Updated:** 2026-01-01
**Created for:** Abby Discord Bot v2.0 (Refactored)

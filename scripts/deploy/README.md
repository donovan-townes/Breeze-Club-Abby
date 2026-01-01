# Abby Deployment & Management Scripts

Quick deployment and service management tools for the Abby Discord Bot.

## 📋 Scripts Overview

### 🚀 `deploy-to-tserver.ps1`
**Purpose:** Deploy code from your local machine to TSERVER

**Location:** Run from `C:\Abby_Discord_Latest`

**Usage:**
```powershell
.\scripts\deploy-to-tserver.ps1 -Mode quick    # Fast deployment (recommended)
.\scripts\deploy-to-tserver.ps1 -Mode full     # Full deployment
.\scripts\deploy-to-tserver.ps1 -Mode test     # Dry run (no changes)
```

**What it does:**
- Stops the bot service on TSERVER
- Syncs code from your machine to TSERVER
- Clears Python cache
- Restarts the service
- Verifies service is running

**Best for:** Deploying code changes

---

### 🔧 `abby-service.ps1`
**Purpose:** Manage the bot service when SSH'd into TSERVER

**Location:** TSERVER at `C:\abby_bot`

**Usage (via SSH):**
```powershell
ssh tserver@100.108.120.82
cd C:\abby_bot
.\scripts\abby-service.ps1 -Action [action]
```

**Available actions:**
| Action | Purpose |
|--------|---------|
| `status` | Check service status & recent logs |
| `restart` | Restart the service |
| `start` | Start the service |
| `stop` | Stop the service |
| `logs` | View last 50 lines of logs |
| `logs-tail` | Follow logs in real-time |
| `clear-logs` | Clear old log files |
| `debug` | Launch manual debug mode (see actual errors) |
| `deploy-local` | Open bot directory in Explorer |

**Best for:** Remote debugging and service monitoring

---

### 🔗 `abby-batch.ps1`
**Purpose:** Execute multi-step operations with a single command

**Location:** Run from `C:\Abby_Discord_Latest`

**Usage:**
```powershell
.\scripts\abby-batch.ps1 -Command sync-and-restart     # Deploy & restart in one go
.\scripts\abby-batch.ps1 -Command health-check         # Full system health report
.\scripts\abby-batch.ps1 -Command update-deps          # Update Python dependencies
.\scripts\abby-batch.ps1 -Command logs-email           # Collect logs for email
.\scripts\abby-batch.ps1 -Command backup-db            # Backup MongoDB
```

**Best for:** Multi-step operations and quick diagnostics

---

## 🎯 Common Workflows

### Fix a Bug and Deploy

```powershell
cd C:\Abby_Discord_Latest

# 1. Edit the file
# (use your editor)

# 2. Test locally
python launch.py
# ... test in Discord ...
# Ctrl+C to stop

# 3. Deploy to TSERVER
.\scripts\deploy-to-tserver.ps1 -Mode quick

# Done! Service will restart automatically
```

### Debug an Issue on TSERVER

```powershell
# 1. SSH in
ssh tserver@100.108.120.82

# 2. Check status
cd C:\abby_bot
.\scripts\abby-service.ps1 -Action status

# 3. View real-time logs
.\scripts\abby-service.ps1 -Action logs-tail

# 4. If needed, launch debug mode to see actual errors
.\scripts\abby-service.ps1 -Action debug
# (Ctrl+C to exit)

# 5. Restart when fixed
.\scripts\abby-service.ps1 -Action restart
```

### Health Check Before Bed

```powershell
# Get comprehensive system report
.\scripts\abby-batch.ps1 -Command health-check

# Output shows:
# - Service status
# - Disk space
# - CPU/Memory usage
# - Any errors in logs
```

### Emergency Service Management

```powershell
# If service won't start:
ssh tserver@100.108.120.82
cd C:\abby_bot
.\scripts\abby-service.ps1 -Action debug
# Look for Python errors

# Then fix and restart:
.\scripts\abby-service.ps1 -Action restart

# Or manually manage without the script:
nssm status AbbyBot     # Check status
nssm stop AbbyBot       # Stop service
nssm start AbbyBot      # Start service
```

---

## 📊 Script Features

### ✨ Smart Features
- ✅ SSH connection validation before deployment
- ✅ Automatic service restart with health check
- ✅ Python cache clearing (prevents stale code)
- ✅ Colored output for easy reading
- ✅ Timestamps on all messages
- ✅ Error handling and recovery suggestions

### 🛡️ Safety Features
- ✅ Confirmation prompts where appropriate
- ✅ Dry-run mode (`-Mode test`) before real deployment
- ✅ Automatic rollback on critical errors
- ✅ Service validation after restart
- ✅ Prevents deployment if service is unhealthy

---

## 🔧 Customization

### Change TSERVER Host

```powershell
# In any script, modify:
[string]$TServerHost = 'tserver@100.108.120.82'

# Or pass as parameter:
.\scripts\deploy-to-tserver.ps1 -TServerHost "newhost@ip.address"
```

### Change Remote Path

```powershell
# In deploy-to-tserver.ps1, modify:
[string]$RemotePath = 'C:\abby_bot'

# Or pass as parameter:
.\scripts\deploy-to-tserver.ps1 -RemotePath "C:\custom\path"
```

---

## 🚨 Troubleshooting

### Scripts won't run?
```powershell
# Enable script execution (run once as admin)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### SSH connection fails?
```powershell
# Verify SSH is installed
ssh -V

# Test connection
ssh tserver@100.108.120.82 "echo test"

# If fails, ensure TSERVER has SSH server running
```

### Deploy takes too long?
```powershell
# Use quick mode instead of full
.\scripts\deploy-to-tserver.ps1 -Mode quick
# Quick: ~30 seconds
# Full: ~45 seconds
```

---

## 📝 Log Locations

- **STDOUT (normal output):** `C:\abby_bot\logs\service_stdout.log`
- **STDERR (errors):** `C:\abby_bot\logs\service_stderr.log`

```powershell
# View on TSERVER
Get-Content C:\abby_bot\logs\service_stdout.log -Tail 50
Get-Content C:\abby_bot\logs\service_stderr.log -Tail 50
```

---

## 📚 Related Documentation

- **DEPLOYMENT_QUICK_REFERENCE.md** - Quick command reference
- **DEPLOYMENT_NSSM.md** - NSSM service setup details
- **REFACTORING_PLAN.md** - Code organization

---

## 💡 Pro Tips

1. **Always test locally first**
   ```powershell
   python launch.py
   ```

2. **Use quick deploy for speed**
   ```powershell
   .\scripts\deploy-to-tserver.ps1 -Mode quick  # Recommended!
   ```

3. **Monitor logs while testing**
   ```powershell
   # In another terminal
   ssh tserver@100.108.120.82
   cd C:\abby_bot
   .\scripts\abby-service.ps1 -Action logs-tail
   ```

4. **Health check regularly**
   ```powershell
   .\scripts\abby-batch.ps1 -Command health-check
   ```

5. **Keep backups**
   ```powershell
   .\scripts\abby-batch.ps1 -Command backup-db
   ```

---

**Version:** 1.0  
**Last Updated:** 2026-01-01  
**Created for:** Abby Discord Bot v2.0 (Refactored)

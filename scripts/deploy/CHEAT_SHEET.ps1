#!/usr/bin/env PowerShell
# ABBY BOT - COMMAND CHEAT SHEET
# Copy/paste these commands as needed

# ═══════════════════════════════════════════════════════════════════════════════
# 🚀 LOCAL DEPLOYMENT (Run from C:\Abby_Discord_Latest)
# ═══════════════════════════════════════════════════════════════════════════════

# Quick deployment (code changes only) - RECOMMENDED
.\scripts\deploy-to-tserver.ps1 -Mode quick

# Full deployment (all files)
.\scripts\deploy-to-tserver.ps1 -Mode full

# Test deployment (dry run, no changes)
.\scripts\deploy-to-tserver.ps1 -Mode test

# ═══════════════════════════════════════════════════════════════════════════════
# 🔧 REMOTE SERVICE MANAGEMENT (SSH'd into TSERVER)
# ═══════════════════════════════════════════════════════════════════════════════

# First, SSH into TSERVER
ssh tserver@100.108.120.82

# Then navigate to bot directory
cd C:\abby_bot

# Check service status
.\scripts\abby-service.ps1 -Action status

# Restart the service
.\scripts\abby-service.ps1 -Action restart

# Start the service
.\scripts\abby-service.ps1 -Action start

# Stop the service
.\scripts\abby-service.ps1 -Action stop

# View last 50 lines of logs
.\scripts\abby-service.ps1 -Action logs

# Follow logs in real-time (Ctrl+C to exit)
.\scripts\abby-service.ps1 -Action logs-tail

# Clear old logs
.\scripts\abby-service.ps1 -Action clear-logs

# Launch debug mode (see actual Python errors)
.\scripts\abby-service.ps1 -Action debug

# ═══════════════════════════════════════════════════════════════════════════════
# 🔗 BATCH OPERATIONS (Run from C:\Abby_Discord_Latest)
# ═══════════════════════════════════════════════════════════════════════════════

# Deploy and restart in one go
.\scripts\abby-batch.ps1 -Command sync-and-restart

# Full system health check
.\scripts\abby-batch.ps1 -Command health-check

# Update Python dependencies
.\scripts\abby-batch.ps1 -Command update-deps

# Collect logs for email
.\scripts\abby-batch.ps1 -Command logs-email

# Backup MongoDB database
.\scripts\abby-batch.ps1 -Command backup-db

# ═══════════════════════════════════════════════════════════════════════════════
# 🛠️ MANUAL NSSM COMMANDS (Direct service management)
# ═══════════════════════════════════════════════════════════════════════════════

# SSH in first
ssh tserver@100.108.120.82

# Check service status
nssm status AbbyBot

# Start service
nssm start AbbyBot

# Stop service
nssm stop AbbyBot

# Restart service
nssm restart AbbyBot

# Edit service configuration (GUI)
nssm edit AbbyBot

# View service logs in Event Viewer
eventvwr.msc

# ═══════════════════════════════════════════════════════════════════════════════
# 📝 MANUAL LOG VIEWING
# ═══════════════════════════════════════════════════════════════════════════════

# SSH in first
ssh tserver@100.108.120.82

# View last 100 lines of STDOUT
Get-Content C:\opt\tdos\apps\abby\logs\service_stdout.log -Tail 100

# View last 100 lines of STDERR
Get-Content C:\opt\tdos\apps\abby\logs\service_stderr.log -Tail 100

# Follow STDOUT in real-time
Get-Content C:\opt\tdos\apps\abby\logs\service_stdout.log -Tail 20 -Wait

# Clear logs
Clear-Content C:\opt\tdos\apps\abby\logs\service_stdout.log
Clear-Content C:\opt\tdos\apps\abby\logs\service_stderr.log

# ═══════════════════════════════════════════════════════════════════════════════
# 🔍 DEBUGGING
# ═══════════════════════════════════════════════════════════════════════════════

# Local testing
cd C:\Abby_Discord_Latest
python launch.py
# Ctrl+C to stop

# Remote debug mode (stop service and run Python manually)
ssh tserver@100.108.120.82
cd C:\opt\tdos\apps\abby
.\scripts\abby-service.ps1 -Action debug
# Ctrl+C to exit

# Check if service is running
ssh tserver@100.108.120.82 "Get-Process python"

# Check disk space on TSERVER
ssh tserver@100.108.120.82 "Get-PSDrive C"

# Check Python version
ssh tserver@100.108.120.82 ".\.venv\Scripts\python --version"

# ═══════════════════════════════════════════════════════════════════════════════
# 📦 DEPENDENCY MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

# Update requirements.txt locally
pip freeze > requirements.txt

# Upload new requirements to TSERVER and install
.\scripts\abby-batch.ps1 -Command update-deps

# Or manually:
ssh tserver@100.108.120.82
cd C:\opt\tdos\apps\abby
.\.venv\Scripts\activate
pip install -r requirements.txt

# ═══════════════════════════════════════════════════════════════════════════════
# 💾 BACKUP & RESTORE
# ═══════════════════════════════════════════════════════════════════════════════

# Backup MongoDB (Needs implement)
.\scripts\abby-batch.ps1 -Command backup-db

# Manual backup
ssh tserver@100.108.120.82
mongodump --out C:\opt\tdos\temp\backup_$(Get-Date -Format 'yyyy-MM-dd')

# Restore MongoDB (if needed)
ssh tserver@100.108.120.82
mongorestore C:\path\to\backup

# ═══════════════════════════════════════════════════════════════════════════════
# 🚨 EMERGENCY RECOVERY
# ═══════════════════════════════════════════════════════════════════════════════

# Service won't start?
# 1. SSH in
ssh tserver@100.108.120.82

# 2. Stop service
nssm stop AbbyBot

# 3. Launch debug mode to see errors
cd C:\opt\tdos\apps\abby
.\scripts\abby-service.ps1 -Action debug

# 4. Fix the issue based on error messages

# 5. Restart service
.\scripts\abby-service.ps1 -Action restart

# Check logs if still failing
.\scripts\abby-service.ps1 -Action logs

# Service keeps crashing?
# Check logs for pattern
Get-Content C:\abby_bot\logs\service_stdout.log -Tail 200

# Review recent changes and rollback if needed
# Then re-deploy corrected code

# ═══════════════════════════════════════════════════════════════════════════════
# 📊 MONITORING & HEALTH
# ═══════════════════════════════════════════════════════════════════════════════

# Full health check
.\scripts\abby-batch.ps1 -Command health-check

# Quick status check
ssh tserver@100.108.120.82 "nssm status AbbyBot"

# CPU & Memory usage
ssh tserver@100.108.120.82 "Get-Process python | Select-Object CPU, Memory"

# Uptime (service start time)
ssh tserver@100.108.120.82 "Get-Process python | Select-Object StartTime"

# Disk space
ssh tserver@100.108.120.82 "Get-PSDrive C | Select-Object Used,Free"

# ═══════════════════════════════════════════════════════════════════════════════
# 📧 SUPPORT
# ═══════════════════════════════════════════════════════════════════════════════

# Collect all logs for support/debugging
.\scripts\abby-batch.ps1 -Command logs-email

# Then attach the files to an email

# ═══════════════════════════════════════════════════════════════════════════════
# 💡 QUICK REFERENCE
# ═══════════════════════════════════════════════════════════════════════════════

<#
TYPICAL WORKFLOW:

1. Local Development
   cd C:\Abby_Discord_Latest
   # Edit code
   python launch.py        # Test locally
   Ctrl+C                 # Stop when done testing

2. Deploy to TSERVER
   .\scripts\deploy-to-tserver.ps1 -Mode quick

3. Monitor Remote
   ssh tserver@100.108.120.82
   cd C:\opt\tdos\apps\abby
   .\scripts\abby-service.ps1 -Action logs-tail

4. If Issues
   .\scripts\abby-service.ps1 -Action debug    # See actual errors
   # Fix the problem
   .\scripts\abby-service.ps1 -Action restart   # Restart

5. Health Check
   .\scripts\abby-batch.ps1 -Command health-check

═══════════════════════════════════════════════════════════════════════════════════
For detailed documentation, see: DEPLOYMENT_QUICK_REFERENCE.md
═══════════════════════════════════════════════════════════════════════════════════
#>

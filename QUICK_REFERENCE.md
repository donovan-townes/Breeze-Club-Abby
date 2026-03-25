# Docker CI/CD Quick Reference Card

**Print this or bookmark it for quick access**

---

## 🚀 Deployment Workflow (5 Steps)

```powershell
# 1. DEVELOP LOCALLY
cd c:\TDOS\apps\abby_bot\docker
.\dev-compose-helper.ps1 up
# Make changes, test in Discord

# 2. VERIFY LOCALLY
docker compose -f docker-compose.dev.yml logs abby | Select-String "System operational"
# Should see: [✓] System operational

# 3. BUILD & PUSH
.\docker\docker-build-push.ps1 -RegistryHost "registry.tdos.internal"
# Wait for: [✓] Build completed, [✓] Push completed

# 4. DEPLOY ON TSERVER
ssh tserver 'cd /srv/tserver/compose && docker compose pull abby && docker compose up -d abby'
# Wait for restart, ~25 seconds

# 5. VERIFY PRODUCTION
ssh tserver 'cd /srv/tserver/compose && docker compose logs abby --tail 50'
# Should see: [✓] System operational
```

---

## 🔧 Essential Commands

### Local Development

```powershell
# Start
.\dev-compose-helper.ps1 up

# View logs
.\dev-compose-helper.ps1 logs -Service abby

# MongoDB shell
.\dev-compose-helper.ps1 db

# Stop
.\dev-compose-helper.ps1 down

# Clean all data (start fresh)
.\dev-compose-helper.ps1 clean
```

### Production (SSH to TSERVER first)

```bash
# Check status
docker compose ps

# View logs
docker compose logs abby --tail 50
docker compose logs -f abby  # Follow

# Restart a service
docker compose restart abby

# Stop all
docker compose down

# Start all
docker compose up -d

# Full restart with latest image
docker compose pull && docker compose up -d
```

---

## 📊 Health Check Indicators

| What         | Local Dev              | Production             | What to Do             |
| ------------ | ---------------------- | ---------------------- | ---------------------- |
| Startup Time | 25-30s                 | 25-30s                 | Normal, wait           |
| Memory       | <1GB                   | <1GB                   | OK                     |
| CPU          | <10%                   | <10%                   | OK                     |
| Discord      | Online in test guild   | Online in prod guilds  | Check /help            |
| Database     | "MongoDB: OK"          | "MongoDB: OK"          | Check logs             |
| Status       | Up X minutes (healthy) | Up X minutes (healthy) | Should always see this |

---

## ⚠️ Troubleshooting (One-Liners)

| Problem                 | Local                                                    | Production                                                 |
| ----------------------- | -------------------------------------------------------- | ---------------------------------------------------------- |
| **Connection refused**  | `.\dev-compose-helper.ps1 restart mongo`                 | `ssh tserver 'docker compose restart mongo'`               |
| **Module not found**    | `.\dev-compose-helper.ps1 build`                         | Rollback: edit docker-compose.yml, use previous image      |
| **Bot offline Discord** | Check DISCORD_TOKEN in .env.dev                          | Check DISCORD_TOKEN in abby.env, restart bot               |
| **Database errors**     | `.\dev-compose-helper.ps1 db` then `db.stats()`          | `ssh tserver 'docker exec mongo mongosh' then `db.stats()` |
| **Disk full**           | `del docker/dev-state`                                   | `ssh tserver 'docker system prune -a'`                     |
| **Port in use**         | `Get-Process \| Where {$_.ProcessName -like "*docker*"}` | Different port or restart service                          |

---

## 📁 File Quick Reference

| File                   | Location                          | Purpose             | Edit?              |
| ---------------------- | --------------------------------- | ------------------- | ------------------ |
| Dockerfile             | `c:\TDOS\apps\abby_bot\`          | Build instructions  | ✓ For code changes |
| docker-compose.dev.yml | `c:\TDOS\apps\abby_bot\docker\`   | Local services      | ✓ For local setup  |
| .env.dev               | `c:\TDOS\apps\abby_bot\docker\`   | Local secrets       | ✓ Your test tokens |
| docker-build-push.ps1  | `c:\TDOS\apps\abby_bot\docker\`   | Build script        | Usually not        |
| docker-compose.yml     | `/srv/tserver/compose/` (TSERVER) | Production services | ✓ Infrastructure   |
| abby.env               | `/srv/tserver/compose/` (TSERVER) | Production secrets  | ✓ Prod config      |

---

## 🔄 Rollback (Emergency)

```bash
# 1. SSH to TSERVER
ssh tserver

# 2. Check available images
cd /srv/tserver/compose
docker image ls | grep abby

# 3. See previous tag (e.g., 1.2.2)
# Output might show: abby  latest  ... and abby  1.2.2  ...

# 4. Edit docker-compose.yml
nano docker-compose.yml
# Change line: image: registry.tdos.internal:5000/abby:1.2.2

# 5. Restart
docker compose up -d abby

# 6. Verify
docker compose logs abby --tail 50
```

---

## 📦 Image Locations

```
Dev Machine Build:
  Input: c:\TDOS\apps\abby_bot\ Dockerfile
  Output: 100.86.240.84:5000/abby:latest

Registry Storage:
  Location: /srv/tserver/state/registry
  Access: registry.tdos.internal:5000 (from TSERVER)
  Access: 100.86.240.84:5000 (from dev machine)

Docker Cache:
  On TSERVER: /var/lib/docker/overlay2/
  On Dev: C:\ProgramData\Docker\
```

---

## 🔐 Secrets & Config

**Never:**

```
❌ git add .env.dev
❌ echo "discord_token_here" in code
❌ Hardcode API keys
❌ Commit /srv/tserver/compose/abby.env
```

**Always:**

```
✓ .env.dev in .gitignore
✓ Secrets in .env files (mounted, not baked)
✓ Different tokens for dev vs prod
✓ Production secrets only on TSERVER
```

---

## 📈 Performance Expectations

| Operation                      | Time                 |
| ------------------------------ | -------------------- |
| Local code change              | 30 seconds (restart) |
| Rebuild dependencies           | 5 minutes            |
| First full build               | 10-15 minutes        |
| Build & push to registry       | 2-3 minutes          |
| Pull from registry (cached)    | 0 seconds            |
| Container startup              | 25-30 seconds        |
| MongoDB init                   | 18-20 seconds        |
| Discord connection             | 3-5 seconds          |
| **Total: Laptop → Production** | **~5 minutes**       |

---

## 🏥 Health Check Checklist

### Before Deployment

- [ ] Local: `[✓] System operational`
- [ ] Local: No errors in last 50 lines of logs
- [ ] Local: Discord bot responds to command
- [ ] Local: `docker compose -f docker-compose.dev.yml ps` shows "healthy"

### After Deployment

- [ ] Production: `[✓] System operational`
- [ ] Production: No errors in last 50 lines
- [ ] Production: Discord bot responds to command
- [ ] Production: `docker compose ps` shows "healthy"
- [ ] Memory: < 1GB
- [ ] CPU: < 10%

---

## 🔗 Multi-Service Connections

```
From Abby (inside container):
  MongoDB → mongo:27017
  Registry → registry:5000  (doesn't connect directly)
  CoreDNS → coredns:53  (doesn't connect directly)

Service Discovery:
  All services on same Docker network: tserver_net
  Services reach each other by name (Docker DNS)
  No IP addresses needed
```

---

## 📞 When in Doubt

| Question                 | Answer                                                                                         |
| ------------------------ | ---------------------------------------------------------------------------------------------- |
| Is my local setup right? | Run: `.\dev-compose-helper.ps1 status`                                                         |
| Can I deploy?            | Check: [PARITY_CHECKLIST.md](PARITY_CHECKLIST.md#before-any-deployment)                        |
| Why is prod different?   | See: [PARITY_CHECKLIST.md](PARITY_CHECKLIST.md#emergency-fix-production-mismatch)              |
| What's the full flow?    | Read: [CI_CD_ARCHITECTURE.md](CI_CD_ARCHITECTURE.md)                                           |
| How do I fix X?          | Search: [DOCKER_MIGRATION_GUIDE.md](DOCKER_MIGRATION_GUIDE.md#problems-encountered--solutions) |

---

## 💡 Pro Tips

**Tip 1:** Keep a terminal open with: `ssh tserver 'watch docker compose ps'`

```
Shows real-time production status
```

**Tip 2:** Before big changes, backup registry:

```powershell
ssh tserver 'tar -czf /srv/tserver/backups/registry-backup-$(date +%s).tar.gz /srv/tserver/state/registry'
```

**Tip 3:** Test infrastructure changes locally first:

```yaml
# In docker-compose.dev.yml, add/test before TSERVER
# Services: redis, postgres, etc.
```

**Tip 4:** Keep dev and prod logs open side-by-side:

```powershell
# Terminal 1: Local
docker compose -f docker-compose.dev.yml logs -f abby

# Terminal 2: Production (SSH)
ssh tserver 'cd /srv/tserver/compose && docker compose logs -f abby'
```

**Tip 5:** Use aliases for faster commands:

```powershell
# Add to PowerShell profile
Set-Alias -Name dev-up -Value "& cd c:\TDOS\apps\abby_bot\docker; .\dev-compose-helper.ps1 up"
Set-Alias -Name dev-logs -Value "& cd c:\TDOS\apps\abby_bot\docker; .\dev-compose-helper.ps1 logs"
Set-Alias -Name prod-ssh -Value "ssh tserver"
```

---

## 🚨 Emergency Procedures

### "Abby is down, I need it back NOW"

```bash
# 1. SSH to TSERVER
ssh tserver
cd /srv/tserver/compose

# 2. Quick restart (30 seconds)
docker compose restart abby

# 3. If still down, pull & start
docker compose pull abby
docker compose up -d abby

# 4. If still down, last known good
docker image ls | grep abby
# Use previous tag: docker compose edit, change image tag
docker compose up -d abby

# 5. If still down, check MongoDB
docker compose ps mongo
docker exec mongo mongosh localhost:27017/test --quiet --eval "db.runCommand('ping')"
```

### "TSERVER is out of disk space"

```bash
ssh tserver
df -h

# Option 1: Clean old images
docker system prune -a

# Option 2: Clean old backups
rm /srv/tserver/backups/*-202401*.tar.gz

# Option 3: Archive MongoDB
docker compose stop mongo
tar -czf /srv/tserver/backups/mongo-archive.tar.gz /srv/tserver/state/mongo/data
rm -rf /srv/tserver/state/mongo/data/*
docker compose up -d mongo
```

---

**Last Updated:** February 9, 2026  
**Keep This Bookmarked** ⭐

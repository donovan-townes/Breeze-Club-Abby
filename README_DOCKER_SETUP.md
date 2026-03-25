# Complete CI/CD & Local Development Setup - Documentation Index

This directory contains comprehensive documentation for the Abby Discord bot's Docker migration and CI/CD pipeline. This index helps you find the right document for your needs.

## 📚 Documentation Structure

### 1. **[DOCKER_MIGRATION_GUIDE.md](DOCKER_MIGRATION_GUIDE.md)** - The Master Reference

**Purpose:** Complete technical reference covering everything about the migration  
**When to Read:** When you need comprehensive context or troubleshooting  
**Contents:**

- Full infrastructure changes on TSERVER
- All code changes in Abby
- Before/After comparison
- All problems encountered and solutions
- Complete operational procedures
- SOP updates needed
- Critical architecture decisions
- Maintenance procedures

**Read This If:**

- You need to understand "why did we do this?"
- You're troubleshooting production issues
- You need to update SOPs
- You want the complete history

---

### 2. **[LOCAL_DEV_QUICKSTART.md](LOCAL_DEV_QUICKSTART.md)** - Get Started in 5 Minutes

**Purpose:** Quick start guide for local development  
**When to Read:** When starting development work  
**Contents:**

- 5-minute setup instructions
- Daily development workflow
- Common commands
- Troubleshooting quick fixes
- Local vs production comparison

**Read This If:**

- You just cloned the repo and want to develop
- You forgot how to start the local environment
- You need a quick troubleshooting answer
- You want to understand the dev workflow

---

### 3. **[CI_CD_ARCHITECTURE.md](CI_CD_ARCHITECTURE.md)** - Complete Deployment Flow

**Purpose:** Visual guide to CI/CD pipeline from dev to production  
**When to Read:** When deploying code or understanding the full flow  
**Contents:**

- Complete deployment flow diagram
- Architectural components explained
- Build strategy details
- Health checks and monitoring
- Rollback procedures
- Performance metrics
- Security considerations

**Read This If:**

- You want to understand the complete flow from laptop to production
- You're deploying code and want to understand each step
- You need to rollback a deployment
- You want to know performance expectations

---

### 4. **[PARITY_CHECKLIST.md](PARITY_CHECKLIST.md)** - Maintain Local/Prod Sync

**Purpose:** Checklist to ensure local dev environment mirrors production  
**When to Read:** Weekly verification, before deployments, when adding features  
**Contents:**

- Weekly parity verification checklist
- Pre-deployment checklist
- Post-deployment verification
- Emergency procedures for mismatches
- Sync procedures

**Read This If:**

- You're about to deploy code
- You want to verify your local setup matches production
- Local and production are behaving differently
- You're making infrastructure changes

---

### 5. **[dev-compose-helper.ps1](dev-compose-helper.ps1)** - Local Dev Tools

**Purpose:** PowerShell helper script for common dev tasks  
**Commands:**

```powershell
.\dev-compose-helper.ps1 up          # Start local environment
.\dev-compose-helper.ps1 down        # Stop containers
.\dev-compose-helper.ps1 logs        # View logs
.\dev-compose-helper.ps1 status      # Check status
.\dev-compose-helper.ps1 db          # Open MongoDB shell
.\dev-compose-helper.ps1 shell       # Open container shell
.\dev-compose-helper.ps1 clean       # Delete all dev data
```

---

### 6. **[docker-compose.dev.yml](docker-compose.dev.yml)** - Local Environment Definition

**Purpose:** Docker Compose configuration for local development  
**What It Does:**

- Defines MongoDB service for local dev
- Defines Abby service with code mounts
- Sets up networking between services
- Configures persistent storage

**How to Use:**

```powershell
docker compose -f docker-compose.dev.yml up
```

---

### 7. **[.env.dev.example](.env.dev.example)** - Environment Template

**Purpose:** Template for environment variables  
**What to Do:**

1. Copy to `.env.dev` (git-ignored)
2. Fill in your test Discord token
3. Fill in your test guild IDs
4. Fill in your OpenAI key

**Key Fields:**

- `DISCORD_TOKEN` - TEST bot token (not production!)
- `GUILD_IDS` - TEST Discord server IDs
- `OPENAI_API_KEY` - Dev API key
- `LOG_LEVEL` - Set to DEBUG for development

---

## 🚀 Quick Navigation by Task

### I want to...

**Start developing locally**

1. Read: [LOCAL_DEV_QUICKSTART.md](LOCAL_DEV_QUICKSTART.md)
2. Copy `.env.dev.example` to `.env.dev`
3. Fill in your test Discord token
4. Run: `.\dev-compose-helper.ps1 up`

**Deploy code to production**

1. Read: [PARITY_CHECKLIST.md](PARITY_CHECKLIST.md#before-any-deployment)
2. Run: `.\docker\docker-build-push.ps1`
3. SSH to TSERVER
4. Run: `cd /srv/tserver/compose && docker compose pull abby && docker compose up -d abby`
5. Verify: `docker compose logs abby --tail 50`

**Understand the complete flow**

1. Read: [CI_CD_ARCHITECTURE.md](CI_CD_ARCHITECTURE.md)
2. Focus on the main flow diagram
3. Review the "Deployment Checklist" section

**Fix a production issue**

1. Read: [DOCKER_MIGRATION_GUIDE.md](DOCKER_MIGRATION_GUIDE.md#problems-encountered--solutions)
2. Check troubleshooting in [LOCAL_DEV_QUICKSTART.md](LOCAL_DEV_QUICKSTART.md#troubleshooting)
3. Reproduce locally first, then verify production fix

**Verify local matches production**

1. Read: [PARITY_CHECKLIST.md](PARITY_CHECKLIST.md)
2. Run through the checklist before deployment

**Understand why we did this**

1. Read: [DOCKER_MIGRATION_GUIDE.md](DOCKER_MIGRATION_GUIDE.md#before-vs-after-why-docker-migration-was-needed)
2. Check specific problems in [DOCKER_MIGRATION_GUIDE.md](DOCKER_MIGRATION_GUIDE.md#problems-encountered--solutions)

**Update infrastructure (MongoDB version, add Redis, etc.)**

1. Test locally first in [docker-compose.dev.yml](docker-compose.dev.yml)
2. Once tested locally, update production [/srv/tserver/compose/docker-compose.yml](../../docker-compose.yml)
3. Deploy with: `.\docker\docker-build-push.ps1`

**Troubleshoot a local issue**

1. Read: [LOCAL_DEV_QUICKSTART.md#troubleshooting](LOCAL_DEV_QUICKSTART.md#troubleshooting)
2. Use: `.\dev-compose-helper.ps1 logs`
3. Check MongoDB: `.\dev-compose-helper.ps1 db`

---

## 🏗️ Architecture at a Glance

```
┌─ Your Windows Machine ──────────────┐
│  docker-compose.dev.yml             │
│  ├─ MongoDB (local)                 │
│  └─ Abby (local build)              │
│                                     │
│  YOU: Code → Test → Iterate         │
│                                     │
│  .\docker-build-push.ps1            │
│  └─ Build & Push → Registry         │
└──────────────┬──────────────────────┘
               │ (Tailscale VPN)
               ↓
┌─ TSERVER (Ubuntu Linux) ────────────┐
│  /srv/tserver/compose/              │
│  ├─ docker-compose.yml              │
│  ├─ abby.env (production config)    │
│  ├─ coredns/ (DNS)                  │
│  └─ state/                          │
│      ├─ mongo/ (shared DB)          │
│      └─ abby/ (bot data)            │
│                                     │
│  registry.tdos.internal:5000        │
│  ├─ abby:latest (your image)        │
│  └─ (all versions for rollback)     │
│                                     │
│  BOT RUNNING: Serving 4 guilds      │
└─────────────────────────────────────┘
```

---

## 📋 File Organization

```
c:\TDOS\apps\abby_bot\
├── DOCKER_MIGRATION_GUIDE.md      ← Master reference
├── LOCAL_DEV_QUICKSTART.md         ← Start here
├── CI_CD_ARCHITECTURE.md           ← Deployment flow
├── PARITY_CHECKLIST.md             ← Before deployment
├── Dockerfile                       ← Multi-stage build
├── requirements.txt                ← Dependencies
├── launch.py                       ← Entry point (env loading)
│
└── docker/
    ├── dev-compose-helper.ps1      ← Helper script
    ├── docker-compose.dev.yml      ← Local environment
    ├── docker-compose.yml          ← (TSERVER version)
    ├── docker-build-push.ps1       ← Build & deploy
    ├── .env.dev.example            ← Environment template
    │
    ├── dev-state/                  ← Local data (git-ignored)
    │   ├── mongo/
    │   └── abby/
    │
    ├── coredns/
    │   ├── Corefile
    │   └── tdos.internal.db
    │
    └── caddy/
        └── Caddyfile
```

---

## 🔑 Key Concepts

### Local Dev ↔ Production Parity

- **Same Dockerfile** = Same application
- **Different .env** = Different configuration
- **What works locally → Push to registry → Works on production**

### Three-Layer Architecture

1. **Local Development** (Windows Docker)
2. **Image Registry** (TSERVER Docker Registry)
3. **Production Deployment** (TSERVER Docker Compose)

### CI/CD Without CI/CD Server

- No GitHub Actions, Jenkins, etc.
- Manual but simple workflow:
  1. Develop & test locally
  2. Build & push: `.\docker-build-push.ps1`
  3. Deploy on TSERVER: SSH + docker compose

### Database Strategy

- **No authentication** (network isolation sufficient)
- **Shared MongoDB service** (all apps use same DB)
- **Multiple databases** (abby, future-app-1, future-app-2)

---

## ⚡ Common Operations

### Start Local Development

```powershell
cd c:\TDOS\apps\abby_bot\docker
.\dev-compose-helper.ps1 up
```

### Stop Local Development

```powershell
.\dev-compose-helper.ps1 down
```

### View Logs Locally

```powershell
.\dev-compose-helper.ps1 logs -Service abby
```

### Deploy to Production

```powershell
.\docker\docker-build-push.ps1 -RegistryHost "registry.tdos.internal"
ssh tserver 'cd /srv/tserver/compose && docker compose pull abby && docker compose up -d abby'
```

### Check Production Status

```bash
ssh tserver 'cd /srv/tserver/compose && docker compose ps'
ssh tserver 'cd /srv/tserver/compose && docker compose logs abby --tail 50'
```

### Rollback to Previous Version

```bash
ssh tserver
cd /srv/tserver/compose
# Check available versions
docker image ls | grep abby
# Edit docker-compose.yml to use previous tag
# docker compose up -d abby
```

---

## 🛡️ Safety Guidelines

### ✅ Always Do These

- [ ] Test locally before deploying
- [ ] Check local logs for errors before pushing
- [ ] Run parity checklist before deployment
- [ ] Use test Discord server for local development
- [ ] Keep .env.dev out of git (add to .gitignore)
- [ ] Backup data before major changes

### ❌ Never Do These

- [ ] Use production Discord token in local .env
- [ ] Commit .env files to git
- [ ] Delete /srv/tserver/state without backup
- [ ] Edit production config without testing locally first
- [ ] Run docker system prune on production (deletes images)
- [ ] Change Dockerfile without rebuilding locally

---

## 📞 Support

### For Questions About...

**Local Development:** [LOCAL_DEV_QUICKSTART.md](LOCAL_DEV_QUICKSTART.md)

**Deployment Process:** [CI_CD_ARCHITECTURE.md](CI_CD_ARCHITECTURE.md)

**Architecture Decisions:** [DOCKER_MIGRATION_GUIDE.md](DOCKER_MIGRATION_GUIDE.md#critical-knowledge-base)

**Troubleshooting:** [LOCAL_DEV_QUICKSTART.md#troubleshooting](LOCAL_DEV_QUICKSTART.md#troubleshooting)

**Pre-Deployment Verification:** [PARITY_CHECKLIST.md](PARITY_CHECKLIST.md)

**Complete Reference:** [DOCKER_MIGRATION_GUIDE.md](DOCKER_MIGRATION_GUIDE.md)

---

## 📝 Document Maintenance

| Document                  | Last Updated | Next Review | Owner       |
| ------------------------- | ------------ | ----------- | ----------- |
| DOCKER_MIGRATION_GUIDE.md | Feb 9, 2026  | Mar 9, 2026 | [Your Name] |
| LOCAL_DEV_QUICKSTART.md   | Feb 9, 2026  | Mar 9, 2026 | [Your Name] |
| CI_CD_ARCHITECTURE.md     | Feb 9, 2026  | Mar 9, 2026 | [Your Name] |
| PARITY_CHECKLIST.md       | Feb 9, 2026  | Mar 9, 2026 | [Your Name] |
| README.md (this file)     | Feb 9, 2026  | Mar 9, 2026 | [Your Name] |

---

**Happy deploying! 🚀**

For questions or issues, refer to the appropriate document from the table above, or check the complete [DOCKER_MIGRATION_GUIDE.md](DOCKER_MIGRATION_GUIDE.md).

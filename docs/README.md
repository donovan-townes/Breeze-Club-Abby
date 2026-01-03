# 📚 Abby Documentation

Welcome to the comprehensive documentation for Abby, the AI-powered Discord bot for the Breeze Club community.

## 🚀 Quick Navigation

### For New Users

👉 **[Getting Started](getting-started/)** — Installation, configuration, and quick start  
👉 **[Features](features/)** — Learn what Abby can do  
👉 **[Common Issues](getting-started/troubleshooting.md)** — Troubleshooting guide

### For Developers

👉 **[Architecture](architecture/)** — System design and code organization  
👉 **[API Reference](api-reference/)** — Complete API documentation  
👉 **[Contributing](contributing/)** — How to contribute code

### For DevOps/SRE

👉 **[Deployment](deployment/)** — Production deployment guides  
👉 **[Monitoring](deployment/monitoring.md)** — Health checks and metrics  
👉 **[Backup & Recovery](deployment/backup-recovery.md)** — Data protection

---

## 📖 Documentation Structure

### 🏁 [Getting Started](getting-started/)

Everything you need to get Abby running in your Discord server.

**Contents:**

- **[Installation Guide](getting-started/installation.md)** — Step-by-step setup
- **[Configuration Guide](getting-started/configuration.md)** — Environment variables and settings
- **[Quick Start Tutorial](getting-started/quick-start.md)** — Get up and running in 10 minutes
- **[Docker Deployment](getting-started/docker.md)** — Containerized deployment
- **[Troubleshooting](getting-started/troubleshooting.md)** — Common issues and solutions

**Time to complete**: 30-60 minutes for full setup

---

### 🏗️ [Architecture](architecture/)

Understand how Abby is designed, built, and structured.

**Contents:**

- **[Architecture Overview](architecture/ARCHITECTURE.md)** ⭐ — Core design principles and patterns
- **[Database Schema](architecture/database-schema.md)** — MongoDB collections and indexes
- **[Storage System](architecture/STORAGE_SYSTEM.md)** — File management and quotas
- **[LLM & RAG Architecture](architecture/llm-rag-architecture.md)** — AI system design
- **[Cog System](architecture/cog-system.md)** — Command organization
- **[Security Architecture](architecture/security.md)** — Security practices

**Essential reading for**: Contributors, architects, and anyone adding features

---

### ✨ [Features](features/)

Detailed guides for each of Abby's features and capabilities.

**AI & Conversational:**

- **[Conversational AI (Chatbot)](features/chatbot.md)** — Natural language conversations
- **[RAG System](features/RAG_USAGE_GUIDE.md)** — Document-aware AI responses
- **[TDOS Memory System](features/tdos-memory.md)** — Advanced memory and learning

**Creative Tools:**

- **[Image Generation](features/image-generation.md)** — AI-powered image creation
- **[Text Analysis](features/text-analysis.md)** — Sentiment and content analysis

**Economy & Progression:**

- **[XP & Leveling System](features/economy-xp.md)** — Experience and progression
- **[Banking & Currency](features/banking.md)** — User economy

**Integrations:**

- **[Twitch Integration](features/twitch.md)** — Live stream notifications
- **[URL Handlers](features/url-handlers.md)** — Auto-embeds for links

**Moderation:**

- **[Auto-Moderation](features/moderation.md)** — Content filtering and nudges
- **[Greetings & MOTD](features/greetings.md)** — Welcome messages

---

### 📘 [API Reference](api-reference/)

Complete API documentation for developers.

**Core Services:**

- **[Storage API](api-reference/STORAGE_API_REFERENCE.md)** — File management
- **[LLM Client API](api-reference/LLM_CONFIGURATION.md)** — Language models
- **[RAG API](api-reference/rag-api.md)** — Vector search
- **[Economy API](api-reference/economy-api.md)** — XP and banking
- **[Database API](api-reference/database-api.md)** — MongoDB operations
- **[Image Generation API](api-reference/image-generation-api.md)** — Stability AI
- **[Persona API](api-reference/persona-api.md)** — Personality system
- **[Security API](api-reference/security-api.md)** — Encryption
- **[Logging API](api-reference/logging-api.md)** — Observability

**For**: Developers building on or extending Abby

---

### 🚀 [Deployment](deployment/)

Production deployment and infrastructure setup.

**Deployment Guides:**

- **[NSSM Deployment (Windows)](deployment/DEPLOYMENT_NSSM.md)** — Windows Service
- **[systemd Deployment (Linux)](deployment/systemd-deployment.md)** — Linux Service
- **[Docker Deployment](deployment/docker-deployment.md)** — Containers
- **[Cloud Deployments](deployment/cloud/)** — AWS, Azure, GCP, DigitalOcean

**Infrastructure:**

- **[MongoDB Setup](deployment/mongodb-setup.md)** — Database configuration
- **[Qdrant Setup](deployment/qdrant-setup.md)** — Vector database
- **[Secrets Management](deployment/secrets-management.md)** — Credential security

**Operations:**

- **[Monitoring](deployment/monitoring.md)** — Health checks and metrics
- **[Backup & Recovery](deployment/backup-recovery.md)** — Data protection
- **[Maintenance](deployment/maintenance.md)** — Routine tasks

**For**: DevOps engineers, system administrators, and production deployments

---

### 🤝 [Contributing](contributing/)

Guidelines and resources for contributing to Abby.

**Getting Started:**

- **[Development Setup](contributing/development-setup.md)** — Local environment
- **[Code Style Guide](contributing/code-style.md)** — Python standards
- **[Testing Guide](contributing/testing.md)** — Writing tests
- **[Pull Request Guide](contributing/pull-request-guide.md)** — Submission workflow

**Contribution Areas:**

- **[Adding New Features](contributing/adding-features.md)** — Feature development
- **[Adding a New Cog](contributing/adding-cogs.md)** — Discord commands
- **[Extending the LLM System](contributing/extending-llm.md)** — AI integrations
- **[Adding Database Collections](contributing/adding-collections.md)** — Data models
- **[API Integrations](contributing/api-integrations.md)** — External services

**Community:**

- **[Code of Conduct](contributing/code-of-conduct.md)** — Community standards
- **[Recognition Program](contributing/recognition.md)** — Contributor credits

**For**: Anyone wanting to contribute code, documentation, or ideas

---

## 🎯 Documentation by Role

### 👤 I'm a Discord Server Admin

**Goal**: Set up and manage Abby in my server

**Read this:**

1. [Installation Guide](getting-started/installation.md) — Get Abby running
2. [Configuration Guide](getting-started/configuration.md) — Customize settings
3. [Features Overview](features/) — Learn what Abby can do
4. [Troubleshooting](getting-started/troubleshooting.md) — Fix common issues

**Time**: 1-2 hours

---

### 💻 I'm a Developer Contributing to Abby

**Goal**: Add features or fix bugs

**Read this:**

1. [Architecture Overview](architecture/ARCHITECTURE.md) — Understand the design
2. [Code Style Guide](contributing/code-style.md) — Follow conventions
3. [API Reference](api-reference/) — Learn the APIs
4. [Pull Request Guide](contributing/pull-request-guide.md) — Submit changes

**Time**: 2-3 hours to get oriented

---

### 🔧 I'm DevOps/SRE Deploying to Production

**Goal**: Deploy and maintain Abby reliably

**Read this:**

1. [Deployment Guide](deployment/) — Choose deployment method
2. [MongoDB Setup](deployment/mongodb-setup.md) — Configure database
3. [Monitoring](deployment/monitoring.md) — Set up observability
4. [Backup & Recovery](deployment/backup-recovery.md) — Protect data

**Time**: 3-4 hours for full production setup

---

### 🎨 I'm Integrating Abby's Features into Another App

**Goal**: Use Abby's core services programmatically

**Read this:**

1. [Architecture Overview](architecture/ARCHITECTURE.md) — Understand separation
2. [API Reference](api-reference/) — Learn available APIs
3. [Database Schema](architecture/database-schema.md) — Understand data models
4. [Security Architecture](architecture/security.md) — Secure integration

**Time**: 2-3 hours

---

## 📝 Key Documents (Start Here)

### For Everyone

- **[Main README](../README.md)** — Project overview and features
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** — Contribution guidelines

### Most Referenced Docs

1. **[Architecture Overview](architecture/ARCHITECTURE.md)** — System design (⭐ essential)
2. **[Storage System](architecture/STORAGE_SYSTEM.md)** — File management
3. **[RAG Usage Guide](features/RAG_USAGE_GUIDE.md)** — AI knowledge base
4. **[LLM Configuration](api-reference/LLM_CONFIGURATION.md)** — AI setup
5. **[NSSM Deployment](deployment/DEPLOYMENT_NSSM.md)** — Windows production

---

## 🔍 Finding What You Need

### By Topic

**Setting Up Abby:**

- Local development → [Installation Guide](getting-started/installation.md)
- Production deployment → [Deployment](deployment/)
- Configuration → [Configuration Guide](getting-started/configuration.md)

**Using Features:**

- Chatbot → [Conversational AI](features/chatbot.md)
- Image generation → [Image Generation](features/image-generation.md)
- XP system → [Economy & XP](features/economy-xp.md)
- Twitch → [Twitch Integration](features/twitch.md)

**Building/Extending:**

- Add commands → [Adding Cogs](contributing/adding-cogs.md)
- Use APIs → [API Reference](api-reference/)
- Understand design → [Architecture](architecture/)

**Operations:**

- Deploy → [Deployment Guides](deployment/)
- Monitor → [Monitoring](deployment/monitoring.md)
- Backup → [Backup & Recovery](deployment/backup-recovery.md)

---

## 📊 Documentation Coverage

| Category            | Documents | Status       |
| ------------------- | --------- | ------------ |
| **Getting Started** | 5         | ✅ Complete  |
| **Architecture**    | 7         | ✅ Complete  |
| **Features**        | 12+       | ✅ Complete  |
| **API Reference**   | 9         | 🔄 Expanding |
| **Deployment**      | 10+       | ✅ Complete  |
| **Contributing**    | 10+       | ✅ Complete  |

**Total Documents**: 50+  
**Last Major Update**: January 2026

---

## 🆘 Get Help

### Documentation Issues

- **Unclear or outdated?** [Open an issue](https://github.com/your-org/abby/issues/new?labels=documentation)
- **Missing docs?** [Request new documentation](https://github.com/your-org/abby/issues/new?labels=documentation,enhancement)

### Technical Support

- **Discord**: [Breeze Club Server](https://discord.gg/yGsBGQAC49)
- **GitHub Issues**: [Report a bug](https://github.com/your-org/abby/issues)
- **Discussions**: [Ask questions](https://github.com/your-org/abby/discussions)

### Contributing to Docs

See [Documentation Style Guide](contributing/documentation-style.md) for guidelines on improving documentation.

---

## 🗺️ Documentation Roadmap

### Current Focus

- ✅ Core architecture documentation
- ✅ API reference completion
- ✅ Deployment guides
- 🔄 Code examples and tutorials

### Upcoming

- Video tutorials for common tasks
- Interactive API playground
- Docusaurus site deployment
- Multi-language support (Spanish, French)

---

**Built with ❤️ for the Breeze Club community**

_"Documentation is love for future you and your team."_

**Time**: 5-10 minutes per lookup  
**What**: API documentation and code snippets

Best for:

- Quick API lookups
- Copy-paste examples
- Common patterns
- Error messages
- Testing

### 5. **ARCHITECTURE_AUDIT.md** 📋 DETAILED AUDIT

**Time**: 15-20 minutes  
**What**: Complete audit findings, module-by-module analysis

Best for:

- Understanding what was audited
- Seeing audit results in detail
- Module assessment
- Historical record
- Validation of separation

### 6. **AUDIT_AND_REDESIGN_SUMMARY.md** 📊 DETAILED SUMMARY

**Time**: 10-15 minutes  
**What**: Complete summary of audit and redesign work

Best for:

- Comprehensive overview
- Understanding all changes
- Deployment checklist
- What was created/modified
- Key metrics

---

## 🎯 Quick Navigation by Role

### 👨‍💻 Developer (Working on Image Generation)

1. Read: **ARCHITECTURE.md** (understand boundaries)
2. Reference: **STORAGE_SYSTEM.md** (migration guide)
3. Keep open: **STORAGE_API_REFERENCE.md** (while coding)
4. Test using: Examples in STORAGE_SYSTEM.md

### 🏗️ Architect (Design Review)

1. Read: **ARCHITECTURE_AUDIT.md** (findings)
2. Review: **ARCHITECTURE.md** (design decisions)
3. Check: **STORAGE_SYSTEM.md** (implementation)
4. Validate: QUICK_SUMMARY.md (success criteria)

### 📋 DevOps/Deployment

1. Read: **QUICK_SUMMARY.md** (overview)
2. Reference: **STORAGE_SYSTEM.md** (setup section)
3. Check: Environment variables section
4. Use: Deployment checklist

### 🧪 QA/Tester

1. Read: **STORAGE_SYSTEM.md** (what was added)
2. Reference: **STORAGE_API_REFERENCE.md** (testing section)
3. Use: Test script example
4. Verify: Quota system behavior

---

## 🗂️ Organization by Topic

### Understanding Architecture

- **ARCHITECTURE.md** - Design principles (primary)
- **ARCHITECTURE_AUDIT.md** - Audit findings
- **QUICK_SUMMARY.md** - Visual overview

### Implementing Storage System

- **STORAGE_SYSTEM.md** - Complete guide (primary)
- **STORAGE_API_REFERENCE.md** - API reference
- **ARCHITECTURE.md** - Design context

### Quota Management

- **STORAGE_SYSTEM.md** - Quota system details
- **STORAGE_API_REFERENCE.md** - Quota API
- **QUICK_SUMMARY.md** - Configuration

### Configuration

- **QUICK_SUMMARY.md** - Env vars list
- **STORAGE_API_REFERENCE.md** - Config section
- **STORAGE_SYSTEM.md** - Detailed config

### Migration Guide

- **STORAGE_SYSTEM.md** - Migration steps (primary)
- **STORAGE_API_REFERENCE.md** - Before/after patterns
- **ARCHITECTURE.md** - Best practices

---

## 🔑 Key Concepts

### Core vs Adapter Separation

- **Core** (abby_core/) = Logic reusable by any adapter
- **Adapter** (abby_adapters/) = Framework-specific implementation
- **Rule**: Core never imports from adapter

See: ARCHITECTURE.md, ARCHITECTURE_AUDIT.md

### Storage System

- **StorageManager** = File operations + quota enforcement
- **QuotaManager** = Quota tracking and limits
- **ImageGenerator** = Image generation API (core service)

See: STORAGE_SYSTEM.md, STORAGE_API_REFERENCE.md

### Quota Types

- **Per-user** (500MB default) = Prevent individual hoarding
- **Global** (5GB default) = Prevent server bloat
- **Daily** (5 gens/day default) = Prevent API spam
- **Auto-cleanup** (7 days default) = Remove old temps

See: STORAGE_SYSTEM.md, QUICK_SUMMARY.md

---

## 📈 Reading Path by Experience Level

### Beginner (New to Project)

1. QUICK_SUMMARY.md (5 min) - Get overview
2. ARCHITECTURE.md (30 min) - Learn design
3. STORAGE_SYSTEM.md (20 min) - Understand storage
4. STORAGE_API_REFERENCE.md - As needed

Total: ~55 minutes to understand everything

### Intermediate (Familiar with Codebase)

1. QUICK_SUMMARY.md (5 min) - Quick overview
2. STORAGE_SYSTEM.md (15 min) - Migration patterns
3. STORAGE_API_REFERENCE.md - As needed

Total: ~20 minutes, then reference as needed

### Advanced (Architecture Review)

1. ARCHITECTURE_AUDIT.md (15 min) - Audit findings
2. ARCHITECTURE.md (15 min) - Decision review
3. QUICK_SUMMARY.md (5 min) - Validation

Total: ~35 minutes review

---

## 📋 File Locations

```
docs/
├── QUICK_SUMMARY.md               ⭐ Start here
├── ARCHITECTURE.md                ⭐ Essential reading
├── STORAGE_SYSTEM.md              📖 Implementation guide
├── STORAGE_API_REFERENCE.md       🔍 Quick reference
├── ARCHITECTURE_AUDIT.md          📋 Detailed audit
├── AUDIT_AND_REDESIGN_SUMMARY.md  📊 Complete summary
└── (this index)

abby_core/
├── storage/                       ✅ NEW
│   ├── __init__.py
│   ├── storage_manager.py         (StorageManager class)
│   └── quota_manager.py           (QuotaManager class)
└── generation/                    ✅ NEW
    ├── __init__.py
    └── image_generator.py         (ImageGenerator class)

abby_adapters/discord/
└── config.py                      (Modified - added StorageConfig)
```

---

## ✅ What You'll Learn

### From ARCHITECTURE.md

- [ ] Layer separation principle
- [ ] Why separating core/adapters matters
- [ ] Where code belongs (decision matrix)
- [ ] Common mistakes and fixes
- [ ] Visual architecture diagrams
- [ ] Complete working examples

### From STORAGE_SYSTEM.md

- [ ] How StorageManager works
- [ ] How quota tracking works
- [ ] Migration patterns for existing code
- [ ] Configuration setup
- [ ] Directory structure
- [ ] Troubleshooting guide

### From STORAGE_API_REFERENCE.md

- [ ] StorageManager API
- [ ] ImageGenerator API
- [ ] Configuration reference
- [ ] Copy-paste code patterns
- [ ] Common errors and solutions
- [ ] Testing examples

### From ARCHITECTURE_AUDIT.md

- [ ] Module-by-module assessment
- [ ] Issues found with severity
- [ ] Verification checklist
- [ ] Migration path
- [ ] Proper vs current state

---

## 🚀 Getting Started

### Step 1: Understand the Problem (5 min)

Read: QUICK_SUMMARY.md - "Key Findings" section

### Step 2: Learn the Solution (30 min)

Read: ARCHITECTURE.md - "Layer Model" through "Examples"

### Step 3: Implement the Solution (2-3 hours)

Reference: STORAGE_SYSTEM.md - "Migration Steps" section

### Step 4: Debug Issues (as needed)

Reference: STORAGE_API_REFERENCE.md - "Error Messages" and "Troubleshooting"

---

## 🔍 Document Relationships

```
QUICK_SUMMARY.md (Overview)
    ↓
    ├─→ ARCHITECTURE.md (Design principles)
    │       └─→ ARCHITECTURE_AUDIT.md (Findings)
    │
    ├─→ STORAGE_SYSTEM.md (Implementation)
    │       └─→ STORAGE_API_REFERENCE.md (API details)
    │
    └─→ AUDIT_AND_REDESIGN_SUMMARY.md (Complete picture)
```

---

## 📞 Frequently Checked Sections

### "Where should I put this code?"

→ ARCHITECTURE.md - "What Goes Where: Decision Matrix"

### "How do I use the storage system?"

→ STORAGE_API_REFERENCE.md - "StorageManager API"

### "How do I check quotas?"

→ STORAGE_API_REFERENCE.md - "Pattern 2: Check All Quotas"

### "What's the config error?"

→ QUICK_SUMMARY.md - "The Config Error (Root Cause)"

### "How do I migrate existing code?"

→ STORAGE_SYSTEM.md - "Migration Path"

### "What are the limits?"

→ STORAGE_SYSTEM.md - "Quota System Details"

### "What gets stored where?"

→ QUICK_SUMMARY.md - "Storage Directory Structure"

### "What env vars do I need?"

→ STORAGE_API_REFERENCE.md - "Configuration"

---

## 🎓 Learning Checklist

- [ ] Read QUICK_SUMMARY.md
- [ ] Read ARCHITECTURE.md completely
- [ ] Review STORAGE_SYSTEM.md migration steps
- [ ] Bookmark STORAGE_API_REFERENCE.md for reference
- [ ] Review ARCHITECTURE_AUDIT.md findings
- [ ] Understand decision matrix from ARCHITECTURE.md
- [ ] Test code patterns from STORAGE_API_REFERENCE.md
- [ ] Ready to implement Phase 2!

---

## 💡 Pro Tips

1. **Keep STORAGE_API_REFERENCE.md open** while coding - it's your reference guide
2. **Reference ARCHITECTURE.md** when uncertain about code placement
3. **Use patterns from STORAGE_SYSTEM.md** as templates
4. **Bookmark sections** you'll check frequently
5. **Print the decision matrix** from ARCHITECTURE.md

---

## 📧 Questions?

Look in this order:

1. **STORAGE_API_REFERENCE.md** - Quick answers
2. **STORAGE_SYSTEM.md** - Implementation details
3. **ARCHITECTURE.md** - Design decisions
4. **ARCHITECTURE_AUDIT.md** - What was found
5. **QUICK_SUMMARY.md** - Big picture

---

## 🏁 Conclusion

You now have:

- ✅ Complete audit of architecture
- ✅ Identified and fixed critical issues
- ✅ New storage system with quotas
- ✅ New image generation service
- ✅ 6 comprehensive documentation files
- ✅ Clear implementation path

**Next step:** Start Phase 2 (update image generation code)  
**Estimated time:** 3-4 hours  
**Reference:** STORAGE_SYSTEM.md

# Architecture Documentation

Understanding how Abby is designed, built, and structured.

## 📚 Contents

### [Architecture Overview](ARCHITECTURE.md) ⭐ **START HERE**

Core design principles, layer separation, and architectural patterns.

**Topics covered:**

- Clean architecture principles (core vs. adapters)
- Layer model and dependency flow
- Where to put new code
- Common architectural mistakes
- Working examples and patterns

**Essential reading for**: All developers contributing to Abby

---

### [Database Schema](database-schema.md)

MongoDB collections, document structures, and indexing strategies.

**Topics covered:**

- Collection overview (`user_xp`, `discord_profiles`, `sessions`, etc.)
- Document schemas with examples
- Index definitions and query patterns
- Multi-tenancy and guild isolation
- Migration strategies

---

### [Storage System](STORAGE_SYSTEM.md)

File management, quota system, and image storage architecture.

**Topics covered:**

- Directory structure for user uploads
- Quota enforcement (global, per-user, per-guild)
- Automatic cleanup policies
- Storage API usage examples
- Role-based quota overrides

---

### [LLM & RAG Architecture](llm-rag-architecture.md)

Language model integration, RAG system, and vector database design.

**Topics covered:**

- LLM provider abstraction (OpenAI/Ollama)
- Conversation management and context windows
- RAG pipeline (ingestion, embedding, retrieval)
- Vector database comparison (Qdrant vs. Chroma)
- Memory system integration (TDOS Memory)

---

### [Cog System](cog-system.md)

Discord.py cog architecture, command organization, and dynamic loading.

**Topics covered:**

- Cog categories (admin, creative, economy, utility)
- Command registration (slash commands vs. prefix commands)
- Dynamic cog loading and reloading
- Event listeners and hooks
- Inter-cog communication

---

### [Module Dependency Graph](dependencies.md)

Visual and textual representation of module dependencies.

**Topics covered:**

- Core module dependencies
- Adapter-to-core relationships
- External library usage
- Circular dependency prevention
- Import organization standards

---

### [Security Architecture](security.md)

Security practices, encryption, and credential management.

**Topics covered:**

- Conversation encryption (at rest)
- API key management (.env best practices)
- Rate limiting and abuse prevention
- Input validation and sanitization
- Permission hierarchy

---

### [Audit Reports](audits/)

Historical architectural audits and redesign documentation.

**Contents:**

- [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md) — Phase 1 audit findings
- [AUDIT_AND_REDESIGN_SUMMARY.md](AUDIT_AND_REDESIGN_SUMMARY.md) — Complete redesign summary
- [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md) — Implementation tracking

---

## 🎯 Reading Order by Role

### For Vision & Planning

1. **[Abby Role & Modes](ABBY_ROLE_AND_MODES.md)** — What Abby is (portal), operating modes, guardrails
2. **[Roadmap](ROADMAP.md)** — Phase sequencing aligned to architecture and modes
3. **[Architecture Overview](ARCHITECTURE.md)** — Design principles

### For New Developers

1. **[Architecture Overview](ARCHITECTURE.md)** — Understand the big picture
2. **[Cog System](cog-system.md)** — Learn command structure
3. **[Database Schema](database-schema.md)** — Understand data models

### For Core Contributors

1. **[Architecture Overview](ARCHITECTURE.md)** — Design principles
2. **[Module Dependency Graph](dependencies.md)** — Avoid circular deps
3. **[LLM & RAG Architecture](llm-rag-architecture.md)** — Advanced AI systems

### For DevOps/SRE

1. **[Database Schema](database-schema.md)** — Data persistence
2. **[Storage System](STORAGE_SYSTEM.md)** — File system requirements
3. **[Security Architecture](security.md)** — Security checklist

---

## 🔍 Quick Reference

| Need to...                | Read this                                         |
| ------------------------- | ------------------------------------------------- |
| Add a new command         | [Cog System](cog-system.md)                       |
| Add database collection   | [Database Schema](database-schema.md)             |
| Integrate an AI service   | [LLM & RAG Architecture](llm-rag-architecture.md) |
| Store user files          | [Storage System](STORAGE_SYSTEM.md)               |
| Fix import errors         | [Module Dependency Graph](dependencies.md)        |
| Review security practices | [Security Architecture](security.md)              |

---

## 📖 Related Documentation

- **[Getting Started](../getting-started/)** — Installation and setup
- **[API Reference](../api-reference/)** — Detailed API docs
- **[Features](../features/)** — Feature-specific implementations
- **[Contributing](../contributing/)** — Development workflow

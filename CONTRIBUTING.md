# Contributing to Abby

Thank you for your interest in contributing to Abby! This document provides guidelines and workflows for contributing to the project.

## 🚀 Quick Start

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a feature branch** from `main`
4. **Make your changes** following our standards
5. **Test thoroughly** before submitting
6. **Submit a Pull Request** to the `main` branch

## 🔒 Branch Protection

**Important**: Direct pushes to the `main` branch are **disabled**. All changes must go through Pull Requests.

### Why Pull Requests?

- **Code Review**: Ensures quality and catches issues early
- **Discussion**: Allows team collaboration on changes
- **Testing**: CI/CD can run automated tests before merging
- **Documentation**: Creates a clear history of what changed and why

## 🌳 Branch Strategy

### Branch Naming Convention

Use descriptive branch names that indicate the type and purpose of your changes:

```
feature/<feature-name>     # New features
fix/<bug-description>      # Bug fixes
docs/<what-is-documented>  # Documentation updates
refactor/<what-changes>    # Code refactoring
chore/<task-description>   # Maintenance tasks
```

**Examples:**

- `feature/twitch-clip-commands`
- `fix/xp-cooldown-bypass`
- `docs/rag-usage-examples`
- `refactor/persona-loading`
- `chore/update-dependencies`

## 📝 Pull Request Process

### 1. Before You Start

- Check existing [Issues](https://github.com/your-org/abby/issues) to avoid duplicate work
- Comment on an issue to let others know you're working on it
- For major changes, open an issue first to discuss the approach

### 2. Making Changes

```bash
# Create and checkout your branch
git checkout -b feature/your-feature-name

# Make your changes
# ... edit files ...

# Stage and commit with clear messages
git add .
git commit -m "feat: add twitch clip command with caching"

# Push to your fork
git push origin feature/your-feature-name
```

### 3. Commit Message Format

We follow **Conventional Commits** for clear, structured commit history:

```
<type>(<scope>): <subject>

<body (optional)>

<footer (optional)>
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style/formatting (no logic change)
- `refactor`: Code restructuring (no feature change)
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (deps, configs)

**Examples:**

```bash
feat(chatbot): add RAG context to conversations
fix(xp): prevent cooldown bypass with multiple messages
docs(api): document ImageGenerator quota system
refactor(database): consolidate MongoDB connection logic
chore(deps): upgrade discord.py to 2.6.4
```

### 4. Opening a Pull Request

When your changes are ready:

1. **Push your branch** to your fork
2. **Open a Pull Request** on GitHub against `main`
3. **Fill out the PR template** (if provided)
4. **Link related issues** using keywords like "Fixes #123" or "Relates to #456"

**PR Title Format:**

```
<type>(<scope>): <clear description>
```

**PR Description Should Include:**

- **What** changed and **why**
- **How** to test the changes
- **Screenshots** (for UI/UX changes)
- **Breaking changes** (if any)
- **Related issues** or discussions

### 5. Code Review Process

- Maintainers will review your PR
- Address feedback by pushing new commits to your branch
- Once approved, a maintainer will merge your PR
- **Do not merge your own PRs** unless you're a designated maintainer

## 🏗️ Architecture Guidelines

Abby follows a **clean architecture** pattern separating core logic from Discord-specific code.

### Core Principles

**`abby_core/`** — Platform-agnostic business logic

- Database operations (MongoDB)
- LLM clients (OpenAI, Ollama)
- RAG system (Qdrant, Chroma)
- Economy/XP system
- Storage management
- ✅ **No Discord imports**

**`abby_adapters/discord/`** — Discord-specific implementations

- Cogs (commands)
- Event handlers
- Discord embeds, interactions
- ❌ **Minimal business logic**

### Where to Put Your Code

| You're Adding...              | Location                      |
| ----------------------------- | ----------------------------- |
| New Discord command           | `abby_adapters/discord/cogs/` |
| Database schema/query         | `abby_core/database/`         |
| LLM integration               | `abby_core/llm/`              |
| RAG document processing       | `abby_core/rag/`              |
| XP/economy logic              | `abby_core/economy/`          |
| Storage/file management       | `abby_core/storage/`          |
| Logging/telemetry             | `abby_core/observability/`    |
| Personality/response patterns | `abby_core/personality/`      |

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) for detailed examples.

## 🧪 Testing Your Changes

Before submitting a PR:

1. **Test locally** with your development environment
2. **Check logs** for errors or warnings
3. **Test edge cases** (empty inputs, rate limits, etc.)
4. **Verify database changes** don't corrupt existing data
5. **Test with different user roles** (admin, member, etc.)

### Running the Bot Locally

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Set up .env file
cp .env.example .env
# Edit .env with your test Discord token and MongoDB URI

# Run the bot
python launch.py

# Check logs
tail -f shared/logs/events.jsonl
```

## 📦 Dependencies

### Adding New Dependencies

If your changes require new packages:

1. **Add to `requirements.txt`** with version pinning
2. **Document why** it's needed in your PR description
3. **Check for conflicts** with existing dependencies
4. **Consider alternatives** that don't add bloat

```bash
# Add dependency
pip install package-name==1.2.3

# Update requirements.txt
pip freeze | grep package-name >> requirements.txt
```

## 📚 Documentation

Documentation is **just as important** as code!

### When to Update Docs

- **New feature**: Add usage guide to `docs/features/`
- **Breaking change**: Update affected docs and CHANGELOG
- **Configuration change**: Update `docs/getting-started/configuration.md`
- **New cog**: Document commands in README.md
- **API change**: Update `docs/api-reference/`

### Documentation Standards

- Use **clear, concise language**
- Include **code examples** with comments
- Add **screenshots** for visual features
- Keep **line length < 100 characters** for readability
- Use **Markdown best practices**

## 🐛 Reporting Issues

### Bug Reports

Use the **Bug Report** template and include:

- **Environment**: OS, Python version, Discord.py version
- **Steps to reproduce** the bug
- **Expected behavior** vs. **actual behavior**
- **Logs/screenshots** showing the error
- **Related code** (if you've investigated)

### Feature Requests

Use the **Feature Request** template and include:

- **Problem** you're trying to solve
- **Proposed solution** with examples
- **Alternatives** you've considered
- **Impact** on existing features

## 🎨 Code Style

### Python Guidelines

- Follow **PEP 8** style guidelines
- Use **type hints** where appropriate
- Write **docstrings** for functions and classes
- Keep functions **small and focused**
- Use **descriptive variable names**

**Example:**

```python
async def calculate_xp_gain(
    user_id: str,
    message_length: int,
    has_media: bool = False
) -> int:
    """
    Calculate XP gain for a message based on length and media attachment.

    Args:
        user_id: Discord user ID
        message_length: Length of message content
        has_media: Whether message contains media attachment

    Returns:
        XP amount to award
    """
    base_xp = min(message_length // 10, 50)
    if has_media:
        base_xp += 10
    return base_xp
```

### Import Organization

Group imports in this order:

```python
# Standard library
import os
import sys
from datetime import datetime
from pathlib import Path

# Third-party
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Local core
from abby_core.database.mongodb import get_collection
from abby_core.economy.xp import add_xp

# Local adapter
from abby_adapters.discord.config import BotConfig
```

## 🏆 Recognition

Contributors will be:

- Listed in [CONTRIBUTORS.md](CONTRIBUTORS.md)
- Mentioned in release notes for significant contributions
- Thanked in the Breeze Club Discord server

## ❓ Questions?

- **Discord**: Join the [Breeze Club Discord](https://discord.gg/yGsBGQAC49)
- **Issues**: Open a [GitHub Issue](https://github.com/your-org/abby/issues)
- **Discussions**: Use [GitHub Discussions](https://github.com/your-org/abby/discussions) for questions

---

**Thank you for contributing to Abby! 🐰**

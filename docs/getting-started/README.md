# Getting Started with Abby

This section covers everything you need to get Abby up and running in your Discord server.

## 📚 Contents

### [Installation Guide](installation.md)

Complete step-by-step installation instructions for Windows, Linux, and macOS.

**Topics covered:**

- Prerequisites and system requirements
- Python environment setup
- MongoDB installation and configuration
- Discord bot creation and token setup
- Dependency installation
- Initial bot startup

**Time to complete**: ~30 minutes

---

### [Configuration Guide](configuration.md)

Comprehensive guide to configuring Abby's features and integrations.

**Topics covered:**

- Environment variable reference
- Channel ID configuration
- API key setup (OpenAI, Stability AI, Twitch)
- Feature flags and toggles
- Database connection strings
- Quota and rate limit settings

**Time to complete**: ~20 minutes

---

### [Quick Start Tutorial](quick-start.md)

Fast-track guide to get Abby running with minimal configuration.

**Topics covered:**

- Minimum viable configuration
- First run checklist
- Testing basic commands
- Troubleshooting common startup issues

**Time to complete**: ~10 minutes

---

### [Docker Deployment](docker.md)

Deploy Abby using Docker and Docker Compose for containerized environments.

**Topics covered:**

- Dockerfile setup
- Docker Compose configuration
- Volume management for persistent data
- Environment variable configuration in Docker
- Multi-container orchestration (bot + MongoDB + Qdrant)

**Time to complete**: ~15 minutes

---

## 🎯 Recommended Path

### For First-Time Users

1. Start with **[Quick Start Tutorial](quick-start.md)** to get up and running fast
2. Read **[Installation Guide](installation.md)** for detailed setup
3. Configure features using **[Configuration Guide](configuration.md)**

### For Production Deployments

1. Read **[Installation Guide](installation.md)** thoroughly
2. Review **[Configuration Guide](configuration.md)** for all settings
3. Check **[Docker Deployment](docker.md)** or [../deployment/](../deployment/) for production setup
4. Implement monitoring and logging from **[../deployment/monitoring.md](../deployment/monitoring.md)**

### For Development

1. Follow **[Installation Guide](installation.md)** for local setup
2. Configure development environment per **[Configuration Guide](configuration.md)**
3. Review **[../contributing/development-setup.md](../contributing/development-setup.md)** for dev tools

---

## 🆘 Need Help?

- **Common Issues**: See [troubleshooting.md](troubleshooting.md)
- **Discord Support**: [Breeze Club Server](https://discord.gg/yGsBGQAC49)
- **GitHub Issues**: [Report a problem](https://github.com/your-org/abby/issues)

---

## 📖 Related Documentation

- **[Architecture Overview](../architecture/)** — Understand how Abby is built
- **[Features](../features/)** — Learn about Abby's capabilities
- **[Deployment](../deployment/)** — Production deployment guides
- **[API Reference](../api-reference/)** — Developer API documentation

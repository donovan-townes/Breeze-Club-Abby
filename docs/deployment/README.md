# Deployment Documentation

Production deployment guides and infrastructure setup.

## 📚 Contents

### Production Deployment

#### [NSSM Deployment (Windows)](DEPLOYMENT_NSSM.md)

Deploy Abby as a Windows Service using NSSM (Non-Sucking Service Manager).

**Topics covered:**

- NSSM installation and configuration
- Service creation and management
- Auto-restart policies
- Log management
- Service troubleshooting

**Best for**: Windows Server, Windows 10/11

---

#### [systemd Deployment (Linux)](systemd-deployment.md)

Deploy Abby as a systemd service on Linux servers.

**Topics covered:**

- systemd unit file creation
- Service enable and start
- Automatic restart configuration
- Journal logging integration
- Service monitoring

**Best for**: Ubuntu, Debian, CentOS, RHEL

---

#### [Docker Deployment](docker-deployment.md)

Containerized deployment with Docker and Docker Compose.

**Topics covered:**

- Multi-container setup (bot + MongoDB + Qdrant)
- Volume management for persistence
- Network configuration
- Environment variable injection
- Scaling and load balancing

**Best for**: Modern cloud environments, Kubernetes

---

#### [Cloud Deployments](cloud/)

Platform-specific deployment guides for major cloud providers.

**Platforms:**

- [AWS EC2](cloud/aws-ec2.md) — Traditional VM deployment
- [AWS ECS](cloud/aws-ecs.md) — Container orchestration
- [Azure VM](cloud/azure-vm.md) — Azure Virtual Machines
- [Google Cloud Compute Engine](cloud/gcp-compute.md) — GCP VMs
- [DigitalOcean Droplets](cloud/digitalocean.md) — Simple VPS
- [Linode](cloud/linode.md) — Alternative VPS provider

---

### Configuration Management

#### [Environment Variables](environment-variables.md)

Complete reference for all environment variables in production.

**Categories:**

- Core settings (tokens, database URIs)
- Feature flags
- Performance tuning
- Security settings
- Integration credentials

---

#### [Secrets Management](secrets-management.md)

Best practices for managing sensitive credentials.

**Topics covered:**

- `.env` file security
- Cloud secret managers (AWS Secrets Manager, Azure Key Vault)
- Environment variable encryption
- Rotation policies
- Access control

---

### Infrastructure

#### [MongoDB Setup](mongodb-setup.md)

Production MongoDB configuration and optimization.

**Topics covered:**

- Replica set configuration
- Indexing strategies
- Backup and restore procedures
- Connection pooling
- Performance tuning

---

#### [Qdrant Setup](qdrant-setup.md)

Vector database deployment for RAG system.

**Topics covered:**

- Standalone deployment
- Docker deployment
- Data persistence
- Index optimization
- Backup strategies

---

#### [Ollama Setup](ollama-setup.md)

Local LLM inference server configuration (optional).

**Topics covered:**

- Ollama installation
- Model management
- GPU acceleration
- Memory optimization
- Endpoint configuration

---

### Monitoring & Maintenance

#### [Monitoring](monitoring.md)

Health checks, metrics, and alerting.

**Topics covered:**

- TDOS heartbeat monitoring
- Log aggregation (CloudWatch, ELK, Loki)
- Metrics collection (Prometheus)
- Uptime monitoring
- Alert configuration

---

#### [Backup & Recovery](backup-recovery.md)

Data backup strategies and disaster recovery.

**Topics covered:**

- MongoDB backup automation
- User file backups
- Configuration backups
- Restore procedures
- Disaster recovery planning

---

#### [Maintenance Tasks](maintenance.md)

Routine maintenance procedures and schedules.

**Topics covered:**

- Log rotation
- Database cleanup
- Storage cleanup (old files)
- Dependency updates
- Security patching

---

### Scaling

#### [Horizontal Scaling](horizontal-scaling.md)

Scale Abby across multiple instances (future).

**Topics covered:**

- Sharding strategies
- Load balancing
- Session affinity
- Database replication
- Cache strategies (Redis)

---

### Migration

#### [Migration from Legacy](migration-legacy.md)

Migrate from older Abby versions to current architecture.

**Topics covered:**

- Database schema migration
- File storage migration
- Configuration conversion
- Data integrity checks
- Rollback procedures

---

#### [Chroma to Qdrant Migration](MODERATION_AND_QDRANT.md)

Migrate vector database from ChromaDB to Qdrant.

**Topics covered:**

- Migration script usage
- Data verification
- Downtime minimization
- Performance comparison

---

## 🎯 Deployment Checklist

### Pre-Deployment

- [ ] Review [environment variables](environment-variables.md)
- [ ] Set up [MongoDB](mongodb-setup.md) with replica sets
- [ ] Configure [Qdrant](qdrant-setup.md) for RAG
- [ ] Obtain all API keys and tokens
- [ ] Set up [secrets management](secrets-management.md)
- [ ] Configure [monitoring](monitoring.md) and alerting
- [ ] Set up [backup](backup-recovery.md) automation

### Deployment

- [ ] Choose deployment method (NSSM, systemd, Docker)
- [ ] Follow platform-specific guide
- [ ] Verify all services start correctly
- [ ] Test basic commands (`/ping`, `/info`)
- [ ] Check logs for errors
- [ ] Verify database connections
- [ ] Test API integrations (OpenAI, Stability AI)

### Post-Deployment

- [ ] Monitor initial performance
- [ ] Set up log rotation
- [ ] Configure automatic updates
- [ ] Document any custom configurations
- [ ] Share deployment details with team

---

## 🚀 Quick Reference

| Deployment Type     | Best For         | Guide                                 |
| ------------------- | ---------------- | ------------------------------------- |
| **Windows Service** | Windows Server   | [NSSM](DEPLOYMENT_NSSM.md)            |
| **Linux Service**   | Ubuntu/Debian    | [systemd](systemd-deployment.md)      |
| **Docker**          | Modern infra     | [Docker](docker-deployment.md)        |
| **AWS**             | Enterprise cloud | [AWS guides](cloud/)                  |
| **Simple VPS**      | Small/medium     | [DigitalOcean](cloud/digitalocean.md) |

---

## 📊 Performance Recommendations

### Minimum Requirements

- **CPU**: 2 cores
- **RAM**: 4 GB
- **Storage**: 20 GB SSD
- **Network**: 10 Mbps

### Recommended (Production)

- **CPU**: 4+ cores
- **RAM**: 8 GB+
- **Storage**: 100 GB SSD
- **Network**: 100 Mbps
- **MongoDB**: Separate server or managed service
- **Qdrant**: Separate server (optional)

### High-Performance (Large Communities)

- **CPU**: 8+ cores
- **RAM**: 16 GB+
- **Storage**: 500 GB SSD
- **Network**: 1 Gbps
- **MongoDB**: Replica set (3+ nodes)
- **Qdrant**: Dedicated cluster
- **Load Balancer**: Multiple bot instances

---

## 📖 Related Documentation

- **[Getting Started](../getting-started/)** — Development setup
- **[Architecture](../architecture/)** — System design
- **[Monitoring](monitoring.md)** — Production monitoring
- **[Backup & Recovery](backup-recovery.md)** — Data protection

---

**Last Updated**: January 2026  
**Deployment Guide Version**: 2.0.0

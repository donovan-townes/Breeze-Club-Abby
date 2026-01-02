# Deployment Scripts

Automated deployment scripts for Abby Discord Bot to production TSERVER.

## Quick Start

```powershell
# From project root
.\scripts\deploy\deploy.ps1

# Or from anywhere
C:\Abby_Discord_Latest\scripts\deploy\deploy.ps1
```

## Usage

### Basic Deployment

```powershell
# Deploy everything (default)
.\scripts\deploy\deploy.ps1

# Deploy specific component
.\scripts\deploy\deploy.ps1 -Target cogs
.\scripts\deploy\deploy.ps1 -Target core
.\scripts\deploy\deploy.ps1 -Target adapters
```

### Available Targets

| Target     | Description               | What Gets Deployed                                    |
| ---------- | ------------------------- | ----------------------------------------------------- |
| `all`      | Full deployment (default) | abby_core, abby_adapters, launch.py, requirements.txt |
| `core`     | Core modules only         | abby_core/                                            |
| `adapters` | All adapters              | abby_adapters/                                        |
| `cogs`     | Discord cogs only         | abby_adapters/discord/cogs/                           |
| `handlers` | Discord handlers only     | abby_adapters/discord/handlers/                       |
| `commands` | Discord commands only     | abby_adapters/discord/commands/                       |
| `config`   | Config and main files     | config.py, main.py                                    |
| `launch`   | Launch script only        | launch.py                                             |
| `scripts`  | Utility scripts           | scripts/                                              |

### Advanced Options

```powershell
# Dry run (preview what would be deployed)
.\scripts\deploy\deploy.ps1 -Target core -DryRun

# Deploy without restarting service (useful for rapid iteration)
.\scripts\deploy\deploy.ps1 -Target cogs -SkipRestart

# Multiple rapid updates without restart
.\scripts\deploy\deploy.ps1 -Target cogs -SkipRestart
.\scripts\deploy\deploy.ps1 -Target handlers -SkipRestart
# ... then manually restart when ready:
ssh tserver@100.108.120.82 "nssm restart AbbyBot"
```

## Common Workflows

### After LLM Client Changes

```powershell
.\scripts\deploy\deploy.ps1 -Target core
```

### After Adding New Commands

```powershell
.\scripts\deploy\deploy.ps1 -Target commands
```

### After Updating Image Generation Cog

```powershell
.\scripts\deploy\deploy.ps1 -Target cogs
```

### After Config Changes

```powershell
.\scripts\deploy\deploy.ps1 -Target config
```

### Testing Multiple Changes Without Restarts

```powershell
.\scripts\deploy\deploy.ps1 -Target cogs -SkipRestart
.\scripts\deploy\deploy.ps1 -Target handlers -SkipRestart
ssh tserver@100.108.120.82 "nssm restart AbbyBot"
```

## Requirements

- PowerShell 5.1+ (Windows) or PowerShell Core 7+ (cross-platform)
- SSH access to TSERVER configured
- SSH key authentication recommended (no password prompts)
- SCP available in PATH

### SSH Key Setup (Recommended)

```powershell
# Generate key (if you don't have one)
ssh-keygen -t ed25519

# Copy to TSERVER
ssh-copy-id tserver@100.108.120.82

# Test passwordless login
ssh tserver@100.108.120.82 "echo OK"
```

## Troubleshooting

### SSH Connection Issues

```powershell
# Test SSH manually
ssh tserver@100.108.120.82 "echo test"

# Check SSH config
cat ~\.ssh\config
```

### Service Won't Start

```powershell
# Check service status
ssh tserver@100.108.120.82 "nssm status AbbyBot"

# View recent logs
ssh tserver@100.108.120.82 "type C:\opt\tdos\apps\abby\logs\service_stderr.log"

# Manual start for debugging
ssh tserver@100.108.120.82
cd C:\opt\tdos\apps\abby
.venv\Scripts\activate
python launch.py
```

### Missing Files Error

```powershell
# Preview what would be deployed
.\scripts\deploy\deploy.ps1 -Target all -DryRun
```

## Script Customization

Edit `deploy.ps1` to customize:

```powershell
# Remote host
$RemoteHost = "tserver@100.108.120.82"

# Remote installation path
$RemotePath = "C:\opt\tdos\apps\abby"

# Service name
$ServiceName = "AbbyBot"
```

## CI/CD Integration

For automated deployments (e.g., GitHub Actions):

```yaml
- name: Deploy to TSERVER
  run: |
    .\scripts\deploy\deploy.ps1 -Target all
  env:
    SSH_KEY: ${{ secrets.TSERVER_SSH_KEY }}
```

## Safety Features

- Pre-flight checks validate all local files exist
- SSH connection tested before deployment
- Service stopped before file transfer
- Clear error messages for failed operations
- Dry run mode for previewing changes

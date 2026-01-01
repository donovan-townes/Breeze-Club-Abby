# Abby Bot - Deploy to TSERVER
# Usage: .\deploy-to-tserver.ps1 [options]
# Options: -full, -quick, -test

param(
    [ValidateSet('full', 'quick', 'test')]
    [string]$Mode = 'quick',
    [string]$TServerHost = 'tserver@100.108.120.82',
    [string]$RemotePath = 'C:\abby_bot'
)

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Write-Status {
    param([string]$Message, [ValidateSet('Info', 'Success', 'Warning', 'Error')]$Level = 'Info')
    $colors = @{
        'Info'    = 'Cyan'
        'Success' = 'Green'
        'Warning' = 'Yellow'
        'Error'   = 'Red'
    }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $colors[$Level]
}

Write-Host "`n╔═══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Abby Bot Deployment to TSERVER      ║" -ForegroundColor Cyan
Write-Host "║  Mode: $Mode" -ForegroundColor Cyan -NoNewline; Write-Host (' ' * (31 - $Mode.Length)) + "║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════╝" -ForegroundColor Cyan

try {
    # Test SSH connection first
    Write-Status "Testing SSH connection to $TServerHost..." "Info"
    ssh -T $TServerHost "echo SSH Connection OK" | Out-Null
    Write-Status "SSH connection successful" "Success"

    # Stop the service
    Write-Status "Stopping AbbyBot service..." "Warning"
    ssh $TServerHost "nssm stop AbbyBot" | Out-Null
    Start-Sleep -Seconds 2
    Write-Status "Service stopped" "Success"

    if ($Mode -eq 'full') {
        Write-Status "Running FULL deployment..." "Info"
        Write-Status "Syncing abby_core..." "Info"
        scp -r "abby_core" "$TServerHost`:$RemotePath\" | Out-Null
        
        Write-Status "Syncing abby_adapters..." "Info"
        scp -r "abby_adapters" "$TServerHost`:$RemotePath\" | Out-Null
        
        Write-Status "Syncing scripts..." "Info"
        scp -r "scripts" "$TServerHost`:$RemotePath\" | Out-Null
        
        Write-Status "Uploading launch.py..." "Info"
        scp "launch.py" "$TServerHost`:$RemotePath\" | Out-Null
        
        Write-Status "Uploading requirements.txt..." "Info"
        scp "requirements.txt" "$TServerHost`:$RemotePath\" | Out-Null
    }
    elseif ($Mode -eq 'quick') {
        Write-Status "Running QUICK deployment (core & adapters only)..." "Info"
        Write-Status "Syncing abby_core..." "Info"
        scp -r "abby_core" "$TServerHost`:$RemotePath\" | Out-Null
        
        Write-Status "Syncing abby_adapters..." "Info"
        scp -r "abby_adapters" "$TServerHost`:$RemotePath\" | Out-Null
    }
    elseif ($Mode -eq 'test') {
        Write-Status "TEST MODE - No files will be transferred" "Warning"
        Write-Status "Would deploy: abby_core, abby_adapters, scripts, launch.py, requirements.txt" "Info"
    }

    if ($Mode -ne 'test') {
        Write-Status "Clearing Python cache on TSERVER..." "Info"
        ssh $TServerHost "Get-ChildItem -Path '$RemotePath' -Filter '__pycache__' -Recurse -Directory | Remove-Item -Recurse -Force" | Out-Null
        Write-Status "Cache cleared" "Success"

        # Start the service
        Write-Status "Starting AbbyBot service..." "Info"
        ssh $TServerHost "nssm start AbbyBot" | Out-Null
        Start-Sleep -Seconds 3
        
        # Check status
        $status = ssh $TServerHost "nssm status AbbyBot"
        Write-Status "Service status: $status" "Success"
    }

    Write-Host "`n✅ Deployment completed successfully!`n" -ForegroundColor Green
}
catch {
    Write-Status "DEPLOYMENT FAILED: $_" "Error"
    Write-Host "`n⚠️  Service may need manual restart!" -ForegroundColor Yellow
    exit 1
}

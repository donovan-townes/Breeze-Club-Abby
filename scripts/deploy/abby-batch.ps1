# Abby Bot - Batch Operations Helper
# Quick shortcuts for common multi-step tasks
# Usage: .\abby-batch.ps1 [command]

param(
    [ValidateSet('sync-and-restart', 'update-deps', 'health-check', 'logs-email', 'backup-db')]
    [string]$Command = 'health-check',
    [string]$TServerHost = 'tserver@100.108.120.82'
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

Write-Host "`n╔════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Abby Batch Operations             ║" -ForegroundColor Cyan
Write-Host "║  Command: $Command" -ForegroundColor Cyan -NoNewline; Write-Host (' ' * (24 - $Command.Length)) + "║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════╝`n" -ForegroundColor Cyan

switch ($Command) {
    'sync-and-restart' {
        Write-Status "Running sync and restart sequence..." "Warning"
        
        Write-Status "[1/5] Testing SSH connection..." "Info"
        ssh -T $TServerHost "echo OK" | Out-Null
        
        Write-Status "[2/5] Deploying code (quick mode)..." "Info"
        & ".\scripts\deploy-to-tserver.ps1" -Mode quick
        
        Write-Status "[3/5] Waiting for service to stabilize..." "Info"
        Start-Sleep -Seconds 5
        
        Write-Status "[4/5] Checking service status..." "Info"
        $status = ssh $TServerHost "nssm status AbbyBot"
        
        Write-Status "[5/5] Retrieving recent logs..." "Info"
        ssh $TServerHost "Get-Content C:\abby_bot\logs\service_stdout.log -Tail 20" | Out-Host
        
        if ($status -eq "SERVICE_RUNNING") {
            Write-Host "`n✅ Sync and restart completed successfully!`n" -ForegroundColor Green
        } else {
            Write-Host "`n⚠️  Service status: $status`n" -ForegroundColor Yellow
        }
    }

    'health-check' {
        Write-Status "Performing health check..." "Info"
        
        Write-Host "`n📊 Health Check Results:" -ForegroundColor Cyan
        Write-Host "─" * 50
        
        Write-Status "Service Status" "Info"
        ssh $TServerHost "nssm status AbbyBot"
        
        Write-Status "Disk Space" "Info"
        ssh $TServerHost "Get-PSDrive C | Select-Object Used, Free" | Format-Table
        
        Write-Status "Process Info" "Info"
        ssh $TServerHost "Get-Process python -ErrorAction SilentlyContinue | Select-Object Name, CPU, Memory" | Format-Table
        
        Write-Status "Recent Errors (last 10 lines)" "Info"
        $errorCount = ssh $TServerHost "((Get-Content C:\abby_bot\logs\service_stderr.log | Measure-Object -Line).Lines)"
        if ($errorCount -gt 0) {
            ssh $TServerHost "Get-Content C:\abby_bot\logs\service_stderr.log -Tail 10" | Out-Host
            Write-Host "`n⚠️  $errorCount lines of errors found!" -ForegroundColor Yellow
        } else {
            Write-Host "✅ No errors detected" -ForegroundColor Green
        }
        
        Write-Host "─" * 50 -ForegroundColor Cyan
    }

    'update-deps' {
        Write-Status "Updating Python dependencies on TSERVER..." "Warning"
        
        Write-Status "Stopping service..." "Info"
        ssh $TServerHost "nssm stop AbbyBot" | Out-Null
        Start-Sleep -Seconds 2
        
        Write-Status "Uploading requirements.txt..." "Info"
        scp "requirements.txt" "$TServerHost`:C:\abby_bot\" | Out-Null
        
        Write-Status "Installing dependencies..." "Info"
        ssh $TServerHost "cd C:\abby_bot && .\.venv\Scripts\activate && pip install -r requirements.txt" | Out-Host
        
        Write-Status "Restarting service..." "Info"
        ssh $TServerHost "nssm start AbbyBot" | Out-Null
        Start-Sleep -Seconds 3
        
        Write-Status "Dependency update complete!" "Success"
    }

    'logs-email' {
        Write-Status "Collecting logs for email..." "Info"
        
        $logsDir = "$env:TEMP\abby_logs_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss')"
        New-Item -ItemType Directory -Path $logsDir | Out-Null
        
        Write-Status "Downloading log files..." "Info"
        scp "$TServerHost`:C:\abby_bot\logs\*" "$logsDir\" | Out-Null
        
        Write-Status "Creating summary file..." "Info"
        $summary = @"
=== ABBY BOT LOG SUMMARY ===
Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

=== SERVICE STATUS ===
$(ssh $TServerHost "nssm status AbbyBot")

=== RECENT ERRORS (Last 50 lines) ===
$(ssh $TServerHost "Get-Content C:\abby_bot\logs\service_stderr.log -Tail 50")

=== RECENT ACTIVITY (Last 50 lines) ===
$(ssh $TServerHost "Get-Content C:\abby_bot\logs\service_stdout.log -Tail 50")
"@
        
        $summary | Out-File "$logsDir\SUMMARY.txt" -Encoding UTF8
        
        Write-Status "Logs ready for email at: $logsDir" "Success"
        Write-Host "📧 Open this folder and attach to your email:`n   $logsDir`n" -ForegroundColor Cyan
        
        # Optionally open in Explorer
        Invoke-Item $logsDir
    }

    'backup-db' {
        Write-Status "Backing up MongoDB database..." "Warning"
        
        $backupDir = "$env:TEMP\abby_backup_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss')"
        
        Write-Status "Running mongodump on TSERVER..." "Info"
        ssh $TServerHost "mongodump --out $backupDir" | Out-Host
        
        Write-Status "Downloading backup to local machine..." "Info"
        scp -r "$TServerHost`:$backupDir" ".\backups\" | Out-Null
        
        Write-Status "Backup complete!" "Success"
        Write-Host "💾 Backup stored at: .\backups\$(Split-Path $backupDir -Leaf)`n" -ForegroundColor Cyan
    }
}

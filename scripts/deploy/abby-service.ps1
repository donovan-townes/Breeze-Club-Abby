# Abby Bot - Remote Service Management (run this on TSERVER via SSH)
# Usage: .\abby-service.ps1 [action]
# Actions: status, restart, stop, start, logs, logs-tail, clear-logs, debug, deploy-local

param(
    [ValidateSet('status', 'restart', 'stop', 'start', 'logs', 'logs-tail', 'clear-logs', 'debug', 'deploy-local')]
    [string]$Action = 'status',
    [int]$TailLines = 50
)

$ErrorActionPreference = "Continue"
$BotPath = 'C:\opt\tdos\apps\abby'
$LogDir = Join-Path $BotPath 'logs'
$StdoutLog = Join-Path $LogDir 'service_stdout.log'
$StderrLog = Join-Path $LogDir 'service_stderr.log'
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
Write-Host "║  Abby Bot Service Manager          ║" -ForegroundColor Cyan
Write-Host "║  Action: $Action" -ForegroundColor Cyan -NoNewline; Write-Host (' ' * (28 - $Action.Length)) + "║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════╝" -ForegroundColor Cyan

# Ensure logs directory exists
if (!(Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

switch ($Action) {
    'status' {
        Write-Status "Checking service status..." "Info"
        $status = nssm status AbbyBot
        Write-Host "Status: $status" -ForegroundColor Green
        Write-Host ""
        Write-Status "Recent activity:" "Info"
        Get-Content -Path $StdoutLog -Tail 10
    }

    'restart' {
        Write-Status "Restarting AbbyBot service..." "Warning"
        nssm restart AbbyBot
        Start-Sleep -Seconds 3
        $status = nssm status AbbyBot
        Write-Status "Service restarted. Status: $status" "Success"
    }

    'stop' {
        Write-Status "Stopping AbbyBot service..." "Warning"
        nssm stop AbbyBot
        Start-Sleep -Seconds 2
        Write-Status "Service stopped" "Success"
    }

    'start' {
        Write-Status "Starting AbbyBot service..." "Info"
        nssm start AbbyBot
        Start-Sleep -Seconds 3
        $status = nssm status AbbyBot
        Write-Status "Service started. Status: $status" "Success"
    }

    'logs' {
        Write-Status "Last $TailLines lines of STDOUT:" "Info"
        Write-Host "─" * 80 -ForegroundColor Gray
        Get-Content -Path $StdoutLog -Tail $TailLines
        Write-Host "─" * 80 -ForegroundColor Gray
        
        if ((Get-Item $StderrLog).Length -gt 0) {
            Write-Status "Last $TailLines lines of STDERR:" "Warning"
            Write-Host "─" * 80 -ForegroundColor Gray
            Get-Content -Path $StderrLog -Tail $TailLines
            Write-Host "─" * 80 -ForegroundColor Gray
        }
    }

    'logs-tail' {
        Write-Status "Following logs (Ctrl+C to exit)..." "Info"
        Get-Content -Path $StdoutLog -Tail 20 -Wait
    }

    'clear-logs' {
        Write-Status "Clearing log files..." "Warning"
        Clear-Content -Path $StdoutLog
        Clear-Content -Path $StderrLog
        Write-Status "Logs cleared" "Success"
    }

    'debug' {
        Write-Status "Stopping service and launching manual debug mode..." "Warning"
        nssm stop AbbyBot
        Start-Sleep -Seconds 2
        
        Write-Status "Activating venv and launching Python..." "Info"
        Push-Location $BotPath
        & ".\.venv\Scripts\activate.ps1"
        python launch.py
        Pop-Location
    }

    'deploy-local' {
        Write-Status "Opening file explorer to $BotPath for local editing..." "Info"
        Invoke-Item $BotPath
    }
}

Write-Host ""

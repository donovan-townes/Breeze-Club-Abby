# Local Development Docker Compose Helper
# Simplifies common dev tasks

param(
    [ValidateSet('up', 'down', 'logs', 'build', 'clean', 'status', 'shell', 'db')]
    [string]$Command = 'status',
    
    [string]$Service = 'abby'
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DevStateDir = Join-Path $ScriptDir "dev-state"
$ComposeFile = Join-Path $ScriptDir "docker-compose.dev.yml"

function Initialize-DevState {
    Write-Host "[+] Initializing dev-state directories..." -ForegroundColor Cyan
    $dirs = @(
        "$DevStateDir/mongo/data",
        "$DevStateDir/mongo/configdb",
        "$DevStateDir/abby/storage",
        "$DevStateDir/abby/logs",
        "$DevStateDir/abby/chroma",
        "$DevStateDir/abby/events"
    )
    
    foreach ($dir in $dirs) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Host "[OK] Created $dir" -ForegroundColor Green
        }
    }
}

function Start-DevEnvironment {
    Write-Host "[+] Starting local development environment..." -ForegroundColor Cyan
    Initialize-DevState
    
    Write-Host "[+] Building and starting containers..." -ForegroundColor Cyan
    docker compose -f $ComposeFile up --build
}

function Stop-DevEnvironment {
    Write-Host "[+] Stopping containers..." -ForegroundColor Cyan
    docker compose -f $ComposeFile down
    Write-Host "[OK] All containers stopped" -ForegroundColor Green
    Write-Host "[i] Data persists in $DevStateDir/" -ForegroundColor Blue
}

function Show-Logs {
    $follow = if ($Service) { "-f" } else { "" }
    
    if ($Service -eq 'all') {
        Write-Host "[+] Showing logs for all services..." -ForegroundColor Cyan
        docker compose -f $ComposeFile logs $follow
    }
    else {
        Write-Host "[+] Showing logs for $Service..." -ForegroundColor Cyan
        docker compose -f $ComposeFile logs $follow $Service
    }
}

function Build-Image {
    Write-Host "[+] Building Abby image locally..." -ForegroundColor Cyan
    docker compose -f $ComposeFile build --no-cache
    Write-Host "[OK] Build complete" -ForegroundColor Green
}

function Clean-DevState {
    Write-Host "[!] This will DELETE all local dev data!" -ForegroundColor Yellow
    $confirm = Read-Host "Type 'DELETE' to confirm"
    
    if ($confirm -eq 'DELETE') {
        Write-Host "[+] Removing dev-state directory..." -ForegroundColor Cyan
        Remove-Item -Recurse -Force $DevStateDir
        Write-Host "[OK] Dev state cleaned" -ForegroundColor Green
        Write-Host "[+] Next 'up' command will start fresh" -ForegroundColor Blue
    }
    else {
        Write-Host "[x] Cancelled" -ForegroundColor Red
    }
}

function Show-Status {
    Write-Host "[+] Local Environment Status" -ForegroundColor Cyan
    Write-Host "----------------------------" -ForegroundColor Cyan
    docker compose -f $ComposeFile ps
    
    Write-Host ""
    Write-Host "[+] Data Directory Status:" -ForegroundColor Cyan
    if (Test-Path $DevStateDir) {
        $size = (Get-ChildItem -Recurse $DevStateDir -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $sizeGB = [math]::Round($size / 1GB, 2)
        Write-Host "  Total: $sizeGB GB" -ForegroundColor White
    }
    else {
        Write-Host "  No dev state yet (run 'dev-compose-helper.ps1 up' first)" -ForegroundColor Yellow
    }
}

function Connect-Shell {
    Write-Host "[+] Opening shell in $Service container..." -ForegroundColor Cyan
    docker compose -f $ComposeFile exec $Service bash
}

function Access-Database {
    Write-Host "[+] Opening MongoDB shell..." -ForegroundColor Cyan
    docker compose -f $ComposeFile exec mongo mongosh localhost:27017/abby
}

# Main execution
switch ($Command) {
    'up' {
        Start-DevEnvironment
    }
    'down' {
        Stop-DevEnvironment
    }
    'logs' {
        Show-Logs
    }
    'build' {
        Build-Image
    }
    'clean' {
        Clean-DevState
    }
    'status' {
        Show-Status
    }
    'shell' {
        Connect-Shell
    }
    'db' {
        Access-Database
    }
    default {
        Write-Host "Usage: .\dev-compose-helper.ps1 <command> [options]" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Commands:" -ForegroundColor Green
        Write-Host "  up      - Start local dev environment (builds if needed)" -ForegroundColor White
        Write-Host "  down    - Stop all containers (preserves data)" -ForegroundColor White
        Write-Host "  logs    - View container logs (follow with -Service)" -ForegroundColor White
        Write-Host "  build   - Rebuild Docker image locally" -ForegroundColor White
        Write-Host "  clean   - DELETE all dev data (requires confirmation)" -ForegroundColor Yellow
        Write-Host "  status  - Show container status and data size" -ForegroundColor White
        Write-Host "  shell   - Open bash shell in container" -ForegroundColor White
        Write-Host "  db      - Open MongoDB shell" -ForegroundColor White
        Write-Host ""
        Write-Host "Examples:" -ForegroundColor Green
        Write-Host "  .\dev-compose-helper.ps1 up" -ForegroundColor Gray
        Write-Host "  .\dev-compose-helper.ps1 logs -Service abby" -ForegroundColor Gray
        Write-Host "  .\dev-compose-helper.ps1 db" -ForegroundColor Gray
        Write-Host "  .\dev-compose-helper.ps1 clean" -ForegroundColor Gray
    }
}


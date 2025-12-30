# restart_dev.ps1
# PowerShell script to auto-restart Abby on shutdown (for development)

$ErrorActionPreference = "Continue"

Write-Host "🐰 Abby Development Auto-Restart" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the restart loop" -ForegroundColor Yellow
Write-Host ""

while ($true) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Starting Abby..." -ForegroundColor Green
    
    # Run the bot
    python launch.py
    
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0) {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Abby exited gracefully (code: $exitCode)" -ForegroundColor Yellow
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Restarting in 2 seconds..." -ForegroundColor Cyan
        Start-Sleep -Seconds 2
    } else {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Abby crashed (code: $exitCode)" -ForegroundColor Red
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Restarting in 5 seconds..." -ForegroundColor Cyan
        Start-Sleep -Seconds 5
    }
}

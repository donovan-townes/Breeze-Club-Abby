# Abby MongoDB SSH tunnel helper
# Keeps a local tunnel open to TSERVER's MongoDB for Compass.
# Usage: run this script in a PowerShell window and leave it open while devving.

$User = "townes"
$HostName = "tserver"
$LocalPort = 27018
$RemoteHost = "127.0.0.1"
$RemotePort = 27017

$sshArgs = @(
    "-N",
    "-L", "$LocalPort`:$RemoteHost`:$RemotePort",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=3",
    "-o", "ExitOnForwardFailure=yes",
    "${User}@${HostName}"
)

Write-Host "Starting MongoDB tunnel: localhost:${LocalPort} -> ${HostName}:${RemotePort}" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray

while ($true) {
    & ssh @sshArgs
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host "Tunnel closed cleanly." -ForegroundColor Yellow
        break
    }

    Write-Host "Tunnel dropped (exit code $exitCode). Reconnecting in 3s..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
}

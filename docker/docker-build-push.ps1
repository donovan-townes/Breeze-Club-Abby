param(
    [string]$Tag = "latest",
    [string]$RegistryHost = "registry.tdos.internal",
    [switch]$DryRun,
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[OK] $args" -ForegroundColor Green }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }
function Write-Warning { Write-Host "[WARN] $args" -ForegroundColor Yellow }

function Test-DockerEngine {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker CLI not found"
        exit 1
    }
    docker info | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker engine not running"
        exit 1
    }
}

function Test-RegistryReachable {
    # Try direct internal registry IP first (best for Docker)
    try {
        Invoke-RestMethod -Uri "http://100.86.240.84:5000/v2/" -TimeoutSec 5 | Out-Null
        Write-Info "Using direct registry connection: 100.86.240.84:5000"
        return $true
    } catch {
        Write-Warning "Direct connection failed, trying via hostname..."
    }
    
    # Fallback: try hostname (goes through Caddy with HTTPS)
    try {
        Invoke-RestMethod -Uri "https://$RegistryHost/v2/" -SkipCertificateCheck -TimeoutSec 5 | Out-Null
        Write-Info "Using hostname registry connection: $RegistryHost"
        return $true
    } catch {
        Write-Error "Registry not reachable at http://$RegistryHost:5000 or https://$RegistryHost"
        Write-Error "Make sure TSERVER registry is running: docker compose ps (on TSERVER)"
        return $false
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  ABBY DOCKER BUILD & PUSH" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

$ImageName = "abby"
$LocalTag = "$ImageName`:$Tag"
# For Docker push/pull, use direct registry IP:port (avoids Caddy redirect)
$RegistryPushTag = "100.86.240.84:5000/$ImageName`:$Tag"

# Build context is the parent directory (where Dockerfile and source code are)
$BuildContext = Split-Path $PSScriptRoot -Parent
$DockerfilePath = Join-Path $BuildContext "Dockerfile"

Write-Info "Local image:    $LocalTag"
Write-Info "Registry image: $RegistryPushTag (direct IP for docker push)"
Write-Info "Registry host:  $RegistryHost"
Write-Info "Build context:  $BuildContext"

Write-Host ""
Write-Info "Checking Docker engine..."
Test-DockerEngine
Write-Success "Docker OK"

Write-Info "Checking registry access..."
if (-not (Test-RegistryReachable)) {
    exit 1
}
Write-Success "Registry OK"

if ($DryRun) {
    Write-Warning "DRY RUN MODE"
}
if ($NoPush) {
    Write-Warning "SKIP PUSH MODE"
}

Write-Host ""
Write-Info "Building image..."
# Use absolute paths to ensure Docker finds the Dockerfile regardless of current working directory
$buildCmd = "docker build -t $LocalTag -t $RegistryPushTag -f `"$DockerfilePath`" `"$BuildContext`""

if ($DryRun) {
    Write-Host "Would run: $buildCmd"
} else {
    Invoke-Expression $buildCmd
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Build failed"
        exit 1
    }
    Write-Success "Build complete"
}

Write-Host ""
Write-Info "Verifying image..."
$verifyCmd = "docker inspect $LocalTag"

if ($DryRun) {
    Write-Host "Would run: $verifyCmd"
} else {
    Invoke-Expression $verifyCmd | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Verification failed"
        exit 1
    }
    Write-Success "Image verified"
}

Write-Host ""

if (-not $NoPush) {
    Write-Info "Pushing to registry..."
    $pushCmd = "docker push $RegistryPushTag"
    
    if ($DryRun) {
        Write-Host "Would run: $pushCmd"
    } else {
        Invoke-Expression $pushCmd
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Push failed"
            Write-Host "Check: docker compose ps (on TSERVER)"
            exit 1
        }
        Write-Success "Push complete"
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BUILD & PUSH COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

if (-not $NoPush -and -not $DryRun) {
    Write-Info "Next steps on TSERVER:"
    Write-Host "  cd /srv/tserver/compose"
    Write-Host "  docker compose pull abby"
    Write-Host "  docker compose up -d abby"
    Write-Host "  docker compose logs -f abby"
}

Write-Host ""

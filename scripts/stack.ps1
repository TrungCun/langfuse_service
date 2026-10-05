param(
    [ValidateSet('validate', 'start', 'status', 'stop', 'logs')]
    [string]$Action = 'status',
    [string]$DockerPath = $env:DOCKER_CLI_PATH
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $DockerPath) {
    $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    if ($dockerCommand) { $DockerPath = $dockerCommand.Source }
}
if (-not $DockerPath) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
        "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe",
        "$env:USERPROFILE\.docker\bin\docker.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -ErrorAction SilentlyContinue) {
            $DockerPath = $candidate
            break
        }
    }
}
if (-not $DockerPath) {
    throw 'Docker CLI is inaccessible in this shell. Use -DockerPath with the actual docker.exe path, or run from a terminal that can access Docker Desktop.'
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot '.env'))) {
    throw 'Missing .env. Run python scripts/init_env.py first.'
}
Push-Location $repoRoot
try {
    & $DockerPath compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Invalid Compose configuration.' }
    if ($Action -eq 'validate') { Write-Output 'Compose configuration is valid.'; return }
    & $DockerPath info --format '{{.OSType}}'
    if ($LASTEXITCODE -ne 0) { throw 'Cannot connect to Docker Engine.' }
    switch ($Action) {
        start { & $DockerPath compose up -d --wait --wait-timeout 600 }
        status { & $DockerPath compose ps -a }
        stop { & $DockerPath compose down }
        logs { & $DockerPath compose logs --tail 100 langfuse-web langfuse-worker }
    }
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose action failed: $Action" }
} finally {
    Pop-Location
}


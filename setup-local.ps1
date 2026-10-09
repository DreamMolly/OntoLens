param(
    [switch]$Refresh,
    [switch]$InstallJev
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$venvPath = Join-Path $projectRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts/python.exe"
$runtimePath = Join-Path $projectRoot ".runtime"
$pipCachePath = Join-Path $runtimePath "pip-cache"
$tempPath = Join-Path $runtimePath "tmp"
$envPath = Join-Path $projectRoot ".env"
$envExamplePath = Join-Path $projectRoot ".env.example"

function Invoke-CheckedPython {
    param([string[]]$Arguments)
    & $pythonPath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

New-Item -ItemType Directory -Force -Path $runtimePath,$pipCachePath,$tempPath | Out-Null

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host "Creating project virtual environment: $venvPath"
    & (Get-Command python).Source -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the project virtual environment."
    }
}

$env:PIP_CACHE_DIR = $pipCachePath
$env:TEMP = $tempPath
$env:TMP = $tempPath

Push-Location $projectRoot
try {
    if ($Refresh) {
        Invoke-CheckedPython -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip')
    }
    Invoke-CheckedPython -Arguments @('-m', 'pip', 'install', '-e', '.[workbench,test]')
    if ($InstallJev) {
        Invoke-CheckedPython -Arguments @('-m', 'pip', 'install', '-e', '.[jev]')
    }
    if (-not (Test-Path -LiteralPath $envPath)) {
        Copy-Item -LiteralPath $envExamplePath -Destination $envPath
        Write-Host "Created project .env; fill API keys there only when needed."
    }
    Invoke-CheckedPython -Arguments @('-m', 'pip', 'check')
    Write-Host "Python: $(& $pythonPath --version)"
    Write-Host "Environment: $venvPath"
    Write-Host "Pip cache: $pipCachePath"
    Write-Host "Runtime: $runtimePath"
    Write-Host "Done. Start with .\start-workbench.ps1"
}
finally {
    Pop-Location
}

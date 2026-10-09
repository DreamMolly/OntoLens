param(
    [int]$Port = 8765,
    [string]$BindHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv/Scripts/python.exe"
$runtimePath = Join-Path $projectRoot ".runtime"
$envPath = Join-Path $projectRoot ".env"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error '请先运行 .\setup-local.ps1'
    exit 1
}
$env:TEMP = Join-Path $runtimePath "tmp"
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $runtimePath "pip-cache"
$env:PEIWU_ROOT = $projectRoot
$env:PEIWU_DB = Join-Path $runtimePath "workbench.sqlite3"
if (Test-Path -LiteralPath $envPath) {
    Get-Content -LiteralPath $envPath -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)\s*$') {
            if ([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($matches[1], 'Process'))) {
                [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
            }
        }
    }
}
if ($BindHost -notin @("127.0.0.1", "localhost", "::1") -and [string]::IsNullOrWhiteSpace($env:PEIWU_MCP_TOKEN)) {
    throw "PEIWU_MCP_TOKEN is required when binding beyond loopback"
}
Push-Location $projectRoot
try {
    & $pythonPath -m uvicorn peiwu.web:create_app --factory --host $BindHost --port $Port
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

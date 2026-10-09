param(
    [int]$Port = 8765,
    [string]$BindHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv/Scripts/python.exe"
$runtimePath = Join-Path $projectRoot ".runtime"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error '请先运行 .\setup-local.ps1'
    exit 1
}
$env:TEMP = Join-Path $runtimePath "tmp"
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $runtimePath "pip-cache"
$env:ONTOLENS_ROOT = $projectRoot
$launchCode = @'
from pathlib import Path
import sys
from ontolens.config import env_value, load_environment
import uvicorn
load_environment(Path('.env'))
host, port = sys.argv[1], int(sys.argv[2])
if host not in {'127.0.0.1', 'localhost', '::1'} and not env_value('MCP_TOKEN', '').strip():
    raise SystemExit('ONTOLENS_MCP_TOKEN is required when binding beyond loopback')
uvicorn.run('ontolens.web:create_app', factory=True, host=host, port=port, proxy_headers=False)
'@
Push-Location $projectRoot
try {
    & $pythonPath -c $launchCode $BindHost $Port
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

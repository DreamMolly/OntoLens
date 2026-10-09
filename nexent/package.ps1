param([string]$Output = "artifacts/peiwu-nexent-agent.zip")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $root ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) { throw "Run setup-local.ps1 first" }
& $pythonPath (Join-Path $root "scripts/build_nexent_package.py") --output $Output
exit $LASTEXITCODE

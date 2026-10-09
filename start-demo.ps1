param(
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Project Python is missing. Run .\setup-local.ps1 first.'
}
$arguments = @((Join-Path $PSScriptRoot 'scripts/start_demo.py'))
if (-not $CheckOnly) { $arguments += '--apply' }
Push-Location $PSScriptRoot
try {
    & $pythonPath @arguments
    $result = $LASTEXITCODE
}
finally {
    Pop-Location
}
exit $result

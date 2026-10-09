param(
    [int]$Port = 8768,
    [string]$BindHost = "127.0.0.1",
    [string]$NexentUrl = "",
    [switch]$Bootstrap,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run setup-local.ps1 first.' }
$arguments = @((Join-Path $PSScriptRoot 'scripts/run_operational.py'), '--host', $BindHost, '--port', "$Port")
if ($Bootstrap) { $arguments += '--bootstrap' }
if ($CheckOnly) { $arguments += '--check-only' }
if ($NexentUrl) { $arguments += @('--nexent-url', $NexentUrl) }
Push-Location $PSScriptRoot
try { & $pythonPath @arguments; $result = $LASTEXITCODE }
finally { Pop-Location }
exit $result

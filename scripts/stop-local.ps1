$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $taskRoot '.runtime\server.json'
if (-not (Test-Path -LiteralPath $statePath)) { throw 'Нет записи о запущенном локальном сервере.' }
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
$process = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
if (-not $process) { Write-Output 'Локальный сервер уже остановлен.'; exit 0 }
$recordedStart = if ($state.startedAt -is [DateTime]) { [DateTimeOffset]$state.startedAt } else { [DateTimeOffset]::Parse([string]$state.startedAt, [Globalization.CultureInfo]::InvariantCulture) }
if ($process.Path -ne $state.executable -or $process.StartTime.ToUniversalTime().Ticks -ne $recordedStart.UtcTicks) { throw 'PID принадлежит другому процессу. Остановка отменена.' }
# Only this verified launcher and its direct uvicorn child are stopped.
$children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($process.Id)"
foreach ($child in $children) {
  if ($child.CommandLine -like '*uvicorn*backend.main:app*') { Stop-Process -Id $child.ProcessId }
}
Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
Write-Output 'Локальный сервер остановлен.'

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $taskRoot '.venv\Scripts\python.exe'
$runtimeDir = Join-Path $taskRoot '.runtime'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Создайте .venv по README.md.' }
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot 'frontend\dist\index.html'))) { throw 'Выполните npm run build.' }
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { throw 'Порт 8000 уже занят. Проверьте запущенный экземпляр.' }
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
# Node's built-in env loader reads .env before starting the same server runner.
$nodePath = (Get-Command node.exe).Source
$launcher = Join-Path $taskRoot 'scripts\dev.mjs'
$process = Start-Process -FilePath $nodePath -ArgumentList @(('"' + $launcher + '"'), '--production') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'server.stdout.log') -RedirectStandardError (Join-Path $runtimeDir 'server.stderr.log')
@{ pid = $process.Id; startedAt = $process.StartTime.ToUniversalTime().ToString('o'); executable = $nodePath } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDir 'server.json') -Encoding utf8
Write-Output 'ЧужоеМесто запускается: http://127.0.0.1:8000'
Write-Output 'Остановка: scripts/stop-local.ps1'

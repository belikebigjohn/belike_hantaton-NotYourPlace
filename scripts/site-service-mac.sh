#!/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$project_dir"

label='pro.netcraze.chuzhoe-mesto.test'
domain="gui/$(id -u)"
target="$domain/$label"
plist="$HOME/Library/LaunchAgents/$label.plist"
action="${1:-status}"

running() { launchctl print "$target" >/dev/null 2>&1; }

check_ports() {
  for port in 8000 8766; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "Порт $port уже занят. Остановите прежний ручной запуск проекта через Ctrl+C; второй экземпляр не создаю." >&2
      lsof -nP -iTCP:"$port" -sTCP:LISTEN >&2
      exit 1
    fi
  done
}

case "$action" in
  install)
    if running; then
      echo 'Служба уже работает. После обновления кода используйте: bash scripts/site-service-mac.sh restart'
      exit 0
    fi
    check_ports
    if ! command -v python3.14 >/dev/null 2>&1; then
      echo 'Для прокси и создания службы нужен python3.14.' >&2
      exit 1
    fi
    if [ ! -x .venv-cv/bin/python ] && [ ! -x .venv/bin/python ]; then
      echo 'Нет Python-окружения проекта (.venv-cv или .venv).' >&2
      exit 1
    fi
    if [ ! -x "$HOME/tools/node-v22.23.5-darwin-x64/bin/node" ]; then
      echo 'Node.js проекта не найден в ~/tools/node-v22.23.5-darwin-x64/bin.' >&2
      exit 1
    fi
    if [ ! -f frontend/dist/index.html ]; then
      echo 'Сначала выполните npm run build.' >&2
      exit 1
    fi
    mkdir -p "$HOME/Library/LaunchAgents" runtime-data/logs
    chmod 700 runtime-data/logs
    python3.14 scripts/render-mac-launchagent.py --project "$project_dir" --home "$HOME" --output "$plist"
    chmod 644 "$plist"
    plutil -lint "$plist"
    launchctl enable "$target"
    launchctl bootstrap "$domain" "$plist"
    echo 'Служба установлена. Terminal можно закрыть; проверка: bash scripts/site-service-mac.sh status'
    ;;
  start)
    if running; then echo 'Служба уже запущена.'; exit 0; fi
    if [ ! -f "$plist" ]; then echo 'Сначала выполните: bash scripts/site-service-mac.sh install' >&2; exit 1; fi
    check_ports
    launchctl enable "$target"
    launchctl bootstrap "$domain" "$plist"
    ;;
  restart)
    if ! running; then echo 'Служба не запущена. Используйте install или start.' >&2; exit 1; fi
    launchctl bootout "$target"
    for _ in {1..20}; do
      if ! lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1 &&
         ! lsof -nP -iTCP:8766 -sTCP:LISTEN >/dev/null 2>&1; then break; fi
      sleep 1
    done
    check_ports
    launchctl bootstrap "$domain" "$plist"
    echo 'Служба перезапущена; новый код и .env загружаются сейчас.'
    ;;
  stop)
    if running; then launchctl bootout "$target"; echo 'Служба остановлена.'
    else echo 'Служба уже остановлена.'; fi
    ;;
  status)
    if running; then
      echo 'launchd: служба загружена.'
      launchctl print "$target" | sed -n '1,25p'
    else
      echo 'launchd: служба не запущена.'
    fi
    echo 'Backend:'
    curl -fsS --max-time 5 http://127.0.0.1:8000/api/health || true
    echo
    echo 'Proxy:'
    curl -fsS --max-time 5 http://192.168.2.32:8766/api/health || true
    echo
    echo "Логи: $project_dir/runtime-data/logs/site.out.log и site.err.log"
    ;;
  *)
    echo 'Использование: bash scripts/site-service-mac.sh install|start|restart|stop|status' >&2
    exit 2
    ;;
esac

#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/tools/node-v22.23.5-darwin-x64/bin:$PATH"
backend_pid=''
proxy_pid=''

cleanup() {
  if [ -n "$proxy_pid" ]; then kill -TERM "$proxy_pid" 2>/dev/null || true; fi
  if [ -n "$backend_pid" ]; then kill -TERM "$backend_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

backend_url='http://127.0.0.1:8000/api/health'
proxy_url='http://192.168.2.32:8766/api/health'

if curl -fsS --max-time 3 "$backend_url" >/dev/null 2>&1; then
  echo 'Backend уже отвечает на 127.0.0.1:8000; второй экземпляр не запускаю.'
else
  if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    echo 'Порт 8000 занят, но /api/health не отвечает. Проверьте этот процесс:' >&2
    lsof -nP -iTCP:8000 -sTCP:LISTEN >&2
    exit 1
  fi
  if [ -z "${APP_PYTHON:-}" ]; then
    if [ -x .venv-cv/bin/python ]; then APP_PYTHON=.venv-cv/bin/python
    else APP_PYTHON=.venv/bin/python
    fi
  fi
  if [ ! -x "$APP_PYTHON" ] || ! command -v node >/dev/null 2>&1; then
    echo 'Не найден Python окружения проекта или Node.js.' >&2
    exit 1
  fi
  export APP_PYTHON
  echo "Запускаю приложение на 127.0.0.1:8000 через $APP_PYTHON"
  node scripts/dev.mjs --production &
  backend_pid=$!
  for _ in {1..60}; do
    if curl -fsS --max-time 2 "$backend_url" >/dev/null 2>&1; then break; fi
    if ! kill -0 "$backend_pid" 2>/dev/null; then
      echo 'Backend завершился при запуске. Смотрите ошибку выше.' >&2
      exit 1
    fi
    sleep 1
  done
  if ! curl -fsS --max-time 3 "$backend_url" >/dev/null; then
    echo 'Backend не ответил за 60 секунд.' >&2
    exit 1
  fi
fi

if curl -fsS --max-time 3 "$proxy_url" >/dev/null 2>&1; then
  echo 'Прокси уже отвечает на 192.168.2.32:8766; второй экземпляр не запускаю.'
else
  if lsof -nP -iTCP:8766 -sTCP:LISTEN >/dev/null 2>&1; then
    echo 'Порт 8766 занят, но прокси не отвечает. Остановите только этот процесс в его терминале и повторите запуск:' >&2
    lsof -nP -iTCP:8766 -sTCP:LISTEN >&2
    exit 1
  fi
  if ! command -v python3.14 >/dev/null 2>&1; then
    echo 'Python 3.14 для прокси не найден.' >&2
    exit 1
  fi
  echo 'Запускаю прокси на 192.168.2.32:8766 → 127.0.0.1:8000'
  python3.14 scripts/keen_proxy.py &
  proxy_pid=$!
  for _ in {1..15}; do
    if curl -fsS --max-time 2 "$proxy_url" >/dev/null 2>&1; then break; fi
    if ! kill -0 "$proxy_pid" 2>/dev/null; then
      echo 'Прокси завершился при запуске. Смотрите ошибку выше.' >&2
      exit 1
    fi
    sleep 1
  done
  if ! curl -fsS --max-time 3 "$proxy_url" >/dev/null; then
    echo 'Прокси не ответил за 15 секунд.' >&2
    exit 1
  fi
fi

if ! node scripts/ensure-max-webhook.mjs; then
  echo 'MAX пока не подключён. Сайт и скачивание архива работают; исправьте настройки по docs/MAX_SETUP.md.' >&2
fi

echo 'Локальная цепочка 8000 → 8766 работает. Проверьте: https://test.agentsofcremlin.netcraze.pro/'
if [ "${CHUZHOE_LAUNCHD:-}" = '1' ]; then
  echo 'Сайт работает под launchd; закрытие Terminal его не остановит.'
else
  echo 'Ручной запуск: оставьте терминал открытым; Ctrl+C остановит только процессы этого запуска.'
fi
if [ -z "$backend_pid" ] && [ -z "$proxy_pid" ]; then exit 0; fi
while true; do
  if [ -n "$backend_pid" ] && ! kill -0 "$backend_pid" 2>/dev/null; then
    echo 'Backend завершился.' >&2
    exit 1
  fi
  if [ -n "$proxy_pid" ] && ! kill -0 "$proxy_pid" 2>/dev/null; then
    echo 'Прокси завершился.' >&2
    exit 1
  fi
  sleep 2
done

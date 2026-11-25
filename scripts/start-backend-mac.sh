#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo 'Port 8000 is already in use. Inspect the existing process; no second backend was started.' >&2
  lsof -nP -iTCP:8000 -sTCP:LISTEN >&2
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo 'Missing .venv/bin/python. Install backend/requirements.txt in the project environment first.' >&2
  exit 1
fi
export PATH="$HOME/tools/node-v22.23.5-darwin-x64/bin:$PATH"
export APP_PYTHON=.venv/bin/python
if ! command -v npm >/dev/null 2>&1; then
  echo 'Node.js/npm was not found at the configured path.' >&2
  exit 1
fi
exec npm start

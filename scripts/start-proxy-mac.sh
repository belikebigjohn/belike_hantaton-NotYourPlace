#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

if lsof -nP -iTCP:8766 -sTCP:LISTEN >/dev/null 2>&1; then
  echo 'Port 8766 is already in use. Inspect the existing proxy; no second proxy was started.' >&2
  lsof -nP -iTCP:8766 -sTCP:LISTEN >&2
  exit 1
fi
if ! curl -fsS --max-time 5 http://127.0.0.1:8000/api/health >/dev/null; then
  echo 'Backend at 127.0.0.1:8000 is unavailable. Start and verify it first.' >&2
  exit 1
fi
if ! command -v python3.14 >/dev/null 2>&1; then
  echo 'Python 3.14 was not found on PATH.' >&2
  exit 1
fi
exec python3.14 scripts/keen_proxy.py

#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if command -v python3.12 >/dev/null 2>&1; then
  exec python3.12 run.py
fi
if command -v uv >/dev/null 2>&1; then
  if repogo_python="$(uv python find 3.12 2>/dev/null)"; then
    exec "$repogo_python" run.py
  fi
fi
command -v python3 >/dev/null 2>&1 || { echo '请先安装 Python 3.10+ 与官方 uv，见 DEPLOY.md。'; exit 2; }
exec python3 run.py

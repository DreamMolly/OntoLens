#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_root"
mkdir -p .runtime/tmp .runtime/pip-cache
export TMPDIR="$project_root/.runtime/tmp"
export PIP_CACHE_DIR="$project_root/.runtime/pip-cache"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -e '.[workbench,test]'
if [[ "${1:-}" == "--jev" ]]; then
  .venv/bin/python -m pip install -e '.[jev]'
fi
if [[ ! -f .env ]]; then
  cp -- .env.example .env
fi
.venv/bin/python -m pip check
printf 'Setup complete. Start the business workspace with .venv/bin/python scripts/run_operational.py --bootstrap\n'

#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_root"
if [[ ! -x .venv/bin/python ]]; then
  printf 'Project Python is missing. Run bash setup-local.sh first.\n' >&2
  exit 1
fi
mkdir -p .runtime/tmp .runtime/pip-cache
export TMPDIR="$project_root/.runtime/tmp"
export PIP_CACHE_DIR="$project_root/.runtime/pip-cache"
export PEIWU_ROOT="$project_root"
export PEIWU_DB="${PEIWU_DB:-$project_root/.runtime/workbench.sqlite3}"
exec .venv/bin/python -m uvicorn peiwu.web:create_app --factory --host 127.0.0.1 --port "${1:-8765}"

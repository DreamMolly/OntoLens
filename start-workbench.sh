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
export ONTOLENS_ROOT="$project_root"
export ONTOLENS_DB="${ONTOLENS_DB-${PEIWU_DB-$project_root/.runtime/workbench.sqlite3}}"
exec .venv/bin/python -c 'from pathlib import Path; from ontolens.config import load_environment; import sys, uvicorn; load_environment(Path(".env")); uvicorn.run("ontolens.web:create_app", factory=True, host="127.0.0.1", port=int(sys.argv[1]), proxy_headers=False)' "${1:-8765}"

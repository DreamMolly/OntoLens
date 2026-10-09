#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_root"
if [[ ! -x .venv/bin/python ]]; then
  printf 'Project Python is missing. Run bash setup-local.sh first.\n' >&2
  exit 1
fi
if [[ "${1:-}" == "--check-only" ]]; then
  exec .venv/bin/python scripts/start_demo.py
fi
exec .venv/bin/python scripts/start_demo.py --apply

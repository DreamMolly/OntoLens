"""Check every shipped frontend JavaScript file with Node.js."""
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    files = sorted((ROOT / "src/peiwu/static").glob("*.js"))
    if not files:
        raise RuntimeError("No frontend JavaScript files found")
    for path in files:
        result = subprocess.run(["node", "--check", str(path)], cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
        print(path.relative_to(ROOT).as_posix() + ": syntax passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

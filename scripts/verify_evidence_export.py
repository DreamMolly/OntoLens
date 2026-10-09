"""Verify and recalculate an evidence export offline without modifying it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ontolens.export_verification import verify_evidence_export_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Check package consistency and recalculate frozen decisions offline; no authenticity claim")
    parser.add_argument("input", type=Path, help="Path to a peiwu-replay-1 JSON export")
    args = parser.parse_args()
    report = verify_evidence_export_file(args.input)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

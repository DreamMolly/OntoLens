"""Generate the reproducible synthetic counterfactual evaluation receipt."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from peiwu.counterfactual import ROOT, build_counterfactual_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run synthetic counterfactual/metamorphic evaluation")
    parser.add_argument("--fixture", type=Path, default=ROOT / "data/evaluation/counterfactuals.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/synthetic-counterfactual-report.json")
    args = parser.parse_args()
    report = build_counterfactual_report(root=ROOT, fixture_path=args.fixture)
    # Timestamp is metadata only. All input hashes and case input_hash values
    # are stable across runs with the same checked-in fixture.
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    return 0 if report["summary"]["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

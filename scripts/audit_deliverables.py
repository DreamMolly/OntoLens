from __future__ import annotations

import argparse
import json
from pathlib import Path

from ontolens.delivery import audit


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local evidence, material counts and Nexent package without network requests")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/deliverable-consistency-report.json")
    args = parser.parse_args()
    output = args.output.resolve()
    artifacts = (ROOT / "artifacts").resolve()
    if (output.parent != artifacts or output.suffix.lower() != ".json"
            or not output.name.startswith("deliverable-consistency-")):
        parser.error("Output must be a deliverable-consistency-*.json file directly inside artifacts")
    report = audit(ROOT)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

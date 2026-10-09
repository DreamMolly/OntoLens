"""Generate a reproducible, clearly scoped report for the frozen demo benchmark.

The report is useful for review and award materials, but its scope is limited to
the checked-in synthetic catalog and case files.  It intentionally does not
convert exact matches into industry accuracy or safety claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ontolens.catalog import load_catalog
from ontolens.counterfactual import build_counterfactual_report
from ontolens.evaluate import evaluate, load_cases
from ontolens.gate import read_text, review_promotion
from ontolens.rules import load_rules


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_report() -> dict[str, Any]:
    catalog_path = ROOT / "data" / "catalog.yaml"
    rules_dir = ROOT / "data" / "rules"
    cases_dir = ROOT / "data" / "cases"
    catalog = load_catalog(catalog_path)
    rules = {version: load_rules(rules_dir / f"{version}.yaml") for version in ("v1", "v2", "v3")}
    cases = {
        "regression": load_cases(cases_dir / "regression.yaml"),
        "incidents": load_cases(cases_dir / "incidents.yaml"),
        "heldout": load_cases(cases_dir / "heldout.yaml"),
    }

    evaluation = {
        "v1": {
            "regression": evaluate(catalog, rules["v1"], cases["regression"]),
            "incidents_gold_v1": evaluate(catalog, rules["v1"], cases["incidents"], expect="gold_v1"),
            "incidents_gold_v2": evaluate(catalog, rules["v1"], cases["incidents"], expect="gold_v2"),
            "heldout": evaluate(catalog, rules["v1"], cases["heldout"]),
        },
        "v2": {
            "regression": evaluate(catalog, rules["v2"], cases["regression"]),
            "incidents_gold_v2": evaluate(catalog, rules["v2"], cases["incidents"], expect="gold_v2"),
            "heldout": evaluate(catalog, rules["v2"], cases["heldout"]),
        },
        "v3": {
            "regression": evaluate(catalog, rules["v3"], cases["regression"]),
            "incidents_gold_v2": evaluate(catalog, rules["v3"], cases["incidents"], expect="gold_v2"),
            "heldout": evaluate(catalog, rules["v3"], cases["heldout"]),
        },
    }
    gates = {
        "v2": review_promotion(
            catalog,
            rules["v1"],
            rules["v2"],
            cases["regression"],
            cases["incidents"],
            cases["heldout"],
            candidate_text=read_text(rules_dir / "v2.yaml"),
        ),
        "v3": review_promotion(
            catalog,
            rules["v1"],
            rules["v3"],
            cases["regression"],
            cases["incidents"],
            cases["heldout"],
            candidate_text=read_text(rules_dir / "v3.yaml"),
        ),
    }
    input_files = [
        catalog_path,
        *(rules_dir / f"{version}.yaml" for version in rules),
        *(cases_dir / f"{name}.yaml" for name in cases),
        ROOT / "data" / "evaluation" / "counterfactuals.yaml",
    ]
    return {
        "schema_version": "synthetic-evaluation.v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "mode": "synthetic_demo",
            "claim_boundary": "Frozen checked-in cases only; not industry accuracy, safety rate, or deployment validation.",
            "labels": "Gold labels are developer-authored expectations and are not independent blind evaluation.",
            "model_output_in_metrics": False,
        },
        "inputs": {
            "files": {
                str(path.relative_to(ROOT)).replace("\\", "/"): {
                    "sha256": _sha256(path),
                    "bytes": path.stat().st_size,
                }
                for path in input_files
            },
            "case_counts": {name: len(items) for name, items in cases.items()},
        },
        "evaluation": evaluation,
        "gates": gates,
        "counterfactual": build_counterfactual_report(root=ROOT),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "synthetic-evaluation-report.json")
    args = parser.parse_args()
    report = build_report()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


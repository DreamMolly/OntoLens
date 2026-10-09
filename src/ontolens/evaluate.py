"""Score one rule card against a case file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ontolens.catalog import load_yaml
from ontolens.checker import decide


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    data = load_yaml(path)
    cases = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{path} needs a non-empty cases list")
    return cases


def evaluate(
    catalog: dict[str, Any],
    rules: dict[str, Any],
    cases: list[dict[str, Any]],
    expect: str = "gold",
) -> dict[str, Any]:
    exact = 0
    unsafe = 0
    over_block = 0
    over_issue = 0
    under_issue = 0
    wrong_action = 0
    reason_mismatch = 0
    quantity_mismatch = 0
    action_matrix: dict[str, int] = {}
    failure_categories: dict[str, int] = {}
    failures: list[dict[str, Any]] = []
    for case in cases:
        decision = decide(catalog, rules, case["request"])
        gold = case[expect]
        actual = decision.as_dict()
        action_pair = f"{gold['action']}->{actual['action']}"
        action_matrix[action_pair] = action_matrix.get(action_pair, 0) + 1
        action_matches = actual["action"] == gold["action"]
        reason_matches = actual["reason_code"] == gold["reason_code"]
        quantity_matches = actual["approved_quantity"] == gold["approved_quantity"]
        if decision.matches_gold(gold):
            exact += 1
        else:
            wrong_action += int(not action_matches)
            reason_mismatch += int(not reason_matches)
            quantity_mismatch += int(not quantity_matches)
            failures.append(
                {
                    "id": case["id"],
                    "expected": gold,
                    "actual": actual,
                    "mismatch": {
                        "action": not action_matches,
                        "approved_quantity": not quantity_matches,
                        "reason_code": not reason_matches,
                    },
                }
            )
        if gold["action"] in ("DENY", "ISOLATE") and decision.action in ("ALLOW", "LIMIT"):
            unsafe += 1
            failure_categories["unsafe_release"] = failure_categories.get("unsafe_release", 0) + 1
        if gold["action"] == "ALLOW" and decision.action in ("DENY", "ISOLATE"):
            over_block += 1
            failure_categories["over_block"] = failure_categories.get("over_block", 0) + 1

        # A LIMIT is unsafe when the checker approves more than the gold
        # quantity, even if the action name happens to match.  This metric is
        # intentionally separate from unsafe_release to avoid changing the
        # historical benchmark definition.
        expected_quantity = gold.get("approved_quantity")
        actual_quantity = actual.get("approved_quantity")
        if (
            expected_quantity is not None
            and actual_quantity is not None
            and actual_quantity > expected_quantity
        ):
            over_issue += 1
            failure_categories["over_issue"] = failure_categories.get("over_issue", 0) + 1
        if (
            expected_quantity is not None
            and actual_quantity is not None
            and actual_quantity < expected_quantity
            and actual["action"] in ("ALLOW", "LIMIT")
        ):
            under_issue += 1
            failure_categories["under_issue"] = failure_categories.get("under_issue", 0) + 1

    mismatch_count = len(failures)
    # Keep a compact, stable summary suitable for the UI and exported audit
    # receipts.  All values are derived from the deterministic checker; no
    # model output or self-reported confidence enters these metrics.
    error_breakdown = {
        "wrong_action": wrong_action,
        "wrong_approved_quantity": quantity_mismatch,
        "wrong_reason_code": reason_mismatch,
        "unsafe_release": unsafe,
        "over_issue": over_issue,
        "over_block": over_block,
        "under_issue": under_issue,
    }
    return {
        "rule_version": rules["version"],
        "total": len(cases),
        "exact_match": exact,
        "unsafe_release": unsafe,
        "over_block": over_block,
        "over_issue": over_issue,
        "under_issue": under_issue,
        "decision_coverage": 1.0 if cases else 0.0,
        "error_breakdown": error_breakdown,
        "failure_categories": failure_categories,
        "action_matrix": dict(sorted(action_matrix.items())),
        "mismatch_count": mismatch_count,
        "failures": failures,
    }

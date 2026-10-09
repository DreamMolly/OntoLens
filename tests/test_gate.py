from pathlib import Path

import copy
import pytest
import yaml

from peiwu.catalog import load_catalog
from peiwu.checker import decide
from peiwu.evaluate import evaluate, load_cases
from peiwu.gate import review_promotion
from peiwu.rules import load_rules

ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_catalog(ROOT / "data" / "catalog.yaml")
V1 = load_rules(ROOT / "data" / "rules" / "v1.yaml")
V2 = load_rules(ROOT / "data" / "rules" / "v2.yaml")
V3 = load_rules(ROOT / "data" / "rules" / "v3.yaml")
REGRESSION = load_cases(ROOT / "data" / "cases" / "regression.yaml")
INCIDENTS = load_cases(ROOT / "data" / "cases" / "incidents.yaml")
HELDOUT = load_cases(ROOT / "data" / "cases" / "heldout.yaml")


def test_regression_matches_both_safe_versions():
    for rules in (V1, V2):
        report = evaluate(CATALOG, rules, REGRESSION)
        assert report["failures"] == []
        assert report["unsafe_release"] == 0
        assert report["over_block"] == 0


def test_v1_misses_incidents_and_v2_fixes_them():
    before = evaluate(CATALOG, V1, INCIDENTS, expect="gold_v1")
    after = evaluate(CATALOG, V2, INCIDENTS, expect="gold_v2")
    leaked = evaluate(CATALOG, V1, INCIDENTS, expect="gold_v2")
    assert before["exact_match"] == before["total"]
    assert after["exact_match"] == after["total"]
    assert leaked["exact_match"] == 0
    assert leaked["unsafe_release"] == leaked["total"]


def test_expired_lot_isolates_before_session_conflict():
    case = next(item for item in REGRESSION if item["id"] == "R23")
    decision = decide(CATALOG, V2, case["request"])
    assert decision.action == "ISOLATE"
    assert decision.reason_code == "LOT_NOT_ISSUABLE"


@pytest.mark.parametrize("quantity", [float("nan"), float("inf"), float("-inf"), 10 ** 4000])
def test_decide_rejects_non_finite_or_unrepresentable_quantities(quantity):
    decision = decide(CATALOG, V2, {
        "requester_id": "stu01", "lot_id": "lot_eth", "destination_cabinet_id": "cab_flam",
        "quantity": quantity,
    })
    assert decision.action == "DENY"
    assert decision.reason_code == "INVALID_QUANTITY"


def test_decide_limits_large_integer_without_rounding_away_excess():
    catalog = copy.deepcopy(CATALOG)
    catalog["chemicals"]["ethanol"]["per_issue_limit"] = 2 ** 53
    catalog["lots"]["lot_eth"]["on_hand"] = 2 ** 54

    decision = decide(catalog, V2, {
        "requester_id": "tea01", "lot_id": "lot_eth", "destination_cabinet_id": "cab_flam",
        "quantity": 2 ** 53 + 1,
    })

    assert decision.action == "LIMIT"
    assert decision.reason_code == "ISSUE_CAP"
    assert decision.approved_quantity == 2 ** 53


@pytest.mark.parametrize("section,key,value", [
    ("chemicals", "ethanol", {"per_issue_limit": float("nan")}),
    ("chemicals", "ethanol", {"per_issue_limit": float("inf")}),
    ("lots", "lot_eth", {"on_hand": float("nan")}),
    ("lots", "lot_eth", {"on_hand": float("inf")}),
])
def test_catalog_rejects_non_finite_stock_limits(tmp_path, section, key, value):
    catalog = copy.deepcopy(CATALOG)
    catalog[section][key].update(value)
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    with pytest.raises(ValueError):
        load_catalog(path)


def test_v2_promotes_and_v3_does_not():
    accepted = review_promotion(
        CATALOG, V1, V2, REGRESSION, INCIDENTS, HELDOUT,
        candidate_text=(ROOT / "data" / "rules" / "v2.yaml").read_text(encoding="utf-8"),
    )
    rejected = review_promotion(
        CATALOG, V1, V3, REGRESSION, INCIDENTS, HELDOUT,
        candidate_text=(ROOT / "data" / "rules" / "v3.yaml").read_text(encoding="utf-8"),
    )
    assert accepted["accepted"] is True
    assert accepted["heldout_candidate_unsafe"] == 0
    assert accepted["heldout_baseline_unsafe"] > 0
    assert rejected["accepted"] is False
    assert any(reason.startswith("regression") for reason in rejected["reasons"])


def test_heldout_expansion_matches_v2_without_duplicates():
    assert [case["id"] for case in HELDOUT] == [f"H{index:02d}" for index in range(1, 61)]

    def signature(case):
        request = case["request"]
        return (
            request["requester_id"],
            request["lot_id"],
            request["quantity"],
            request["destination_cabinet_id"],
            tuple(request.get("open_issue_classes") or []),
        )

    seen = {signature(case) for case in REGRESSION + INCIDENTS + HELDOUT[:12]}
    for case in HELDOUT[12:]:
        case_signature = signature(case)
        assert case_signature not in seen
        seen.add(case_signature)

    current = evaluate(CATALOG, V2, HELDOUT)
    baseline = evaluate(CATALOG, V1, HELDOUT)
    assert current["exact_match"] == 60
    assert current["unsafe_release"] == 0
    assert baseline["unsafe_release"] == 13


def test_rule_cards_do_not_name_heldout_cases():
    ids = [case["id"] for case in HELDOUT]
    for name in ("v1.yaml", "v2.yaml"):
        text = (ROOT / "data" / "rules" / name).read_text(encoding="utf-8")
        assert all(case_id not in text for case_id in ids)


def test_evaluation_reports_action_reason_quantity_error_breakdown():
    # Deliberately use a gold record that is stricter than the deterministic
    # checker so the report exercises each audit dimension without touching
    # the frozen benchmark files.
    case = copy.deepcopy(REGRESSION[0])
    case["id"] = "SYNTHETIC-METRICS-01"
    case["gold"] = {
        "action": "DENY",
        "approved_quantity": 50,
        "reason_code": "SYNTHETIC_EXPECTATION",
    }
    report = evaluate(CATALOG, V2, [case])

    assert report["exact_match"] == 0
    assert report["mismatch_count"] == 1
    assert report["error_breakdown"] == {
        "wrong_action": 1,
        "wrong_approved_quantity": 1,
        "wrong_reason_code": 1,
        "unsafe_release": 1,
        "over_issue": 1,
        "over_block": 0,
        "under_issue": 0,
    }
    assert report["failure_categories"] == {
        "unsafe_release": 1,
        "over_issue": 1,
    }
    assert report["action_matrix"] == {"DENY->ALLOW": 1}
    assert report["failures"][0]["mismatch"] == {
        "action": True,
        "approved_quantity": True,
        "reason_code": True,
    }


def test_promotion_report_exposes_machine_readable_gate_checks():
    report = review_promotion(
        CATALOG, V1, V2, REGRESSION, INCIDENTS, HELDOUT,
        candidate_text=(ROOT / "data" / "rules" / "v2.yaml").read_text(encoding="utf-8"),
    )
    assert report["accepted"] is True
    assert report["checks"] == {
        "no_heldout_id_leak": True,
        "regression_unchanged": True,
        "incidents_exact_match": True,
        "heldout_exact_match": True,
        "heldout_unsafe_not_increased": True,
    }
    assert report["regression_changes"] == []
    assert report["incident_report"]["exact_match"] == 5
    assert report["heldout_candidate_report"]["over_issue"] == 0

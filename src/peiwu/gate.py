"""Promotion gate. The candidate may not regress, and may not leak held-out ids."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from peiwu.checker import decide
from peiwu.evaluate import evaluate


def review_promotion(
    catalog: dict[str, Any],
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    regression: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    heldout: list[dict[str, Any]],
    candidate_text: str = "",
) -> dict[str, Any]:
    reasons: list[str] = []
    if "H0" in candidate_text:
        reasons.append("candidate rule text contains a held-out id")

    regression_changes: list[dict[str, Any]] = []
    for case in regression:
        before = decide(catalog, baseline, case["request"])
        after = decide(catalog, candidate, case["request"])
        if not after.same_outcome(before):
            reasons.append(f"regression {case['id']} changed")
            regression_changes.append(
                {"id": case["id"], "before": before.as_dict(), "after": after.as_dict()}
            )

    incident_report = evaluate(catalog, candidate, incidents, expect="gold_v2")
    if incident_report["exact_match"] != incident_report["total"]:
        failed = ", ".join(item["id"] for item in incident_report["failures"])
        reasons.append(f"incidents not fixed: {failed}")

    heldout_candidate = evaluate(catalog, candidate, heldout, expect="gold")
    heldout_baseline = evaluate(catalog, baseline, heldout, expect="gold")
    if heldout_candidate["exact_match"] != heldout_candidate["total"]:
        failed = ", ".join(item["id"] for item in heldout_candidate["failures"])
        reasons.append(f"heldout mismatch: {failed}")
    if heldout_candidate["unsafe_release"] > heldout_baseline["unsafe_release"]:
        reasons.append("heldout unsafe releases increased")

    return {
        "accepted": not reasons,
        "baseline": baseline["version"],
        "candidate": candidate["version"],
        "reasons": reasons,
        "checks": {
            "no_heldout_id_leak": not any("held-out id" in reason for reason in reasons),
            "regression_unchanged": not regression_changes,
            "incidents_exact_match": incident_report["exact_match"] == incident_report["total"],
            "heldout_exact_match": heldout_candidate["exact_match"] == heldout_candidate["total"],
            "heldout_unsafe_not_increased": heldout_candidate["unsafe_release"] <= heldout_baseline["unsafe_release"],
        },
        "regression_changes": regression_changes,
        "incident_report": incident_report,
        "heldout_candidate_report": heldout_candidate,
        "heldout_baseline_report": heldout_baseline,
        "heldout_baseline_unsafe": heldout_baseline["unsafe_release"],
        "heldout_candidate_unsafe": heldout_candidate["unsafe_release"],
    }


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")

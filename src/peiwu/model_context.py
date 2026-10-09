"""Explicit model views: private business records stay inside the workspace."""
from __future__ import annotations

from peiwu.workspace import Workspace, encode


ACTIONS = {"ALLOW", "DENY", "LIMIT", "ISOLATE"}
REASONS = {
    "ALLOWED", "UNKNOWN_REQUESTER", "UNKNOWN_LOT", "UNKNOWN_CABINET", "BANNED_REQUESTER",
    "LOT_NOT_ISSUABLE", "STUDENT_BLOCKED", "CLASS_NOT_AUTHORIZED", "CABINET_INCOMPATIBLE",
    "SESSION_INCOMPATIBLE", "OUT_OF_STOCK", "ISSUE_CAP", "STOCK_SHORT", "INVALID_QUANTITY",
    "MISSING_REFERENCE", "AUTHORIZATION_NOT_ACTIVE", "AUTHORIZATION_EXPIRED", "UNIT_MISMATCH",
}


def decision_summary(run: dict) -> dict:
    """Only enumerated outcomes and counts, never identifiers or original quotes."""
    result = run.get("result", {})
    decision = result.get("decision") or {}
    reason = decision.get("reason_code") or decision.get("reason") or result.get("review", {}).get("reason_code")
    return {
        "status": "ready" if result.get("status") == "ready" else "needs_review",
        "action": decision.get("action") if decision.get("action") in ACTIONS else None,
        "reason_code": reason if reason in REASONS else "REVIEW_REQUIRED",
        "evidence_count": len(result.get("evidence", [])),
        "synthetic": True if result.get("mode") == "synthetic_demo" else None,
        "source_text_sent": False,
    }


def explanation_view(workspace: Workspace, run: dict) -> tuple[dict, str]:
    result = run["result"]
    edges = result.get("evidence", [])
    permitted = bool(edges)
    for edge in edges:
        source = workspace.document(edge["source_id"])
        if source["kind"] == "private" or source["external_model_allowed"] is not True:
            permitted = False
    if permitted:
        context = {"request": run["request"], "result": result}
        # Do not truncate serialized business context halfway through a quote.
        if len(encode(context)) <= 18000:
            return context, "permitted_evidence"
    return decision_summary(run), "decision_summary"

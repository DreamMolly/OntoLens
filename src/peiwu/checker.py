"""Deterministic issue decision."""

from __future__ import annotations

import math
from typing import Any

from peiwu.models import Decision, number
from peiwu.rules import classes_conflict


def decide(catalog: dict[str, Any], rules: dict[str, Any], request: dict[str, Any]) -> Decision:
    version = rules["version"]

    def finish(action: str, reason: str, quantity: float | None = None) -> Decision:
        approved = None if quantity is None else number(quantity)
        return Decision(action, approved, reason, version)

    quantity = request.get("quantity")
    # Reject NaN and infinities before any min/cap arithmetic.  The HTTP
    # contract already rejects them, but the CLI and library entry point call
    # this deterministic checker directly.
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
        return finish("DENY", "INVALID_QUANTITY")
    try:
        finite_quantity = float(quantity)
    except (OverflowError, ValueError):
        return finish("DENY", "INVALID_QUANTITY")
    if not math.isfinite(finite_quantity) or quantity <= 0:
        return finish("DENY", "INVALID_QUANTITY")

    person = catalog["people"].get(request.get("requester_id"))
    lot = catalog["lots"].get(request.get("lot_id"))
    cabinet = catalog["cabinets"].get(request.get("destination_cabinet_id"))
    if person is None:
        return finish("DENY", "UNKNOWN_REQUESTER")
    if lot is None:
        return finish("DENY", "UNKNOWN_LOT")
    if cabinet is None:
        return finish("DENY", "UNKNOWN_CABINET")
    if person["banned"]:
        return finish("DENY", "BANNED_REQUESTER")
    if lot["status"] != "available":
        return finish("ISOLATE", "LOT_NOT_ISSUABLE")
    if rules["deny_students"] and person["role"] == "student":
        return finish("DENY", "STUDENT_BLOCKED")

    chemical = catalog["chemicals"][lot["chemical_id"]]
    hazard = chemical["hazard_class"]
    if hazard not in person["classes"]:
        return finish("DENY", "CLASS_NOT_AUTHORIZED")
    if hazard not in cabinet["allowed_classes"]:
        return finish("DENY", "CABINET_INCOMPATIBLE")

    open_classes = request.get("open_issue_classes") or []
    if not isinstance(open_classes, list):
        raise ValueError("open_issue_classes must be a list")
    if rules["session_incompatibility"] and any(
        classes_conflict(hazard, other, rules) for other in open_classes
    ):
        return finish("DENY", "SESSION_INCOMPATIBLE")

    on_hand = float(lot["on_hand"])
    if on_hand <= 0:
        return finish("DENY", "OUT_OF_STOCK")

    fraction = 1.0 if person["role"] == "teacher" else float(rules["student_fraction"])
    cap = float(chemical["per_issue_limit"]) * fraction
    approved = min(quantity, cap, on_hand)
    if quantity > approved:
        reason = "ISSUE_CAP" if cap <= on_hand else "STOCK_SHORT"
        return finish("LIMIT", reason, approved)
    return finish("ALLOW", "ALLOWED", quantity)

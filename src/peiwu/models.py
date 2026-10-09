"""Shared decision value."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Decision:
    action: str
    approved_quantity: float | None
    reason_code: str
    rule_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "approved_quantity": self.approved_quantity,
            "reason_code": self.reason_code,
            "rule_version": self.rule_version,
        }

    def same_outcome(self, other: "Decision") -> bool:
        if self.action != other.action or self.reason_code != other.reason_code:
            return False
        return _qty_equal(self.approved_quantity, other.approved_quantity)

    def matches_gold(self, gold: dict[str, Any]) -> bool:
        if self.action != gold["action"] or self.reason_code != gold["reason_code"]:
            return False
        return _qty_equal(self.approved_quantity, gold.get("approved_quantity"))


def _qty_equal(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return abs(float(left) - float(right)) < 1e-9


def number(value: float) -> float:
    rounded = round(float(value))
    if abs(float(value) - rounded) < 1e-9:
        return float(int(rounded))
    return float(value)

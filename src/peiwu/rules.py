"""Versioned rule cards."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from peiwu.catalog import HAZARD_CLASSES, load_yaml


def load_rules(path: str | Path) -> dict[str, Any]:
    rules = load_yaml(path)
    version = rules.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("rule card needs a version")
    fraction = float(rules.get("student_fraction", -1))
    if not 0 <= fraction <= 1:
        raise ValueError("student_fraction must be between 0 and 1")
    if not isinstance(rules.get("session_incompatibility"), bool):
        raise ValueError("session_incompatibility must be boolean")
    if not isinstance(rules.get("deny_students"), bool):
        raise ValueError("deny_students must be boolean")
    pairs = rules.get("incompatible_pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("incompatible_pairs must be a non-empty list")
    normalized: set[frozenset[str]] = set()
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError(f"bad pair: {pair}")
        left, right = pair
        if left not in HAZARD_CLASSES or right not in HAZARD_CLASSES or left == right:
            raise ValueError(f"bad pair: {pair}")
        normalized.add(frozenset((left, right)))
    rules["pair_set"] = normalized
    return rules


def classes_conflict(left: str, right: str, rules: dict[str, Any]) -> bool:
    return frozenset((left, right)) in rules["pair_set"]

"""Load and validate the synthetic catalog."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

HAZARD_CLASSES = (
    "FLAMMABLE",
    "OXIDIZER",
    "ACID",
    "BASE",
    "WATER_REACTIVE",
    "TOXIC",
    "COMPRESSED_GAS",
    "GENERAL",
)
LOT_STATUSES = ("available", "expired", "damaged")


def load_yaml(path: str | Path) -> Any:
    file_path = Path(path)
    with file_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{file_path} must contain a mapping")
    return data


def load_catalog(path: str | Path) -> dict[str, Any]:
    catalog = load_yaml(path)
    for key in ("people", "chemicals", "lots", "cabinets"):
        if not isinstance(catalog.get(key), dict) or not catalog[key]:
            raise ValueError(f"catalog.{key} must be a non-empty mapping")
    for person_id, person in catalog["people"].items():
        if person.get("role") not in ("student", "teacher"):
            raise ValueError(f"{person_id} has an unknown role")
        if not isinstance(person.get("banned"), bool):
            raise ValueError(f"{person_id} banned flag must be boolean")
        _check_classes(person.get("classes"), person_id)
    for chemical_id, chemical in catalog["chemicals"].items():
        if chemical.get("hazard_class") not in HAZARD_CLASSES:
            raise ValueError(f"{chemical_id} has an unknown hazard class")
        limit = float(chemical.get("per_issue_limit", 0))
        if not math.isfinite(limit) or limit <= 0:
            raise ValueError(f"{chemical_id} limit must be positive")
    for lot_id, lot in catalog["lots"].items():
        if lot.get("chemical_id") not in catalog["chemicals"]:
            raise ValueError(f"{lot_id} points at an unknown chemical")
        if lot.get("status") not in LOT_STATUSES:
            raise ValueError(f"{lot_id} has an unknown status")
        on_hand = float(lot.get("on_hand", -1))
        if not math.isfinite(on_hand) or on_hand < 0:
            raise ValueError(f"{lot_id} on_hand must be zero or positive")
    for cabinet_id, cabinet in catalog["cabinets"].items():
        _check_classes(cabinet.get("allowed_classes"), cabinet_id)
    return catalog


def _check_classes(classes: Any, owner: str) -> None:
    if not isinstance(classes, list) or not classes:
        raise ValueError(f"{owner} needs at least one class")
    unknown = sorted(set(classes) - set(HAZARD_CLASSES))
    if unknown:
        raise ValueError(f"{owner} has unknown classes: {unknown}")

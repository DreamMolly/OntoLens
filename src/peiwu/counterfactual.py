"""Deterministic synthetic counterfactual/metamorphic evaluation.

This module deliberately evaluates the source-bound workspace contract rather
than modifying the frozen regression, incident, or held-out gold fixtures.
After optional auditable synthetic setup, each case has one declared mutation
and expected outcomes plus a change/invariance relation. It is a diagnostic
of fact sensitivity, not an estimate of real-world accuracy or safety.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from peiwu.catalog import load_catalog, load_yaml
from peiwu.workspace import Workspace


ROOT = Path(__file__).resolve().parents[2]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: str | Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _set_path(root: dict[str, Any], path: str, value: Any, *, allow_new_leaf: bool = False) -> None:
    parts = path.split(".")
    if not parts or any(not part for part in parts):
        raise ValueError(f"invalid mutation path: {path!r}")
    cursor: Any = root
    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor:
            raise ValueError(f"mutation path does not exist: {path!r}")
        cursor = cursor[part]
    if not isinstance(cursor, dict) or (parts[-1] not in cursor and not allow_new_leaf):
        raise ValueError(f"mutation leaf does not exist: {path!r}")
    cursor[parts[-1]] = copy.deepcopy(value)


def _apply_setup(state: dict[str, Any], operations: Any) -> None:
    """Declare synthetic authorization baselines without relaxing mutations."""
    if not isinstance(operations, list):
        raise ValueError("setup must be a list")
    seen: set[str] = set()
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("setup operation must be a mapping")
        path, value = operation.get("path"), operation.get("value")
        allowed = {f"validity.{person}" for person in state["catalog"]["people"]}
        if not isinstance(path, str) or path not in allowed or path in seen:
            raise ValueError("setup requires a unique validity path for an existing person")
        reason = operation.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("setup requires an auditable reason")
        if not isinstance(value, dict) or set(value) != {"from", "until"}:
            raise ValueError("setup validity requires from/until dates")
        if not all(isinstance(value[key], str) for key in ("from", "until")):
            raise ValueError("setup validity dates must be ISO strings")
        if date.fromisoformat(value["from"]) > date.fromisoformat(value["until"]):
            raise ValueError("setup validity start must not exceed end")
        _set_path(state, path, value, allow_new_leaf=True)
        seen.add(path)


def _diff_paths(left: Any, right: Any, prefix: str = "") -> list[str]:
    """Return stable dotted paths whose values differ between two JSON values."""
    if isinstance(left, dict) and isinstance(right, dict):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(_diff_paths(left[key], right[key], child))
        return paths
    if isinstance(left, list) and isinstance(right, list):
        if left == right:
            return []
        return [prefix or "$"]
    return [] if left == right else [prefix or "$"]


def _outcome(workspace: Workspace, snapshot: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    # This is the internal calculation layer, downstream of HTTP validation.
    # In particular, quantity=0 here exercises checker defense, not API behavior.
    result = workspace._calculate(snapshot, copy.deepcopy(request))
    outcome = {
        "status": result.get("status"),
        "unit": result.get("unit"),
        "decision": copy.deepcopy(result.get("decision")),
    }
    if result.get("review"):
        outcome["review_reason_code"] = result["review"]["reason_code"]
    return outcome


def _compare_expected(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    # Python's JSON model treats 100 and 100.0 as the same numeric value,
    # while the receipt intentionally preserves the checker-produced float
    # representation.  Structural equality therefore avoids false failures
    # caused only by YAML number formatting.
    return actual == expected


def _case_input_hash(case: dict[str, Any], base: dict[str, Any], variant: dict[str, Any]) -> str:
    return _sha256_bytes(_canonical({"case": case, "base": base, "variant": variant}).encode("utf-8"))


def build_counterfactual_report(
    *,
    root: str | Path = ROOT,
    fixture_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run the checked-in synthetic metamorphic fixture and return JSON data."""
    project_root = Path(root).resolve()
    fixture = Path(fixture_path or project_root / "data/evaluation/counterfactuals.yaml").resolve()
    catalog_path = project_root / "data/catalog.yaml"
    rules_path = project_root / "data/rules/v2.yaml"
    spec = load_yaml(fixture)
    if spec.get("version") != "synthetic-counterfactual-v1":
        raise ValueError("unsupported counterfactual fixture version")
    cases = spec.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("counterfactual fixture needs a non-empty cases list")

    # Workspace._seed creates the same demo-initial snapshot used by the web
    # contract.  The temporary database is outside the report and discarded.
    temp_root = project_root / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="counterfactual-evaluation-", dir=temp_root) as temp_dir:
        workspace = Workspace(project_root, Path(temp_dir) / "evaluation.sqlite3")
        seed_snapshot = workspace.version("demo-initial")["snapshot"]
        # Validate the catalog/rule inputs explicitly even though Workspace
        # also loads them, so malformed benchmark inputs fail closed.
        catalog = load_catalog(catalog_path)
        if _canonical(catalog) != _canonical(seed_snapshot["catalog"]):
            raise ValueError("workspace seed catalog differs from checked-in catalog")
        if seed_snapshot.get("rules", "") != rules_path.read_text(encoding="utf-8"):
            raise ValueError("workspace seed rules differ from v2 rules fixture")

        results: list[dict[str, Any]] = []
        for raw_case in cases:
            if not isinstance(raw_case, dict):
                raise ValueError("counterfactual case must be a mapping")
            case_id = raw_case.get("id")
            category = raw_case.get("category")
            base_request = raw_case.get("base")
            variant = raw_case.get("variant")
            changed_path = raw_case.get("changed_path")
            expected = raw_case.get("expected")
            relation = raw_case.get("expected_relation", "changed")
            if relation not in ("changed", "invariant"):
                raise ValueError(f"{case_id}: expected_relation must be changed or invariant")
            if not isinstance(case_id, str) or not isinstance(category, str):
                raise ValueError("counterfactual case id/category must be strings")
            if not isinstance(base_request, dict) or not isinstance(variant, dict):
                raise ValueError(f"{case_id}: base/variant must be mappings")
            mutation_path = variant.get("path")
            if mutation_path != changed_path or not isinstance(mutation_path, str):
                raise ValueError(f"{case_id}: changed_path must match variant.path")
            if not isinstance(expected, dict) or not isinstance(expected.get("base"), dict) or not isinstance(expected.get("variant"), dict):
                raise ValueError(f"{case_id}: expected base/variant outcomes required")

            base_snapshot = copy.deepcopy(seed_snapshot)
            base_state = {"request": copy.deepcopy(base_request),
                          "catalog": base_snapshot["catalog"], "issues": base_snapshot["issues"],
                          # Authorization setup is synthetic, never published
                          # as source evidence or a change to frozen gold.
                          "validity": copy.deepcopy(base_snapshot.get("validity", {}))}
            seed_state = copy.deepcopy(base_state)
            setup = raw_case.get("setup", [])
            _apply_setup(base_state, setup)
            setup_changed_paths = _diff_paths(seed_state, base_state)
            variant_state = copy.deepcopy(base_state)
            variant_snapshot = copy.deepcopy(base_snapshot)
            _set_path(variant_state, mutation_path, variant.get("value"))
            variant_request = variant_state["request"]
            # Apply the isolated state to the calculation snapshots.
            base_snapshot["validity"] = base_state["validity"]
            variant_snapshot["validity"] = variant_state["validity"]
            variant_snapshot["catalog"] = variant_state["catalog"]
            variant_snapshot["issues"] = variant_state["issues"]
            base_result = _outcome(workspace, base_snapshot, base_request)
            variant_result = _outcome(workspace, variant_snapshot, variant_request)
            changed_paths = _diff_paths(base_state, variant_state)
            input_hash = _case_input_hash(raw_case, base_state, variant_state)
            checks = {
                "mutation_isolated": changed_paths == [changed_path],
                "expected_base": _compare_expected(base_result, expected["base"]),
                "expected_variant": _compare_expected(variant_result, expected["variant"]),
                "decision_changed": base_result["decision"] != variant_result["decision"],
                "status_changed": base_result["status"] != variant_result["status"],
                "relation_holds": (base_result == variant_result) if relation == "invariant" else (base_result != variant_result),
            }
            # A valid mutation may preserve the outer status (for example
            # ALLOW -> LIMIT remains ``ready``), so status_changed is
            # diagnostic rather than a pass gate. Explicit invariance cases
            # must preserve the complete outcome, including review reasons.
            checks["passed"] = all(checks[name] for name in (
                "mutation_isolated", "expected_base", "expected_variant", "relation_holds"))
            results.append({
                "id": case_id,
                "category": category,
                "evaluation_layer": "internal_calculation",
                "expected_relation": relation,
                "setup": copy.deepcopy(setup),
                "observed_setup_paths": setup_changed_paths,
                "input_hash": input_hash,
                "changed_path": changed_path,
                "observed_changed_paths": changed_paths,
                "base": {"request": base_request, "outcome": base_result},
                "variant": {"mutation": {"path": mutation_path, "value": variant.get("value")},
                            "request": variant_request, "outcome": variant_result},
                "expected": expected,
                "checks": checks,
            })

    by_category: dict[str, dict[str, int]] = {}
    for item in results:
        counts = by_category.setdefault(item["category"], {"total": 0, "passed": 0, "failed": 0})
        counts["total"] += 1
        counts["passed" if item["checks"]["passed"] else "failed"] += 1
    return {
        "schema_version": "synthetic-counterfactual.v1",
        "scope": {
            "mode": "synthetic_demo",
            "claim_boundary": "Synthetic snapshot mutations only; this is not industry accuracy, safety rate, or professional review.",
            "decision_contract": "Internal Workspace._calculate plus deterministic peiwu.checker.decide; no HTTP validation, model or network request.",
            "http_boundary": "Invalid HTTP quantities are rejected by request validation before calculation; checker INVALID_QUANTITY is not an HTTP response.",
            "gold_boundary": "Counterfactual expectations are a separate developer-authored metamorphic fixture; frozen data/cases gold is untouched.",
        },
        "inputs": {
            "fixture": {"path": str(fixture.relative_to(project_root)).replace("\\", "/"), "sha256": file_sha256(fixture), "bytes": fixture.stat().st_size},
            "catalog": {"path": str(catalog_path.relative_to(project_root)).replace("\\", "/"), "sha256": file_sha256(catalog_path), "bytes": catalog_path.stat().st_size},
            "rules": {"path": str(rules_path.relative_to(project_root)).replace("\\", "/"), "sha256": file_sha256(rules_path), "bytes": rules_path.stat().st_size},
            "case_count": len(results),
        },
        "summary": {
            "total": len(results),
            "passed": sum(1 for item in results if item["checks"]["passed"]),
            "failed": sum(1 for item in results if not item["checks"]["passed"]),
            "all_pass": all(item["checks"]["passed"] for item in results),
            "by_category": by_category,
        },
        "cases": results,
    }

"""Offline consistency checks for a detached peiwu-replay-1 export.

This module deliberately has no dependency on the workspace or database. It
contains a small detached replay of the frozen decision contract so a package
can be checked from a clean environment. A passing report does not authenticate
the package author or establish professional validity.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any
from datetime import date

import yaml

from peiwu.review_verification import check_review_records
from peiwu.ledger_import import snapshot_report


_CHECKS = ("format", "version_binding", "snapshot_hash", "source_bytes", "source_closure", "citations",
           "review_records", "decision_reexecution")
_SCOPE = {
    "code": "package_internal_consistency_only",
    "authenticity_verified": False,
    "semantics_verified": False,
    "professional_review_verified": False,
    "decision_reexecuted": False,
}


def _replay_number(value: float) -> float:
    rounded = round(float(value))
    return float(int(rounded)) if abs(float(value) - rounded) < 1e-9 else float(value)


def _replay_decision(catalog: dict[str, Any], rules: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """Small dependency-free copy of the frozen decision contract.

    This intentionally does not import Workspace or the production checker:
    a detached evidence package should catch a changed/tampered decision even
    when it is verified from a clean environment.  The implementation mirrors
    the public decision order and returns only JSON-safe values.
    """
    version = rules["version"]

    def finish(action: str, reason: str, quantity: float | None = None) -> dict[str, Any]:
        return {"action": action,
                "approved_quantity": None if quantity is None else _replay_number(quantity),
                "reason_code": reason, "rule_version": version}

    quantity = request.get("quantity")
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
        frozenset((hazard, other)) in rules["pair_set"] for other in open_classes
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


def _replay_calculation(snapshot: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """Re-execute the package's status/decision contract without a database."""
    catalog = snapshot["catalog"]
    requester = request["requester_id"]
    for group, field in (("people", "requester_id"), ("lots", "lot_id"),
                         ("cabinets", "destination_cabinet_id")):
        if request[field] not in catalog[group]:
            return {"status": "needs_review", "decision": None}
    validity = snapshot.get("validity", {}).get(requester, {})
    at = date.fromisoformat(request["as_of"])
    if validity.get("from") and at < date.fromisoformat(validity["from"]):
        return {"status": "needs_review", "decision": None}
    if validity.get("until") and at > date.fromisoformat(validity["until"]):
        return {"status": "needs_review", "decision": None}
    lot = catalog["lots"][request["lot_id"]]
    unit = catalog["chemicals"][lot["chemical_id"]]["unit"]
    if request["unit"] != unit:
        return {"status": "needs_review", "decision": None}
    rules = yaml.safe_load(snapshot["rules"])
    if not isinstance(rules, dict) or not isinstance(rules.get("version"), str):
        raise ValueError("invalid rule card")
    rules["pair_set"] = {frozenset(pair) for pair in rules["incompatible_pairs"]}
    trusted = {**request, "open_issue_classes": snapshot["issues"][requester]}
    return {"status": "ready", "decision": _replay_decision(catalog, rules, trusted), "unit": unit}


def verify_evidence_export(payload: Any) -> dict[str, Any]:
    """Check package-local identities, hashes, source closure, and citations.

    A needs_review citation with a null quote is explicitly unresolved. It is
    not counted as a verified quote and does not alone make the package invalid.
    Reports contain fixed codes, safe identifiers, and counts, never raw text.
    """
    checks = {name: {"id": name, "status": "not_checked"} for name in _CHECKS}
    issues: list[dict[str, Any]] = []
    scope = dict(_SCOPE)

    def issue(check: str, code: str, *, unresolved: bool = False, **context: Any) -> None:
        item = {"check": check, "code": code, "severity": "unresolved" if unresolved else "error"}
        for key, value in context.items():
            if isinstance(value, int) or (isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value)):
                item[key] = value
        issues.append(item)
        if not unresolved:
            checks[check]["status"] = "failed"
        elif checks[check]["status"] != "failed":
            checks[check]["status"] = "unresolved"

    def finish() -> dict[str, Any]:
        return {"passed": not any(item["severity"] == "error" for item in issues),
                "scope": dict(scope), "checks": list(checks.values()), "issues": issues}

    checks["format"]["status"] = "passed"
    if not isinstance(payload, dict) or payload.get("format") != "peiwu-replay-1":
        issue("format", "unsupported_export_format")
        return finish()
    run, version, sources = payload.get("run"), payload.get("version"), payload.get("sources")
    if (not isinstance(run, dict) or not isinstance(version, dict) or not isinstance(sources, list)
            or not isinstance(run.get("result"), dict) or not isinstance(run.get("request"), dict)
            or not isinstance(version.get("snapshot"), dict)):
        issue("format", "invalid_export_structure")
        return finish()
    result, snapshot = run["result"], version["snapshot"]
    if result.get("status") not in ("ready", "needs_review"):
        issue("format", "invalid_run_status")
    if result.get("status") == "needs_review" and result.get("decision") is not None:
        issue("format", "needs_review_has_decision")
    if result.get("status") == "ready" and not isinstance(result.get("decision"), dict):
        issue("format", "ready_decision_missing")

    checks["version_binding"]["status"] = "passed"
    if not isinstance(version.get("id"), str) or not version["id"]:
        issue("version_binding", "invalid_version_id")
    if not isinstance(run.get("id"), str) or not run["id"]:
        issue("version_binding", "invalid_run_id")
    for value in (run.get("version_id"), result.get("version_id")):
        if value != version.get("id"):
            issue("version_binding", "version_id_mismatch")
    if result.get("run_id") != run.get("id"):
        issue("version_binding", "run_id_mismatch")
    if result.get("snapshot_hash") != version.get("sha256"):
        issue("version_binding", "run_snapshot_hash_mismatch")

    checks["snapshot_hash"]["status"] = "passed"
    try:
        # Identical canonical encoding to Workspace.encode, without importing it.
        encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != version.get("sha256"):
            issue("snapshot_hash", "snapshot_hash_mismatch")
    except (TypeError, ValueError, RecursionError, UnicodeError):
        issue("snapshot_hash", "invalid_snapshot_encoding")

    checks["source_bytes"]["status"] = "passed"
    source_map: dict[str, dict] = {}
    chunk_maps: dict[str, dict[str, str]] = {}
    hash_verified_sources: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or not isinstance(source.get("id"), str) or not source["id"]:
            issue("source_bytes", "invalid_source", source_index=index)
            continue
        source_id = source["id"]
        if source_id in source_map:
            issue("source_bytes", "duplicate_source_id", source_id=source_id)
            continue
        source_map[source_id] = source
        if source.get("raw_encoding") != "base64" or not isinstance(source.get("raw_base64"), str):
            issue("source_bytes", "invalid_raw_encoding", source_id=source_id)
        else:
            try:
                raw = base64.b64decode(source["raw_base64"], validate=True)
                if hashlib.sha256(raw).hexdigest() != source.get("sha256"):
                    issue("source_bytes", "source_hash_mismatch", source_id=source_id)
                else:
                    hash_verified_sources.add(source_id)
            except (ValueError, binascii.Error):
                issue("source_bytes", "invalid_base64", source_id=source_id)
        chunks = source.get("chunks")
        chunk_map: dict[str, str] = {}
        chunk_maps[source_id] = chunk_map
        if not isinstance(chunks, list):
            issue("source_bytes", "invalid_source_chunks", source_id=source_id)
            continue
        for chunk in chunks:
            if (not isinstance(chunk, dict) or not isinstance(chunk.get("locator"), str)
                    or not chunk["locator"] or not isinstance(chunk.get("text"), str)):
                issue("source_bytes", "invalid_source_chunk", source_id=source_id)
                continue
            if chunk["locator"] in chunk_map:
                issue("source_bytes", "duplicate_chunk_locator", source_id=source_id)
            else:
                chunk_map[chunk["locator"]] = chunk["text"]
    checks["source_bytes"]["source_count"] = len(sources)

    checks["source_closure"]["status"] = "passed"
    checks["citations"]["status"] = "passed"
    required_sources: set[str] = set()

    def reference(source_id: Any, **context: Any) -> dict | None:
        if not isinstance(source_id, str) or not source_id:
            issue("source_closure", "invalid_source_reference", **context)
            return None
        required_sources.add(source_id)
        if source_id not in source_map:
            issue("source_closure", "missing_source", source_id=source_id, **context)
            return None
        return source_map[source_id]

    provenance, people = snapshot.get("provenance"), snapshot.get("person_evidence")
    empty_operational = (snapshot.get("mode") == "imported_workspace"
                         and all(snapshot.get("catalog", {}).get(group) == {} for group in ("people", "chemicals", "lots", "cabinets"))
                         and snapshot.get("rules") == "" and result.get("status") == "needs_review")
    if not isinstance(provenance, dict) or (not provenance and not empty_operational):
        issue("source_closure", "invalid_provenance")
    else:
        for source_id in provenance.values():
            reference(source_id)
    if not isinstance(people, dict):
        issue("source_closure", "invalid_person_evidence")
    else:
        for person_id, citation in people.items():
            if not isinstance(citation, dict):
                issue("citations", "invalid_person_citation", person_id=person_id)
                continue
            source_id = citation.get("source_id")
            source = reference(source_id, person_id=person_id)
            if source is None:
                continue
            if citation.get("sha256") != source.get("sha256"):
                issue("citations", "person_source_hash_mismatch", person_id=person_id, source_id=source_id)
            locator = citation.get("locator")
            if (not isinstance(locator, str) or not chunk_maps[source_id].get(locator, "").strip()):
                issue("citations", "person_locator_unresolved", person_id=person_id, source_id=source_id)

    evidence = result.get("evidence")
    verified_quotes = 0
    unresolved_quotes = 0
    if not isinstance(evidence, list) or (not evidence and not empty_operational):
        issue("citations", "invalid_run_evidence")
    else:
        for index, citation in enumerate(evidence):
            if not isinstance(citation, dict):
                issue("citations", "invalid_run_citation", evidence_index=index)
                continue
            source_id = citation.get("source_id")
            source = reference(source_id, evidence_index=index)
            if source is None:
                continue
            if citation.get("sha256") != source.get("sha256"):
                issue("citations", "citation_source_hash_mismatch", source_id=source_id, evidence_index=index)
            locator, quote = citation.get("locator"), citation.get("quote")
            if not isinstance(locator, str) or not locator:
                issue("citations", "invalid_citation_locator", source_id=source_id, evidence_index=index)
                continue
            if "quote" not in citation:
                issue("citations", "missing_citation_quote", source_id=source_id, evidence_index=index)
            elif locator not in chunk_maps[source_id]:
                if (result.get("status") == "needs_review" and quote is None
                        and citation.get("unresolved") is True):
                    unresolved_quotes += 1
                    issue("citations", "unresolved_quote", unresolved=True,
                          source_id=source_id, evidence_index=index)
                else:
                    issue("citations", "citation_locator_unresolved", source_id=source_id,
                          evidence_index=index)
            elif quote is None and result.get("status") == "needs_review":
                unresolved_quotes += 1
                issue("citations", "unresolved_quote", unresolved=True, source_id=source_id, evidence_index=index)
            elif not isinstance(quote, str) or not quote.strip():
                issue("citations", "empty_citation_quote", source_id=source_id, evidence_index=index)
            elif chunk_maps[source_id].get(locator) != quote:
                issue("citations", "citation_quote_mismatch", source_id=source_id, evidence_index=index)
            elif source_id in hash_verified_sources and citation.get("sha256") == source.get("sha256"):
                verified_quotes += 1
    checks["source_closure"]["required_source_count"] = len(required_sources)
    checks["citations"].update(verified_quote_count=verified_quotes, unresolved_quote_count=unresolved_quotes)
    if snapshot.get("mode") == "imported_workspace" and not empty_operational:
        try:
            imported_documents = {source_id: {**source, "raw": base64.b64decode(source["raw_base64"], validate=True)}
                                  for source_id, source in source_map.items()}
            report = snapshot_report(snapshot, imported_documents)
            if not report["accepted"]:
                issue("source_closure", "imported_source_mapping_mismatch")
            if result.get("mode") != "imported_workspace":
                issue("version_binding", "operational_mode_mismatch")
        except (ValueError, TypeError, KeyError, binascii.Error):
            issue("source_closure", "imported_source_mapping_invalid")

    checks["review_records"]["status"] = "passed"
    counts = check_review_records(run, lambda code, **context: issue("review_records", code, **context))
    checks["review_records"].update(counts)

    # Re-run the frozen status/decision contract from the detached snapshot.
    # This remains offline and never trusts source text as executable input.
    checks["decision_reexecution"]["status"] = "passed"
    try:
        replayed = _replay_calculation(snapshot, run["request"])
        if replayed.get("status") != result.get("status"):
            issue("decision_reexecution", "decision_status_mismatch")
        elif replayed.get("status") == "ready":
            expected, actual = result.get("decision"), replayed.get("decision")
            if not isinstance(expected, dict) or not isinstance(actual, dict):
                issue("decision_reexecution", "decision_missing")
            else:
                for key in ("action", "reason_code", "rule_version"):
                    if expected.get(key) != actual.get(key):
                        issue("decision_reexecution", "decision_field_mismatch", field=key)
                expected_quantity, actual_quantity = expected.get("approved_quantity"), actual.get("approved_quantity")
                if expected_quantity is None or actual_quantity is None:
                    if expected_quantity != actual_quantity:
                        issue("decision_reexecution", "decision_quantity_mismatch")
                elif (not isinstance(expected_quantity, (int, float)) or
                      not isinstance(actual_quantity, (int, float)) or
                      not math.isclose(float(expected_quantity), float(actual_quantity), rel_tol=0, abs_tol=1e-9)):
                    issue("decision_reexecution", "decision_quantity_mismatch")
                if "unit" in result and result.get("unit") != replayed.get("unit"):
                    issue("decision_reexecution", "decision_unit_mismatch")
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError, yaml.YAMLError):
        issue("decision_reexecution", "replay_failed")
    else:
        if not any(item["check"] == "decision_reexecution" and item["severity"] == "error" for item in issues):
            scope["decision_reexecuted"] = True
    return finish()


def verify_evidence_export_file(path: Path) -> dict[str, Any]:
    """Read one UTF-8 JSON export without changing it or exposing its contents."""
    def strict_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("non_finite_json_number")

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"),
                             object_pairs_hook=strict_object, parse_constant=reject_constant)
    except OSError:
        code = "input_unreadable"
    except (ValueError, UnicodeError, RecursionError):
        code = "invalid_json"
    else:
        return verify_evidence_export(payload)
    return {"passed": False, "scope": dict(_SCOPE),
            "checks": [{"id": "input", "status": "failed"}],
            "issues": [{"check": "input", "code": code, "severity": "error"}]}

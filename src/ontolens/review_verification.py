"""Validate detached follow-up records without authenticating the operator."""

import hashlib
import json
from datetime import datetime


def check_review_records(run: dict, issue) -> dict:
    """Report internal binding errors; legacy records remain explicitly partial."""
    result = run["result"]
    records = result.get("review_records", [])
    counts = {"record_count": 0, "structured_record_count": 0, "legacy_record_count": 0,
              "reference_count": 0, "unresolved_reference_count": 0}
    if not isinstance(records, list):
        issue("invalid_review_records")
        return counts
    counts["record_count"] = len(records)
    edges = {}
    evidence = result.get("evidence", [])
    for edge in evidence if isinstance(evidence, list) else []:
        if (isinstance(edge, dict) and isinstance(edge.get("source_id"), str)
                and isinstance(edge.get("locator"), str)):
            edges.setdefault((edge["source_id"], edge["locator"]), []).append(edge)
    source_ids = {key[0] for key in edges}
    try:
        request_hash = hashlib.sha256(json.dumps(
            run["request"], ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()
    except (TypeError, ValueError, RecursionError, UnicodeError):
        request_hash = None
    seen_ids, seen_sequences = set(), set()
    last_sequence = 0
    for index, record in enumerate(records):
        def fail(code, **context):
            issue(code, record_index=index, **context)

        if not isinstance(record, dict):
            fail("invalid_review_record")
            continue
        if result.get("status") != "needs_review" or result.get("decision") is not None:
            fail("review_record_on_ready_run")
        if record.get("run_id") != run.get("id"):
            fail("review_run_id_mismatch")
        for field, maximum in (("reviewer", 120), ("note", 1000)):
            value = record.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                fail("invalid_review_" + field)
        if record.get("review_status") not in ("queued", "in_review", "evidence_requested", "closed_no_decision"):
            fail("invalid_review_status")
        if record.get("decision_written") is not False or any(key in record for key in (
                "decision", "action", "approved_quantity", "reason_code", "status")):
            fail("review_wrote_decision")

        modern = record.get("schema_version") == "peiwu-review-1"
        if modern:
            counts["structured_record_count"] += 1
            identity = record.get("id")
            if not isinstance(identity, str) or not identity or identity in seen_ids:
                fail("invalid_review_id")
            else:
                seen_ids.add(identity)
            sequence = record.get("audit_sequence")
            if type(sequence) is not int or sequence <= last_sequence or sequence in seen_sequences:
                fail("invalid_review_sequence")
            else:
                seen_sequences.add(sequence)
                last_sequence = sequence
            if record.get("version_id") != run.get("version_id"):
                fail("review_version_mismatch")
            if record.get("snapshot_hash") != result.get("snapshot_hash"):
                fail("review_snapshot_mismatch")
            if request_hash is None or record.get("request_sha256") != request_hash:
                fail("review_request_mismatch")
            if record.get("reviewer_identity_verified") is not False:
                fail("review_identity_overclaim")
        elif "schema_version" in record:
            fail("unsupported_review_schema")
        else:
            counts["legacy_record_count"] += 1
            fail("legacy_review_binding_unverified", unresolved=True)
        try:
            at = datetime.fromisoformat(record["created_at"])
            if at.tzinfo is None or at.utcoffset() is None:
                raise ValueError("timezone missing")
        except (KeyError, TypeError, ValueError):
            fail("invalid_review_timestamp")

        ids = record.get("evidence_ids")
        ids_valid = isinstance(ids, list) and all(isinstance(value, str) and value for value in ids)
        if not ids_valid:
            fail("review_source_id_unresolved")
            ids = []
        elif len(ids) != len(set(ids)) or not set(ids) <= source_ids:
            fail("review_source_id_unresolved")
        refs = record.get("evidence_references")
        if refs is None and "evidence_references" not in record and not modern:
            if ids:
                fail("legacy_review_locator_unavailable", unresolved=True)
            continue
        if not isinstance(refs, list):
            fail("invalid_review_references")
            continue
        referenced_ids, seen_refs = set(), set()
        for ref_index, ref in enumerate(refs):
            context = {"reference_index": ref_index}
            if not isinstance(ref, dict):
                fail("invalid_review_reference", **context)
                continue
            source_id, locator = ref.get("source_id"), ref.get("locator")
            if not isinstance(source_id, str) or not isinstance(locator, str):
                fail("invalid_review_reference", **context)
                continue
            referenced_ids.add(source_id)
            key = (source_id, locator)
            if key in seen_refs:
                fail("duplicate_review_reference", **context)
            seen_refs.add(key)
            matches = edges.get(key, [])
            if not matches:
                fail("review_locator_unresolved", **context)
                continue
            counts["reference_count"] += 1
            if "quote" not in ref:
                fail("missing_review_quote", **context)
            for edge in matches:
                if ref.get("sha256") != edge.get("sha256"):
                    fail("review_source_hash_mismatch", **context)
                if ref.get("quote") != edge.get("quote"):
                    fail("review_quote_mismatch", **context)
                unresolved = edge.get("quote") is None or edge.get("unresolved") is True
                if type(ref.get("unresolved")) is not bool or ref["unresolved"] != unresolved:
                    fail("review_unresolved_flag_mismatch", **context)
            if ref.get("unresolved") is True:
                counts["unresolved_reference_count"] += 1
                fail("unresolved_review_reference", unresolved=True, **context)
        if ids_valid and set(ids) != referenced_ids:
            fail("review_source_reference_mismatch")
    return counts

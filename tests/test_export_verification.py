import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from ontolens.export_verification import verify_evidence_export, verify_evidence_export_file
from ontolens.workspace import Workspace, encode


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path):
    return Workspace(ROOT, tmp_path / "export-verification.sqlite3")


def exported(workspace, **changes):
    request = {"request_id": "offline-check", "requester_id": "stu01", "lot_id": "lot_eth",
               "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL",
               "as_of": "2026-09-28", **changes}
    result = workspace.check(request)
    return workspace.export(result["run_id"])


def codes(report):
    return {item["code"] for item in report["issues"]}


def rehash_snapshot(bundle):
    digest = hashlib.sha256(encode(bundle["version"]["snapshot"]).encode()).hexdigest()
    bundle["version"]["sha256"] = digest
    bundle["run"]["result"]["snapshot_hash"] = digest


def test_export_verifies_without_mutation_or_claiming_authenticity(workspace):
    bundle = exported(workspace)
    original = copy.deepcopy(bundle)

    report = verify_evidence_export(bundle)

    assert report["passed"] is True
    assert report["issues"] == []
    assert all(check["status"] == "passed" for check in report["checks"])
    assert report["scope"]["code"] == "package_internal_consistency_only"
    assert report["scope"]["decision_reexecuted"] is True
    assert all(value is False for key, value in report["scope"].items()
               if key not in {"code", "decision_reexecuted"})
    assert bundle == original


def test_needs_review_reports_null_quotes_as_unresolved(workspace):
    bundle = exported(workspace, requester_id="missing")
    assert all(item.get("unresolved") is True
               for item in bundle["run"]["result"]["evidence"] if item["quote"] is None)

    report = verify_evidence_export(bundle)

    assert report["passed"] is True
    assert codes(report) == {"unresolved_quote"}
    assert all(issue["severity"] == "unresolved" for issue in report["issues"])
    check = next(check for check in report["checks"] if check["id"] == "citations")
    assert check["status"] == "unresolved"
    assert check["unresolved_quote_count"] == 2
    assert check["verified_quote_count"] == 4


def test_export_verifies_structured_human_review_references(workspace):
    request = {"request_id": "review-export", "requester_id": "missing", "lot_id": "lot_eth",
               "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL",
               "as_of": "2026-09-28"}
    result = workspace.check(request)
    edge = next(edge for edge in result["evidence"] if edge["quote"] is not None)
    workspace.record_review(
        result["run_id"], "审核员甲", "evidence_requested", "请补充缺失人员授权",
        evidence_references=[{
            "source_id": edge["source_id"], "locator": edge["locator"],
            "sha256": edge["sha256"], "quote": edge["quote"], "unresolved": False,
        }],
    )
    bundle = workspace.export(result["run_id"])

    report = verify_evidence_export(bundle)

    assert report["passed"] is True
    check = next(item for item in report["checks"] if item["id"] == "review_records")
    assert check["status"] == "passed"
    assert check["record_count"] == 1


def test_export_rejects_tampered_human_review_reference_or_decision_flag(workspace):
    request = {"request_id": "review-export-tamper", "requester_id": "missing", "lot_id": "lot_eth",
               "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL",
               "as_of": "2026-09-28"}
    result = workspace.check(request)
    edge = next(edge for edge in result["evidence"] if edge["quote"] is not None)
    workspace.record_review(
        result["run_id"], "审核员甲", "evidence_requested", "请补充缺失人员授权",
        evidence_references=[{"source_id": edge["source_id"], "locator": edge["locator"],
                              "sha256": edge["sha256"], "quote": edge["quote"], "unresolved": False}],
    )
    bundle = workspace.export(result["run_id"])
    bundle["run"]["result"]["review_records"][0]["evidence_references"][0]["quote"] = "tampered"
    report = verify_evidence_export(bundle)
    assert report["passed"] is False
    assert "review_quote_mismatch" in codes(report)

    bundle = workspace.export(result["run_id"])
    bundle["run"]["result"]["review_records"][0]["decision_written"] = True
    report = verify_evidence_export(bundle)
    assert report["passed"] is False
    assert "review_wrote_decision" in codes(report)


def test_published_authorization_export_keeps_original_and_override_sources(workspace):
    raw = "stu01 授权仅保留 ACID".encode("utf-8")
    source = workspace.import_document("override.txt", "text/plain", raw,
                                       [{"locator": "L1", "text": raw.decode("utf-8")}], "synthetic")
    parent_id = workspace.active_id()
    candidate = workspace.propose({
        "parent_id": parent_id, "requester_id": "stu01", "classes": ["ACID"],
        "source_id": source["id"], "locator": "L1", "note": "合成来源校验",
        "valid_from": None, "valid_until": None,
    })
    workspace.publish(candidate["id"], parent_id, "合成来源校验")
    bundle = exported(workspace)

    report = verify_evidence_export(bundle)

    assert report["passed"] is True
    assert report["issues"] == []
    closure = next(check for check in report["checks"] if check["id"] == "source_closure")
    assert closure["required_source_count"] == 7


def test_missing_quote_field_is_not_treated_as_a_needs_review_null_quote(workspace):
    bundle = exported(workspace, requester_id="missing")
    del bundle["run"]["result"]["evidence"][0]["quote"]

    report = verify_evidence_export(bundle)

    assert report["passed"] is False
    assert "missing_citation_quote" in codes(report)


def test_needs_review_null_quote_still_requires_existing_locator(workspace):
    bundle = exported(workspace, requester_id="missing")
    citation = bundle["run"]["result"]["evidence"][0]
    citation["locator"] = "missing-location"
    citation["quote"] = None
    citation.pop("unresolved", None)

    report = verify_evidence_export(bundle)

    assert report["passed"] is False
    assert "citation_locator_unresolved" in codes(report)


@pytest.mark.parametrize("kind,expected", [
    ("bytes", "source_hash_mismatch"), ("snapshot", "snapshot_hash_mismatch"),
    ("quote", "citation_quote_mismatch"), ("missing", "missing_source"),
    ("duplicate", "duplicate_source_id"), ("base64", "invalid_base64"),
    ("format", "unsupported_export_format"), ("version_id", "version_id_mismatch"),
    ("run_id", "run_id_mismatch"), ("snapshot_binding", "run_snapshot_hash_mismatch"),
    ("citation_hash", "citation_source_hash_mismatch"), ("null_quote", "empty_citation_quote"),
    ("duplicate_locator", "duplicate_chunk_locator"), ("decision", "decision_field_mismatch"),
])
def test_export_tampering_is_rejected(workspace, kind, expected):
    bundle = exported(workspace)
    if kind == "bytes":
        bundle["sources"][0]["raw_base64"] = base64.b64encode(b"tampered").decode()
    elif kind == "snapshot":
        bundle["version"]["snapshot"]["mode"] = "tampered"
    elif kind == "quote":
        bundle["run"]["result"]["evidence"][0]["quote"] = "private-sentinel-do-not-print"
    elif kind == "missing":
        bundle["sources"].pop()
    elif kind == "duplicate":
        bundle["sources"].append(copy.deepcopy(bundle["sources"][0]))
    elif kind == "base64":
        bundle["sources"][0]["raw_base64"] = "invalid-base64-秘密"
    elif kind == "format":
        bundle["format"] = "unknown"
    elif kind == "version_id":
        bundle["run"]["version_id"] = "different-version"
    elif kind == "run_id":
        bundle["run"]["result"]["run_id"] = "different-run"
    elif kind == "snapshot_binding":
        bundle["run"]["result"]["snapshot_hash"] = "0" * 64
    elif kind == "citation_hash":
        bundle["run"]["result"]["evidence"][0]["sha256"] = "0" * 64
    elif kind == "null_quote":
        bundle["run"]["result"]["evidence"][0]["quote"] = None
    elif kind == "duplicate_locator":
        bundle["sources"][0]["chunks"].append(copy.deepcopy(bundle["sources"][0]["chunks"][0]))
    elif kind == "decision":
        bundle["run"]["result"]["decision"]["reason_code"] = "TAMPERED_DECISION"

    report = verify_evidence_export(bundle)

    assert report["passed"] is False
    assert expected in codes(report)
    assert "private-sentinel" not in json.dumps(report)
    assert "秘密" not in json.dumps(report, ensure_ascii=False)


def test_person_evidence_source_must_be_included_even_when_not_in_run(workspace):
    bundle = exported(workspace)
    bundle["version"]["snapshot"]["person_evidence"]["stu02"] = {
        "source_id": "doc_missing", "locator": "L1", "sha256": "0" * 64}
    rehash_snapshot(bundle)

    report = verify_evidence_export(bundle)

    assert report["passed"] is False
    assert "missing_source" in codes(report)


def test_person_evidence_location_and_hash_are_checked(workspace):
    bundle = exported(workspace)
    source = bundle["sources"][0]
    bundle["version"]["snapshot"]["person_evidence"]["stu02"] = {
        "source_id": source["id"], "locator": "missing-location", "sha256": "0" * 64}
    rehash_snapshot(bundle)

    report = verify_evidence_export(bundle)

    assert report["passed"] is False
    assert {"person_locator_unresolved", "person_source_hash_mismatch"} <= codes(report)


@pytest.mark.parametrize("value", [None, [], {}, {"format": "ontolens-replay-1"}])
def test_malformed_package_returns_a_failure_report(value):
    assert verify_evidence_export(value)["passed"] is False


@pytest.mark.parametrize("text", ['{"secret":"private-sentinel"', '{"format":1,"format":2}', '{"x": NaN}'])
def test_malformed_json_is_not_echoed(tmp_path, text):
    path = tmp_path / "invalid.json"
    path.write_text(text, encoding="utf-8")

    report = verify_evidence_export_file(path)

    assert report["passed"] is False
    assert codes(report) == {"invalid_json"}
    assert "private-sentinel" not in json.dumps(report)


def test_cli_returns_success_failure_and_does_not_rewrite_input(workspace, tmp_path):
    bundle = exported(workspace)
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    original = path.read_bytes()
    command = [sys.executable, str(ROOT / "scripts/verify_evidence_export.py"), str(path)]

    success = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)

    assert success.returncode == 0, success.stderr
    assert json.loads(success.stdout)["passed"] is True
    assert path.read_bytes() == original
    path.write_text('{"private-sentinel":', encoding="utf-8")
    failure = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert failure.returncode == 1
    assert json.loads(failure.stdout)["passed"] is False
    assert failure.stderr == ""
    assert "private-sentinel" not in failure.stdout
    assert "Traceback" not in failure.stdout

"""A follow-up must identify the evidence actually inspected, even after export."""

import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from ontolens.export_verification import verify_evidence_export, verify_evidence_export_file
from tests.test_review_workflow import client, request


def reference(edge):
    return {key: edge[key] for key in ("source_id", "locator", "sha256", "quote")} | {
        "unresolved": edge.get("unresolved", False),
    }


@pytest.fixture
def review_bundle(client):
    result = client.post("/api/check", json=request(requester_id="stu01", unit="g")).json()
    response = client.post(f"/api/runs/{result['run_id']}/review", json={
        "reviewer": "演示操作者", "review_status": "evidence_requested", "note": "核对申请单位",
        "evidence_references": [reference(result["evidence"][0])],
    })
    assert response.status_code == 201, response.text
    return client.get(f"/api/runs/{result['run_id']}/export").json()


@pytest.mark.parametrize("change", ["remove_references", "drop_quote", "empty_references",
                                  "version", "snapshot", "request_hash", "decision",
                                  "status_list", "wrong_locator", "wrong_hash", "duplicate_reference"])
def test_detached_review_cannot_lose_binding_or_acquire_a_decision(review_bundle, change, tmp_path):
    bundle = copy.deepcopy(review_bundle)
    record = bundle["run"]["result"]["review_records"][0]
    if change == "remove_references":
        record.pop("evidence_references")
    elif change == "drop_quote":
        record["evidence_references"][0].pop("quote")
    elif change == "empty_references":
        record["evidence_references"] = []
    elif change == "version":
        record["version_id"] = "other-version"
    elif change == "snapshot":
        record["snapshot_hash"] = "0" * 64
    elif change == "request_hash":
        record["request_sha256"] = "0" * 64
    elif change == "decision":
        record["decision"] = {"action": "ALLOW"}
    elif change == "status_list":
        record["review_status"] = ["in_review"]
    elif change == "wrong_locator":
        record["evidence_references"][0]["locator"] = "$.another_person"
    elif change == "wrong_hash":
        record["evidence_references"][0]["sha256"] = "0" * 64
    elif change == "duplicate_reference":
        record["evidence_references"].append(copy.deepcopy(record["evidence_references"][0]))
    record["note"] = "private-sentinel-do-not-echo"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    report = verify_evidence_export_file(path)
    assert report["passed"] is False
    assert any(item["check"] == "review_records" for item in report["issues"])
    assert "private-sentinel" not in json.dumps(report)


def test_legacy_source_only_review_is_reported_as_unresolved(review_bundle):
    record = review_bundle["run"]["result"]["review_records"][0]
    for key in ("schema_version", "id", "version_id", "snapshot_hash", "request_sha256",
                "audit_sequence", "reviewer_identity_verified", "evidence_references"):
        record.pop(key, None)
    report = verify_evidence_export(review_bundle)
    review = next(item for item in report["checks"] if item["id"] == "review_records")
    assert report["passed"] is True
    assert review["status"] == "unresolved"
    assert review["legacy_record_count"] == 1
    assert "evidence_references" not in record  # Inspection never invents historical references.


def test_parallel_followups_return_their_own_persisted_receipt(client, monkeypatch):
    workspace = client.app.state.workspace
    result = workspace.check(request())
    with workspace.connect() as db:
        original = db.execute("SELECT result FROM runs WHERE id=?", (result["run_id"],)).fetchone()[0]
    original_reader = workspace.review_records
    calls = threading.local()
    barrier = threading.Barrier(2)

    def interleaved_reader(run_id):
        calls.count = getattr(calls, "count", 0) + 1
        if calls.count == 2:
            barrier.wait(timeout=5)
        return original_reader(run_id)

    monkeypatch.setattr(workspace, "review_records", interleaved_reader)
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda note: workspace.record_review(
            result["run_id"], "演示操作者", "in_review", note), ["记录甲", "记录乙"]))
    stored = {record["note"]: record for record in original_reader(result["run_id"])}
    assert all(receipt == stored[receipt["note"]] for receipt in receipts)
    with workspace.connect() as db:
        assert db.execute("SELECT result FROM runs WHERE id=?", (result["run_id"],)).fetchone()[0] == original


@pytest.mark.parametrize("corruption", ["bytes", "chunk"])
def test_review_rejects_changed_source_before_writing_audit(client, corruption):
    result = client.post("/api/check", json=request()).json()
    edge = next(item for item in result["evidence"] if item["quote"] is not None)
    workspace = client.app.state.workspace
    with workspace.connect(write=True) as db:
        if corruption == "bytes":
            db.execute("UPDATE documents SET raw=? WHERE id=?", (b"changed", edge["source_id"]))
        else:
            db.execute("UPDATE documents SET chunks=? WHERE id=?", (
                json.dumps([{"locator": edge["locator"], "text": "changed"}]), edge["source_id"]))
    response = client.post(f"/api/runs/{result['run_id']}/review", json={
        "reviewer": "演示操作者", "review_status": "in_review", "note": "不应记录",
        "evidence_references": [reference(edge)],
    })
    assert response.status_code == 409
    assert workspace.review_records(result["run_id"]) == []


def test_explicit_missing_reference_must_keep_unresolved_flag(client):
    result = client.post("/api/check", json=request()).json()
    edge = next(item for item in result["evidence"] if item["quote"] is None)
    ref = reference(edge) | {"unresolved": False}
    response = client.post(f"/api/runs/{result['run_id']}/review", json={
        "reviewer": "演示操作者", "review_status": "in_review", "note": "缺失应保留",
        "evidence_references": [ref],
    })
    assert response.status_code == 400
    assert client.app.state.workspace.review_records(result["run_id"]) == []

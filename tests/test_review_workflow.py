from pathlib import Path

import pytest
pytest.importorskip("mcp")
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from ontolens.web import create_app


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("PEIWU_MODEL_BASE_URL", "PEIWU_MODEL_NAME", "PEIWU_MODEL_PROTOCOL", "PEIWU_MCP_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    app = create_app(ROOT, tmp_path / "review.sqlite3", seed_demo=True)
    with TestClient(app) as connection:
        connection.headers["X-Peiwu-Token"] = connection.get("/api/status").json()["csrf_token"]
        yield connection


def request(**changes):
    return {"request_id": "REVIEW-01", "requester_id": "missing", "lot_id": "lot_eth",
            "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL",
            "as_of": "2026-09-23", **changes}


def test_needs_review_exposes_structured_gap_without_decision(client):
    response = client.post("/api/check", json=request())
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "needs_review"
    assert result["decision"] is None
    assert result["review"] == {
        "reason_code": "MISSING_REFERENCE",
        "severity": "blocking",
        "blocking_fields": ["requester_id"],
        "requested_evidence": ["people 快照中 missing 的可核验记录"],
        "next_step": "补充带来源定位的人员、批次或柜位记录，再重新核验",
        "decision_blocked": True,
        "synthetic_boundary": "仅用于合成演示复核；不得视为真实行业或专业审核结论",
    }
    assert result["review_records"] == []


@pytest.mark.parametrize("changes,reason_code", [
    ({"unit": "g"}, "UNIT_MISMATCH"),
])
def test_each_blocking_gap_has_a_distinct_machine_reason(client, changes, reason_code):
    result = client.post("/api/check", json=request(requester_id="stu01", **changes)).json()
    assert result["status"] == "needs_review"
    assert result["decision"] is None
    assert result["review"]["reason_code"] == reason_code
    assert result["review"]["decision_blocked"] is True


def test_human_review_record_is_append_only_and_cannot_close_decision(client):
    result = client.post("/api/check", json=request()).json()
    source_id = result["evidence"][0]["source_id"]
    review = client.post("/api/runs/" + result["run_id"] + "/review", json={
        "reviewer": "审核员甲", "review_status": "evidence_requested",
        "note": "请补充人员授权原文及定位", "evidence_ids": [source_id],
    })
    assert review.status_code == 201, review.text
    record = review.json()
    assert record["decision_written"] is False
    assert record["run_id"] == result["run_id"]
    saved = client.get("/api/runs").json()[0]
    assert saved["result"]["decision"] is None
    assert saved["result"]["review_records"][0]["review_status"] == "evidence_requested"
    assert saved["result"]["review_records"][0]["evidence_ids"] == [source_id]
    assert any(event["event"] == "human_review_recorded" for event in client.get("/api/audit").json())
    exported = client.get("/api/runs/" + result["run_id"] + "/export").json()
    assert exported["run"]["result"]["decision"] is None
    assert exported["run"]["result"]["review_records"][0]["decision_written"] is False


def test_review_endpoint_rejects_ready_run_and_unknown_evidence(client):
    ready = client.post("/api/check", json=request(requester_id="stu01")).json()
    assert ready["decision"]["action"] == "ALLOW"
    rejected = client.post("/api/runs/" + ready["run_id"] + "/review", json={
        "reviewer": "审核员甲", "review_status": "in_review", "note": "不应写入",
    })
    assert rejected.status_code == 409

    pending = client.post("/api/check", json=request()).json()
    rejected = client.post("/api/runs/" + pending["run_id"] + "/review", json={
        "reviewer": "审核员甲", "review_status": "in_review", "note": "来源不存在",
        "evidence_ids": ["source-does-not-exist"],
    })
    assert rejected.status_code == 400
    saved = next(run for run in client.get("/api/runs").json() if run["id"] == pending["run_id"])
    assert saved["result"]["review_records"] == []


def test_structured_review_reference_is_canonicalized_by_api(client):
    result = client.post("/api/check", json=request()).json()
    edge = next(item for item in result["evidence"] if item["quote"] is not None)
    response = client.post("/api/runs/" + result["run_id"] + "/review", json={
        "reviewer": "审核员乙", "review_status": "in_review", "note": "核对具体原文",
        "evidence_references": [{
            "source_id": edge["source_id"], "locator": edge["locator"],
            "sha256": edge["sha256"], "quote": edge["quote"], "unresolved": False,
        }],
    })
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["evidence_ids"] == [edge["source_id"]]
    assert record["evidence_references"] == [{
        "source_id": edge["source_id"], "locator": edge["locator"],
        "sha256": edge["sha256"], "quote": edge["quote"], "unresolved": False,
    }]

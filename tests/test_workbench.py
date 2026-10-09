import io
import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("mcp")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from peiwu.web import create_app
from peiwu.workspace import Workspace


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("PEIWU_MODEL_BASE_URL", raising=False)
    monkeypatch.delenv("PEIWU_MODEL_NAME", raising=False)
    monkeypatch.delenv("PEIWU_MODEL_PROTOCOL", raising=False)
    for name in ("TYPESAFE_API_KEY", "TYPESAFE_MODEL", "TYPESAFE_ENDPOINT", "TYPESAFE_BASE_URL", "PEIWU_MCP_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    app = create_app(ROOT, tmp_path / "workbench.sqlite3", seed_demo=True)
    with TestClient(app) as connection:
        connection.headers["X-Peiwu-Token"] = connection.get("/api/status").json()["csrf_token"]
        yield connection


def request(**changes):
    return {"request_id": "T01", "requester_id": "stu01", "lot_id": "lot_eth",
            "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL",
            "as_of": "2026-09-23", **changes}


def source(client, kind="synthetic"):
    response = client.post("/api/documents", data={"kind": kind}, files={
        "file": ("new-policy.md", "# 合成变更\nstu01 授权只保留 ACID。\n".encode(), "text/plain")})
    assert response.status_code == 201
    return response.json()


def candidate(client, **changes):
    document = source(client)
    response = client.post("/api/candidates", json={
        "parent_id": client.get("/api/status").json()["active_id"], "requester_id": "stu01",
        "classes": ["ACID"], "source_id": document["id"], "locator": "L2",
        "note": "仅作合成授权变更演示", **changes,
    })
    assert response.status_code == 201, response.text
    return response.json()


def publish(client, candidate_id, expected="demo-initial"):
    return client.post("/api/candidates/" + candidate_id + "/publish", json={
        "expected_active": expected, "note": "确认仅演示", "confirm_demo": True})


@pytest.mark.parametrize("changes,action,quantity", [
    ({}, "ALLOW", 100.0),
    ({"requester_id": "stu03"}, "DENY", None),
    ({"quantity": 300}, "LIMIT", 250.0),
    ({"lot_id": "lot_eth_exp"}, "ISOLATE", None),
])
def test_decision_actions_with_source_references(client, changes, action, quantity):
    response = client.post("/api/check", json=request(**changes))
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["decision"]["action"] == action
    assert report["decision"]["approved_quantity"] == quantity
    assert report["human_reviewer"] is None
    assert len(report["evidence"]) == 6
    for edge in report["evidence"]:
        document = client.get("/api/documents/" + edge["source_id"]).json()
        assert document["sha256"] == edge["sha256"]
        assert any(chunk["locator"] == edge["locator"] and chunk["text"] == edge["quote"] for chunk in document["chunks"])


@pytest.mark.parametrize("changes", [{"requester_id": "missing"}, {"unit": "g"}])
def test_missing_or_inconsistent_inputs_never_produce_decision(client, changes):
    result = client.post("/api/check", json=request(**changes)).json()
    assert result["status"] == "needs_review"
    assert result["decision"] is None


@pytest.mark.parametrize("quantity", [True, 0, -1, "NaN", "Infinity", "100"])
def test_invalid_quantities_fail_schema(client, quantity):
    assert client.post("/api/check", json=request(quantity=quantity)).status_code == 422


def test_caller_cannot_supply_authorization_or_session_classes(client):
    result = client.post("/api/check", json=request(open_issue_classes=[], classes=["FLAMMABLE"]))
    assert result.status_code == 422


def test_import_is_searchable_but_does_not_change_active_snapshot(client):
    initial = client.get("/api/status").json()["active_id"]
    document = source(client)
    hits = client.get("/api/evidence", params={"query": "只保留"}).json()
    assert hits[0]["id"] == document["id"]
    assert hits[0]["locator"] == "L2"
    assert client.get("/api/status").json()["active_id"] == initial
    assert client.post("/api/check", json=request()).json()["decision"]["action"] == "ALLOW"
    version_hits = client.get("/api/evidence", params={"query": "只保留", "version_id": initial}).json()
    assert version_hits == []


def test_source_external_model_permission_is_explicit_and_private_is_blocked(client):
    initial_sources = client.get("/api/documents").json()
    assert initial_sources and all(source["external_model_allowed"] is True for source in initial_sources)
    local = client.post("/api/documents", data={"kind": "synthetic"}, files={
        "file": ("local.md", "stu01 授权 ACID", "text/plain")}).json()
    assert local["external_model_allowed"] is False
    public = client.post("/api/documents", data={"kind": "public", "allow_external_model": "true"}, files={
        "file": ("public.md", "公开资料", "text/plain")})
    assert public.status_code == 201
    assert public.json()["external_model_allowed"] is True
    private = client.post("/api/documents", data={"kind": "private", "allow_external_model": "true"}, files={
        "file": ("private.md", "私有资料", "text/plain")})
    assert private.status_code == 409


def test_image_with_manual_transcript_becomes_source_bound_assets(client):
    image = (ROOT / "data" / "demo" / "synthetic-asset-label.png").read_bytes()
    transcript = (ROOT / "data" / "demo" / "synthetic-asset-label.transcript.md").read_text(encoding="utf-8")
    response = client.post("/api/documents", data={"kind": "synthetic", "transcript": transcript}, files={
        "file": ("synthetic-asset-label.png", image, "image/png")})
    assert response.status_code == 201
    document = response.json()
    assert document["media_type"] == "image/png"
    assert document["external_model_allowed"] is False
    assert document["chunks"][0]["locator"] == "人工摘录（未核验）"
    assets = client.get("/api/documents/" + document["id"] + "/assets").json()
    observed = {(item["type"], item["id"]) for item in assets["entities"]}
    assert ("Lot", "lot_eth") in observed
    assert ("HazardClass", "FLAMMABLE") in observed
    assert assets["relations"] == []


def test_candidate_suggestions_are_proposed_and_source_bound(client):
    document = client.post("/api/documents", data={"kind": "synthetic"}, files={
        "file": ("authorization.md", "stu01 授权仅保留 ACID，生效: 2026-10-01\n", "text/plain")}).json()
    response = client.get("/api/documents/" + document["id"] + "/suggestions")
    assert response.status_code == 200
    suggestions = response.json()["candidates"]
    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["status"] == "proposed"
    assert suggestion["review_required"] is True
    assert suggestion["requester_id"] == "stu01"
    assert suggestion["proposed_classes"] == ["ACID"]
    assert suggestion["change_mode"] == "replace"
    assert suggestion["valid_from"] == "2026-10-01"
    assert suggestion["source_id"] == document["id"]
    assert client.get("/api/status").json()["active_id"] == "demo-initial"


def test_asset_recognition_preserves_sources_and_proposes_relations(client):
    document = client.post("/api/documents", data={"kind": "synthetic"}, files={
        "file": ("assets.md", "stu01 授权仅保留 ACID。lot_eth 位于 cab_flam.\n", "text/plain")}).json()
    response = client.get("/api/documents/" + document["id"] + "/assets")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"]["version"] == "peiwu-ontology-1"
    assert payload["schema"]["alignment"]["external_standard"] is None
    observed = {(item["type"], item["id"], item["locator"]) for item in payload["entities"]}
    assert ("Person", "stu01", "L1") in observed
    assert ("Lot", "lot_eth", "L1") in observed
    assert ("StorageZone", "cab_flam", "L1") in observed
    assert ("HazardClass", "ACID", "L1") in observed
    relation = payload["relations"][0]
    assert relation["type"] == "authorized_for"
    assert relation["status"] == "proposed"
    assert relation["review_required"] is True
    assert relation["source_id"] == document["id"]
    assert payload["schema_candidates"] == []


def test_asset_recognition_proposes_effective_period_schema_property(client):
    document = client.post("/api/documents", data={"kind": "synthetic"}, files={
        "file": ("validity.md", "stu01 授权 ACID，生效: 2026-10-01，有效至: 2026-12-31\n", "text/plain")}).json()
    payload = client.get("/api/documents/" + document["id"] + "/assets").json()
    assert len(payload["schema_candidates"]) == 1
    candidate = payload["schema_candidates"][0]
    assert candidate["relation"] == "authorized_for"
    assert candidate["properties"] == ["valid_from", "valid_until"]
    assert candidate["status"] == "proposed"
    assert candidate["source_id"] == document["id"]


def test_jev_rerank_is_explicitly_unavailable_without_configuration(client):
    response = client.post("/api/evidence/jev", json={"query": "stu01 授权", "limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert "TYPESAFE_API_KEY" in payload["reason"]
    assert client.get("/api/status").json()["jev_configured"] is False


def test_web_jev_cannot_request_online_even_with_configured_key(client, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    response = client.post("/api/evidence/jev", json={"query": "stu01", "limit": 5})
    assert response.status_code == 200
    assert response.json()["code"] == "live_not_authorized"
    assert response.json()["request_count"] == 0
    rejected = client.post("/api/evidence/jev", json={"query": "stu01", "allow_live": True})
    assert rejected.status_code == 422


def test_version_preview_publish_rollback_and_immutable_old_record(client):
    old_run = client.post("/api/check", json=request()).json()
    proposed = candidate(client)
    preview = client.get("/api/candidates/" + proposed["id"] + "/preview").json()
    assert len(preview["changes"]) == 1
    assert preview["changes"][0]["after"]["decision"]["action"] == "DENY"
    response = publish(client, proposed["id"])
    assert response.status_code == 200, response.text
    active = response.json()["id"]
    current = client.post("/api/check", json=request()).json()
    assert current["decision"]["reason_code"] == "CLASS_NOT_AUTHORIZED"
    assert current["version_id"] == active
    saved = client.get("/api/runs/" + old_run["run_id"] + "/export").json()
    assert saved["run"]["result"]["decision"]["action"] == "ALLOW"
    assert saved["version"]["id"] == "demo-initial"
    assert publish(client, proposed["id"], active).status_code == 409
    response = client.post("/api/versions/demo-initial/rollback", json={
        "expected_active": active, "note": "恢复合成旧版本", "confirm_demo": True})
    assert response.status_code == 200
    assert client.post("/api/check", json=request()).json()["decision"]["action"] == "ALLOW"
    assert any(event["event"] == "demo_version_rolled_back" for event in client.get("/api/audit").json())


def test_two_candidates_cannot_silently_overwrite_each_other(client):
    first = candidate(client)
    second = candidate(client)
    assert publish(client, first["id"]).status_code == 200
    assert publish(client, second["id"]).status_code == 409


def test_private_source_cannot_be_published_without_real_review(client):
    document = source(client, kind="private")
    response = client.post("/api/candidates", json={
        "parent_id": "demo-initial", "requester_id": "stu01", "classes": ["ACID"],
        "source_id": document["id"], "locator": "L2", "note": "私有资料"})
    assert response.status_code == 409


def test_unverified_and_empty_source_locations_cannot_be_cited(client):
    document = source(client)
    response = client.post("/api/candidates", json={
        "parent_id": "demo-initial", "requester_id": "stu01", "classes": ["ACID"],
        "source_id": document["id"], "locator": "L999", "note": "错误引用"})
    assert response.status_code == 400


@pytest.mark.parametrize("dates", [
    {"valid_from": "2026-10-01"}, {"valid_until": "2026-09-01"},
])
def test_validity_fails_closed(client, dates):
    proposed = candidate(client, classes=["FLAMMABLE"], **dates)
    assert publish(client, proposed["id"]).status_code == 200
    report = client.post("/api/check", json=request()).json()
    assert report["status"] == "needs_review"
    assert report["decision"] is None


def test_date_range_and_publish_confirmation_validated(client):
    document = source(client)
    response = client.post("/api/candidates", json={
        "parent_id": "demo-initial", "requester_id": "stu01", "classes": ["ACID"],
        "source_id": document["id"], "locator": "L2", "note": "错误日期",
        "valid_from": "2026-10-01", "valid_until": "2026-09-01"})
    assert response.status_code == 422
    proposed = candidate(client)
    response = client.post("/api/candidates/" + proposed["id"] + "/publish", json={
        "expected_active": "demo-initial", "note": "未确认", "confirm_demo": False})
    assert response.status_code == 422


def test_cross_origin_write_and_missing_token_rejected(client):
    assert client.post("/api/check", json=request(), headers={"X-Peiwu-Token": ""}).status_code == 403
    assert client.post("/api/check", json=request(), headers={"Origin": "https://example.org"}).status_code == 403


def test_upload_types_and_limits(client):
    invalid_files = [("bad.exe", b"bad"), ("bad.json", b"{oops"), ("bad.png", b"<script/>"),
                     ("empty.txt", b""), ("large.txt", b"x" * (4 * 1024 * 1024 + 1))]
    for name, content in invalid_files:
        response = client.post("/api/documents", data={"kind": "synthetic"}, files={"file": (name, content)})
        assert response.status_code in (400, 413)
    csv_source = client.post("/api/documents", data={"kind": "synthetic"}, files={"file": ("table.csv", b"person,class\r\nstu01,ACID")}).json()
    assert csv_source["chunks"][1]["locator"] == "R2"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    writer.write(output)
    pdf = client.post("/api/documents", data={"kind": "synthetic"}, files={"file": ("scan.pdf", output.getvalue())}).json()
    assert pdf["chunks"] == []
    assert "OCR" in pdf["notice"]


def test_empty_people_and_disconnected_model_are_honest(client):
    status = client.get("/api/status").json()
    assert status["team"] == {"students": [], "advisor": None, "reviewer": None}
    assert status["model_configured"] is False
    run = client.post("/api/check", json=request()).json()
    assert client.post("/api/runs/" + run["run_id"] + "/explain").status_code == 503


def test_workspace_survives_restart_without_reseeding(client):
    workspace = client.app.state.workspace
    proposed = candidate(client)
    version = publish(client, proposed["id"]).json()
    reopened = Workspace(ROOT, workspace.database)
    assert reopened.active_id() == version["id"]
    assert len(reopened.documents()) == 7


def test_workspace_migrates_legacy_document_permission_without_implicit_consent(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("""CREATE TABLE documents (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, media_type TEXT NOT NULL,
            sha256 TEXT NOT NULL, kind TEXT NOT NULL, chunks TEXT NOT NULL,
            raw BLOB NOT NULL, created_at TEXT NOT NULL)""")
        connection.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)", (
            "legacy-doc", "legacy.md", "text/plain", "hash", "synthetic", "[]", b"legacy", "2026-09-23T00:00:00Z"))
    workspace = Workspace(ROOT, database)
    assert workspace.document("legacy-doc")["external_model_allowed"] is False
    seeded = workspace.version("demo-initial")["snapshot"]["provenance"]["issues"]
    assert workspace.document(seeded)["external_model_allowed"] is True
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
    assert "external_model_allowed" in columns


def test_mcp_initialize_tools_and_call(client):
    headers = {"Accept": "application/json, text/event-stream"}
    initialized = client.post("/mcp/", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "peiwu-test", "version": "1"}}})
    assert initialized.status_code == 200, initialized.text
    headers["MCP-Protocol-Version"] = initialized.json()["result"]["protocolVersion"]
    result = client.post("/mcp/", headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).json()
    tool_names = {tool["name"] for tool in result["result"]["tools"]}
    assert tool_names == {"evidence_lookup", "graph_query", "asset_recognition", "candidate_suggestions", "evidence_rerank_jev", "decision_check", "candidate_review"}
    called = client.post("/mcp/", headers=headers, json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "decision_check", "arguments": {"request": request(requester_id="stu03")}}})
    assert called.status_code == 200, called.text
    result = called.json()["result"]
    assert not result.get("isError")
    payload = json.loads(result["content"][0]["text"])
    assert payload["decision"]["reason_code"] == "SESSION_INCOMPATIBLE"

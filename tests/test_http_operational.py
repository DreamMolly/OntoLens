"""HTTP acceptance with disposable synthetic records; no external service calls."""
from __future__ import annotations

import base64
import builtins
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
import pytest

from ontolens.access import update_account
from ontolens.export_verification import verify_evidence_export
from ontolens.web import create_app

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "HTTP-TEST-FIXTURE-ONLY-4892"
PRIVATE_MARKER = "PRIVATE_TEST_LEDGER_ORIGINAL_MUST_STAY_LOCAL"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for key in list(os.environ):
        if key.startswith(("PEIWU_", "TYPESAFE_", "MODEL_", "NEXENT_", "OPENAI_", "ANTHROPIC_")):
            monkeypatch.delenv(key, raising=False)
    async def no_external_post(*args, **kwargs):
        pytest.fail("HTTP acceptance must never contact an external model or platform")
    monkeypatch.setattr(httpx.AsyncClient, "post", no_external_post)


@pytest.fixture
def app_factory(tmp_path, monkeypatch):
    def factory(auth=False, seed_demo=None):
        if auth:
            accounts = tmp_path / "accounts.json"
            for role in ("admin", "operator", "reviewer", "viewer"):
                update_account(accounts, role + "-account", name="TEST " + role,
                               role=role, password=PASSWORD, create=True)
            monkeypatch.setenv("PEIWU_AUTH_FILE", str(accounts))
            monkeypatch.setenv("PEIWU_SESSION_DB", str(tmp_path / "access.sqlite3"))
        return create_app(ROOT, tmp_path / "workbench.sqlite3", seed_demo=seed_demo)
    return factory


def business_files(stock=200):
    """Explicitly synthetic test fixture, presented as local private input bytes."""
    facts = {
        "people": {
            "staff_947": {"role": "teacher", "banned": False, "classes": ["FLAMMABLE"],
                          "authorization_basis": PRIVATE_MARKER, "valid_from": "2026-01-01", "valid_until": "2026-10-31"},
            "blocked_548": {"role": "teacher", "banned": True, "classes": ["FLAMMABLE"],
                            "authorization_basis": PRIVATE_MARKER, "valid_from": "2026-01-01", "valid_until": "2026-10-31"}},
        "chemicals": {"chemical_582": {"hazard_class": "FLAMMABLE", "per_issue_limit": 50, "unit": "mL"}},
        "lots": {"lot_631": {"chemical_id": "chemical_582", "on_hand": stock, "status": "available"},
                 "expired_671": {"chemical_id": "chemical_582", "on_hand": 20, "status": "expired"}},
        "cabinets": {"cab_209": {"allowed_classes": ["FLAMMABLE"]}},
        "issues": {"staff_947": [], "blocked_548": []},
        "rules": {"version": "HTTP-TEST-POLICY-1", "student_fraction": 0.5, "session_incompatibility": True,
                  "deny_students": False, "incompatible_pairs": [["FLAMMABLE", "OXIDIZER"]]},
    }
    return {group: (b"\xef\xbb\xbf" + json.dumps(data, ensure_ascii=False, indent=2).replace("\n", "\r\n").encode("utf-8"))
            for group, data in facts.items()}


def login(client, role):
    response = client.post("/api/auth/login", json={"username": role + "-account", "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"x-peiwu-token": response.json()["csrf_token"]}


def local_headers(client):
    return {"x-peiwu-token": client.get("/api/status").json()["csrf_token"]}


def upload(client, headers, files=None, **changes):
    original_files = business_files() if files is None else files
    data = {"label": "SYNTHETIC HTTP TEST FIXTURE", "operator": "forged-admin-name",
            "basis": "Disposable test fixture authorized for contract verification",
            "purpose": "HTTP acceptance only", "authorized_by": "TEST authority",
            "recorded_at": "2026-10-08", "kind": "private", "local_operation_authorized": "true", **changes}
    # Same Unicode/path-like name for every source must not clash or escape storage.
    multipart = {group: ("../../原始台账.json", raw, "application/json") for group, raw in original_files.items()}
    return client.post("/api/ledger-bundles", headers=headers, data=data, files=multipart)


def publish(client, candidate_id, headers, active="operational-initial", **changes):
    payload = {"expected_active": active, "note": "Publish synthetic HTTP test fixture",
               "confirm_publish": True, **changes}
    return client.post(f"/api/candidates/{candidate_id}/publish", headers=headers, json=payload)


def check_request(**changes):
    return {"request_id": "http-fixture-check", "requester_id": "staff_947", "lot_id": "lot_631",
            "destination_cabinet_id": "cab_209", "quantity": 20.0, "unit": "mL", "as_of": "2026-10-08", **changes}


def activated_local(client):
    headers = local_headers(client)
    imported = upload(client, headers)
    assert imported.status_code == 201, imported.text
    published = publish(client, imported.json()["id"], headers)
    assert published.status_code == 200, published.text
    return headers, published.json()["id"]


def test_new_default_workspace_template_and_empty_check_have_no_fake_business_facts(app_factory):
    with TestClient(app_factory()) as client:
        status = client.get("/api/status").json()
        assert status["mode"] == "operational_empty"
        assert not status["model_configured"] and not status["nexent_connected"]
        catalog = client.get("/api/catalog").json()
        assert all(records == {} for records in catalog["catalog"].values())
        assert client.get("/api/documents").json() == []
        template = client.get("/api/ledger-bundles/template").json()
        assert set(template["sources"]) == set(business_files())
        skeleton = {group: source["content"].encode("utf-8") for group, source in template["sources"].items()}
        assert all(json.loads(skeleton[group]) == {} for group in ("people", "chemicals", "lots", "cabinets", "issues"))
        failed = upload(client, local_headers(client), files=skeleton)
        assert failed.status_code == 400
        assert client.get("/api/documents").json() == []
        assert client.get("/api/versions").json()["candidates"] == []
        empty = client.post("/api/check", headers=local_headers(client), json=check_request())
        assert empty.status_code == 200, empty.text
        result = empty.json()
        assert result["status"] == "needs_review" and result["decision"] is None and result["evidence"] == []
        exported = client.get(f"/api/runs/{result['run_id']}/export").json()
        assert verify_evidence_export(exported)["passed"]


def test_http_import_preview_explicit_publish_cas_actions_export_and_stock_rollback(app_factory):
    with TestClient(app_factory(seed_demo=False)) as client:
        headers = local_headers(client)
        first = upload(client, headers)
        stale = upload(client, headers)
        assert first.status_code == stale.status_code == 201
        candidate = first.json()["id"]
        preview = client.get(f"/api/candidates/{candidate}/preview")
        assert preview.status_code == 200 and preview.json()["structural_validation"]["accepted"]
        legacy_confirmation = client.post(f"/api/candidates/{candidate}/publish", headers=headers,
                                          json={"expected_active": "operational-initial", "note": "TEST", "confirm_demo": True})
        assert legacy_confirmation.status_code == 422
        assert client.get("/api/status").json()["mode"] == "operational_empty"
        published = publish(client, candidate, headers)
        assert published.status_code == 200, published.text
        first_version = published.json()["id"]
        assert publish(client, stale.json()["id"], headers).status_code == 409
        catalog = client.get("/api/catalog").json()
        assert catalog["mode"] == "imported_workspace" and "staff_947" in catalog["catalog"]["people"]
        assert "stu01" not in catalog["catalog"]["people"]
        cases = [(check_request(), "ALLOW"), (check_request(quantity=80.0), "LIMIT"),
                 (check_request(requester_id="blocked_548"), "DENY"), (check_request(lot_id="expired_671"), "ISOLATE"),
                 (check_request(as_of="2026-11-01"), None), (check_request(requester_id="absent-person"), None),
                 (check_request(unit="g"), None)]
        original_export = None
        for payload, expected in cases:
            response = client.post("/api/check", headers=headers, json=payload)
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["mode"] == "imported_workspace"
            assert (result["decision"]["action"] if result["decision"] else None) == expected
            exported = client.get(f"/api/runs/{result['run_id']}/export").json()
            report = verify_evidence_export(exported)
            assert report["passed"] and report["scope"]["decision_reexecuted"], report
            if expected == "ALLOW": original_export = exported
        sources = original_export["sources"]
        snapshot = original_export["version"]["snapshot"]
        originals = business_files()
        assert len(sources) == 12 and all(source["kind"] == "private" and not source["external_model_allowed"] for source in sources)
        source_map = {source["id"]: source for source in sources}
        for group, binding in snapshot["import_bindings"].items():
            source = source_map[binding["original_source_id"]]
            assert source["title"] == group + ".json"
            assert base64.b64decode(source["raw_base64"]) == originals[group]
        updated = upload(client, headers, files=business_files(stock=7))
        updated_candidate = updated.json()["id"]
        impact = client.get(f"/api/candidates/{updated_candidate}/preview").json()
        assert any(change["after"].get("decision", {}).get("approved_quantity") == 7 for change in impact["changes"] if change["after"].get("decision"))
        second = publish(client, updated_candidate, headers, active=first_version)
        assert second.status_code == 200, second.text
        assert client.post("/api/check", headers=headers, json=check_request()).json()["decision"]["approved_quantity"] == 7
        assert client.get(f"/api/runs/{original_export['run']['id']}/export").json() == original_export
        rolled_back = client.post(f"/api/versions/{first_version}/rollback", headers=headers,
                                  json={"expected_active": second.json()["id"], "note": "TEST rollback", "confirm_publish": True})
        assert rolled_back.status_code == 200, rolled_back.text
        assert client.post("/api/check", headers=headers, json=check_request()).json()["decision"]["approved_quantity"] == 20


def test_http_auth_cookie_csrf_role_bound_identity_and_transactional_audit(app_factory):
    with TestClient(app_factory(auth=True, seed_demo=False)) as client:
        assert client.get("/api/status").status_code == 401
        assert client.get("/api/auth/session").json()["authenticated"] is False
        login_response = client.post("/api/auth/login", json={"username": "operator-account", "password": PASSWORD})
        assert login_response.status_code == 200
        cookie = login_response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert "session_token" not in login_response.json()
        operator_headers = {"x-peiwu-token": login_response.json()["csrf_token"]}
        assert client.post("/api/check", json=check_request()).status_code == 403
        assert client.post("/api/check", headers={**operator_headers, "origin": "https://other.invalid"}, json=check_request()).status_code == 403
        imported = upload(client, operator_headers, operator="admin-account")
        assert imported.status_code == 201, imported.text
        candidate = imported.json()["id"]
        assert imported.json()["patch"]["operator"] == "operator-account"
        assert publish(client, candidate, operator_headers).status_code == 403
        viewer_headers = login(client, "viewer")
        assert client.get("/api/catalog").status_code == 200
        assert client.post("/api/check", headers=viewer_headers, json=check_request()).status_code == 403
        assert upload(client, viewer_headers).status_code == 403
        admin_headers = login(client, "admin")
        assert publish(client, candidate, admin_headers).status_code == 200
        reviewer_headers = login(client, "reviewer")
        checked = client.post("/api/check", headers=reviewer_headers, json=check_request(as_of="2026-11-01"))
        assert checked.status_code == 200, checked.text
        run = checked.json()
        assert run["status"] == "needs_review" and run["decision"] is None
        first_edge = run["evidence"][0]
        reference = {key: first_edge[key] for key in ("source_id", "locator", "sha256", "quote")}
        reviewed = client.post(f"/api/runs/{run['run_id']}/review", headers=reviewer_headers,
                               json={"reviewer": "forged-admin-name", "review_status": "in_review", "note": "TEST review only",
                                     "evidence_references": [reference]})
        assert reviewed.status_code == 201, reviewed.text
        assert reviewed.json()["reviewer"] == "reviewer-account" and not reviewed.json()["decision_written"]
        events = client.get("/api/audit").json()
        actors = {event["event"]: event["payload"].get("actor", {}).get("username") for event in events}
        assert actors["ledger_bundle_candidate_created"] == "operator-account"
        assert actors["ledger_version_published"] == "admin-account"
        assert actors["decision_checked"] == actors["human_review_recorded"] == "reviewer-account"
        exported = client.get(f"/api/runs/{run['run_id']}/export").json()
        assert exported["run"]["result"]["decision"] == run["decision"]
        assert verify_evidence_export(exported)["passed"]
        logged_out = client.post("/api/auth/logout", headers=reviewer_headers)
        assert logged_out.status_code == 200 and not client.get("/api/auth/session").json()["authenticated"]
        assert client.get("/api/catalog").status_code == 401


def test_private_http_explanation_sends_only_whitelisted_summary_and_cannot_change_decision(app_factory, monkeypatch):
    with TestClient(app_factory(seed_demo=False)) as client:
        headers, _ = activated_local(client)
        run = client.post("/api/check", headers=headers, json=check_request(requester_id="blocked_548")).json()
        assert run["decision"]["action"] == "DENY"
        url = f"/api/runs/{run['run_id']}/explain"
        assert client.post(url, headers=headers).status_code == 503
        before = client.get(f"/api/runs/{run['run_id']}/export").json()
        captured = []
        async def provider_stub(self, endpoint, *, headers, json):
            captured.append({"url": endpoint, "body": json})
            return httpx.Response(200, request=httpx.Request("POST", endpoint),
                                  json={"choices": [{"message": {"content": "TEST provider suggests ALLOW (unverified text)"}}]})
        monkeypatch.setenv("PEIWU_MODEL_BASE_URL", "https://fixture-provider.invalid/v1")
        monkeypatch.setenv("PEIWU_MODEL_NAME", "fixture-model")
        monkeypatch.setenv("PEIWU_MODEL_API_KEY", "fixture-key-only")
        monkeypatch.setattr(httpx.AsyncClient, "post", provider_stub)
        response = client.post(url, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["context_scope"] == "decision_summary"
        assert response.json()["source_text_sent"] is False and response.json()["verified"] is False
        assert len(captured) == 1 and captured[0]["url"] == "https://fixture-provider.invalid/v1/chat/completions"
        summary = json.loads(captured[0]["body"]["messages"][-1]["content"])
        assert set(summary) == {"status", "action", "reason_code", "evidence_count", "synthetic", "source_text_sent"}
        assert summary["action"] == "DENY" and summary["source_text_sent"] is False
        body_text = json.dumps(captured[0]["body"], ensure_ascii=False)
        for secret in (PRIVATE_MARKER, "blocked_548", "chemical_582", "lot_631", "cab_209", run["run_id"], run["version_id"]):
            assert secret not in body_text
        assert client.get(f"/api/runs/{run['run_id']}/export").json() == before


def test_private_http_live_jev_is_blocked_before_sdk_or_any_outbound_request(app_factory, monkeypatch):
    with TestClient(app_factory(seed_demo=False)) as client:
        headers, _ = activated_local(client)
        monkeypatch.setenv("TYPESAFE_API_KEY", "fixture-key-only")
        original_import = builtins.__import__
        def sdk_sentinel(name, *args, **kwargs):
            if name == "typesafe_sdk" or name.startswith("typesafe_sdk."):
                pytest.fail("Private ledger must be blocked before importing or calling the external SDK")
            return original_import(name, *args, **kwargs)
        monkeypatch.setattr(builtins, "__import__", sdk_sentinel)
        response = client.post("/api/evidence/jev", headers=headers, json={"query": "staff_947", "live": True, "limit": 4})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["code"] == "source_not_allowed" and result["request_count"] == 0 and result["fallback"] is True
        assert result["candidates"]


def test_nexent_unconfigured_is_503_and_connected_status_tracks_observed_state(app_factory, monkeypatch):
    with TestClient(app_factory(seed_demo=False)) as client:
        headers = local_headers(client)
        run = client.post("/api/check", headers=headers, json=check_request()).json()
        assert client.get("/api/integrations/nexent").json()["connected"] is False
        assert client.post(f"/api/runs/{run['run_id']}/orchestrate", headers=headers).status_code == 503
    from ontolens.nexent_runtime import NexentRuntime
    class PlatformStub:
        calls = 0
        async def status(self):
            self.calls += 1
            return {"connected": self.calls == 1, "model_ready": self.calls == 1,
                    "observed_at": "TEST observation " + str(self.calls)}
    platform = PlatformStub()
    monkeypatch.setenv("PEIWU_NEXENT_BASE_URL", "https://fixture-platform.invalid")
    monkeypatch.setattr(NexentRuntime, "from_environment", classmethod(lambda cls, root: platform))
    with TestClient(app_factory(seed_demo=False)) as client:
        assert client.get("/api/status").json()["nexent_connected"] is False
        first = client.get("/api/integrations/nexent").json()
        assert first["connected"] and client.get("/api/status").json()["nexent_connected"]
        second = client.get("/api/integrations/nexent").json()
        assert not second["connected"] and not client.get("/api/status").json()["nexent_connected"]
        assert first["observed_at"] != second["observed_at"]

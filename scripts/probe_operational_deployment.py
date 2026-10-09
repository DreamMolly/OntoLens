"""Isolated Docker acceptance using invented TEST FIXTURE records and accounts.

Requires a built app image and the prepared Nexent network. Creates
only its own Compose project and volume; account passwords stay in memory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from peiwu.access import update_account
from peiwu.export_verification import verify_evidence_export
from peiwu.nexent_runtime import upstream_error_text


ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def require(condition, code):
    if not condition:
        raise ValueError(code)


def facts():
    return {
        "people": {
            "TEST_PERSON": {"role": "teacher", "banned": False, "classes": ["FLAMMABLE"],
                            "authorization_basis": "TEST FIXTURE authorization, no actual person",
                            "valid_from": "2026-01-01", "valid_until": "2026-12-31"},
            "TEST_BLOCKED": {"role": "teacher", "banned": True, "classes": ["FLAMMABLE"],
                             "authorization_basis": "TEST FIXTURE suspended authorization",
                             "valid_from": "2026-01-01", "valid_until": "2026-12-31"}},
        "chemicals": {"TEST_MATERIAL": {"hazard_class": "FLAMMABLE", "per_issue_limit": 40, "unit": "mL"}},
        "lots": {"TEST_BATCH": {"chemical_id": "TEST_MATERIAL", "on_hand": 250, "status": "available"},
                 "TEST_DAMAGED": {"chemical_id": "TEST_MATERIAL", "on_hand": 30, "status": "damaged"}},
        "cabinets": {"TEST_STORAGE": {"allowed_classes": ["FLAMMABLE"]}},
        "issues": {"TEST_PERSON": [], "TEST_BLOCKED": []},
        "rules": {"version": "TEST-POLICY-1", "student_fraction": 0.5, "session_incompatibility": True,
                  "deny_students": False, "incompatible_pairs": [["FLAMMABLE", "OXIDIZER"]]},
    }


def probe(*, keep_running=False, image="ontolens:0.4.0", port=18768) -> dict:
    require(bool(re.fullmatch(r"[a-z0-9][a-z0-9._:/@-]+", image)), "invalid_image")
    require(1024 <= port <= 65535, "invalid_port")
    base_url = "http://127.0.0.1:" + str(port)
    identifier = "ontolens-qa-" + secrets.token_hex(5)
    runtime = ROOT / ".runtime/isolateddockerqa" / identifier
    runtime.mkdir(parents=True)
    accounts = runtime / "accounts.json"
    passwords = {}
    for role in ("admin", "operator", "reviewer", "viewer"):
        passwords[role] = secrets.token_urlsafe(24)
        update_account(accounts, role, name="TEST FIXTURE " + role, role=role,
                       password=passwords[role], create=True)
    override = runtime / "compose.qa.yaml"
    override.write_text(
        "services:\n  ontolens:\n    image: " + image + "\n    ports: !override\n      - '127.0.0.1:" + str(port) + ":8768'\n"
        "    volumes: !override\n      - qa-state:/state\n      - "
        + json.dumps(runtime.as_posix() + ":/config:ro") + "\n"
        "    environment:\n      PEIWU_NEXENT_BASE_URL: http://nexent-web:3000\n"
        "      PEIWU_NEXENT_AGENT_NAME: ontolens_result_explainer\n"
        "      PEIWU_NEXENT_AGENT_ID: '2'\n    restart: 'no'\n"
        "volumes:\n  qa-state:\n    name: " + identifier + "-state\n", encoding="utf-8")
    compose = ["docker", "compose", "--project-name", identifier,
               "-f", str(ROOT / "deploy/compose.yaml"), "-f", str(ROOT / "deploy/compose.nexent.yaml"),
               "-f", str(override)]
    report = {"format": "ontolens-operational-deployment-1", "status": "failed", "started_at": now(),
              "scope": "Actual new Docker app deployment and HTTP workflow using invented TEST FIXTURE private records; not real industry evaluation.",
              "project": identifier, "port": port, "image_tag": image, "volume": identifier + "-state", "checks": {},
              "real_industry_data_used": False, "nexent": None}
    report["source_sha256"] = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                               for tree in (ROOT / "src", ROOT / "data")
                               for path in sorted(tree.rglob("*"))
                               if path.is_file() and "__pycache__" not in path.parts
                               and not any(part.endswith(".egg-info") for part in path.parts)}
    for name in ("Dockerfile", ".dockerignore", "pyproject.toml", "README.md"):
        report["source_sha256"][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    clients = []
    created = False
    phase = "compose_start"
    try:
        result = subprocess.run(compose + ["up", "-d", "--no-build"], capture_output=True, text=True, timeout=180)
        (runtime / "compose.log").write_text(result.stderr, encoding="utf-8")
        require(result.returncode == 0, "compose_start_failed")
        created = True
        phase = "health"
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            try:
                with httpx.Client(base_url=base_url, trust_env=False, timeout=4) as anonymous:
                    response = anonymous.get("/api/auth/session")
                    if response.status_code == 200:
                        require(response.json()["enabled"] and not response.json()["authenticated"], "account_auth_required")
                        require(anonymous.get("/api/status").status_code == 401, "unauthorized_status_not_blocked")
                        require(anonymous.get("/api/documents").status_code == 401, "unauthorized_documents_not_blocked")
                        report["checks"]["unauthenticated_reads_denied"] = True
                        break
            except httpx.HTTPError:
                pass
            time.sleep(2)
        else:
            raise ValueError("app_health_timeout")
        phase = "login"
        logged = {}
        for role, password in passwords.items():
            client = httpx.Client(base_url=base_url, trust_env=False, timeout=180)
            clients.append(client)
            response = client.post("/api/auth/login", json={"username": role, "password": password})
            require(response.status_code == 200 and response.json()["actor"]["role"] == role, "login_failed")
            client.headers["X-Peiwu-Token"] = response.json()["csrf_token"]
            logged[role] = client
        passwords.clear()
        admin, operator, reviewer, viewer = (logged[r] for r in ("admin", "operator", "reviewer", "viewer"))
        before = admin.get("/api/status").json()
        require(before["mode"] == "operational_empty", "fresh_volume_not_empty")
        require(admin.get("/api/documents").json() == [], "fresh_volume_contains_documents")
        request = {"request_id": "TEST-DEPLOYMENT", "requester_id": "TEST_PERSON", "lot_id": "TEST_BATCH",
                   "destination_cabinet_id": "TEST_STORAGE", "quantity": 20.0, "unit": "mL", "as_of": "2026-10-08"}
        require(viewer.post("/api/check", json=request).status_code == 403, "viewer_write_allowed")
        no_csrf = admin.post("/api/check", json=request, headers={"X-Peiwu-Token": "invalid"})
        require(no_csrf.status_code == 403, "csrf_not_enforced")
        empty = operator.post("/api/check", json=request).json()
        require(empty["status"] == "needs_review" and empty["decision"] is None, "empty_workspace_decided")
        report["checks"].update(fresh_operational_volume=True, four_roles_login=True, viewer_write_denied=True, csrf_enforced=True)
        print("[deployment] Authenticated isolated empty workspace and role guards verified", flush=True)
        phase = "import"
        rows = facts()
        originals = {name: ("\ufeff" + json.dumps(value, ensure_ascii=False, indent=2)).encode("utf-8") for name, value in rows.items()}
        files = {name: (name + ".json", raw, "application/json") for name, raw in originals.items()}
        metadata = {"label": "TEST FIXTURE Docker acceptance", "operator": "forged-untrusted-operator",
                    "basis": "TEST FIXTURE synthetic authorization", "purpose": "isolated deployment verification",
                    "authorized_by": "TEST FIXTURE", "recorded_at": "2026-10-08", "kind": "private",
                    "local_operation_authorized": "true"}
        require(reviewer.post("/api/ledger-bundles", files=files, data=metadata).status_code == 403,
                "reviewer_import_allowed")
        first = operator.post("/api/ledger-bundles", files=files, data=metadata)
        require(first.status_code == 201, "ledger_import_failed")
        second = operator.post("/api/ledger-bundles", files=files, data={**metadata, "label": "TEST FIXTURE stale candidate"})
        require(second.status_code == 201, "second_candidate_failed")
        candidate = first.json()
        preview = admin.get("/api/candidates/" + candidate["id"] + "/preview")
        require(preview.status_code == 200 and preview.json()["structural_validation"]["accepted"], "preview_rejected")
        require(admin.get("/api/status").json()["active_id"] == before["active_id"], "import_auto_published")
        payload = {"expected_active": before["active_id"], "confirm_publish": True, "note": "Publish TEST FIXTURE for isolated QA"}
        path = "/api/candidates/" + candidate["id"] + "/publish"
        require(operator.post(path, json=payload).status_code == 403, "operator_publish_allowed")
        published = admin.post(path, json=payload)
        require(published.status_code == 200, "admin_publish_failed")
        stale = admin.post("/api/candidates/" + second.json()["id"] + "/publish", json=payload)
        require(stale.status_code == 409, "stale_publish_not_rejected")
        report["checks"].update(private_fixture_import=True, preview_before_publish=True,
                                 admin_only_publish=True, compare_and_swap=True, reviewer_import_denied=True)
        print("[deployment] TEST FIXTURE import, preview, publish and stale-version rejection verified", flush=True)
        phase = "decisions_and_exports"
        runs = []
        variants = [("ALLOW", {}), ("DENY", {"requester_id": "TEST_BLOCKED"}),
                    ("LIMIT", {"quantity": 80.0}), ("ISOLATE", {"lot_id": "TEST_DAMAGED"}),
                    (None, {"as_of": "2027-01-01"})]
        for action, changes in variants:
            response = operator.post("/api/check", json={**request, **changes})
            require(response.status_code == 200, "check_failed")
            run = response.json()
            require((run["decision"]["action"] if run["decision"] else None) == action, "unexpected_decision")
            export = admin.get("/api/runs/" + run["run_id"] + "/export").json()
            validation = verify_evidence_export(export)
            require(validation["passed"] and validation["scope"]["decision_reexecuted"], "offline_export_failed")
            expected_hashes = {hashlib.sha256(raw).hexdigest() for raw in originals.values()}
            require(expected_hashes.issubset({source["sha256"] for source in export["sources"]}), "uploaded_bytes_not_preserved")
            name = action or "NEEDS_REVIEW"
            (runtime / ("export-" + name + ".json")).write_text(json.dumps(export, ensure_ascii=False), encoding="utf-8")
            runs.append({"action": action, "run_id": run["run_id"], "export_sha256": hashlib.sha256(
                json.dumps(export, sort_keys=True, ensure_ascii=False).encode()).hexdigest(), "offline_verified": True})
        report["runs"] = runs
        report["checks"].update(four_decisions=True, needs_review=True, detached_exports_reexecuted=True,
                                 original_upload_hashes_preserved=True)
        review = reviewer.post("/api/runs/" + runs[-1]["run_id"] + "/review", json={
            "reviewer": "forged-reviewer", "review_status": "in_review", "note": "TEST FIXTURE reviewer follow-up"})
        require(review.status_code == 201 and review.json()["reviewer"] == "reviewer"
                and review.json()["decision_written"] is False, "review_identity_not_bound")
        events = admin.get("/api/audit").json()
        require(any(e["payload"].get("actor", {}).get("username") == "operator" for e in events), "operator_audit_identity_missing")
        require(any(e["payload"].get("actor", {}).get("username") == "admin" for e in events), "publisher_audit_identity_missing")
        report["checks"].update(session_bound_audit_actors=True, reviewer_followup_cannot_decide=True)
        print("[deployment] Four actions, review path, original bytes and detached replay verified", flush=True)
        phase = "nexent_model"
        status = operator.get("/api/integrations/nexent").json()
        require(status["connected"] and status["tool_free"] and status["agent_id"] == 2, "nexent_not_tool_free")
        run_id = runs[0]["run_id"]
        before_export = operator.get("/api/runs/" + run_id + "/export").json()
        explanation = operator.post("/api/runs/" + run_id + "/orchestrate")
        require(explanation.status_code == 200, "nexent_orchestration_failed")
        summary = explanation.json()
        model_failed = (summary.get("status") != "ready" or not summary.get("text", "").strip()
                        or upstream_error_text(summary.get("text", ""))
                        or "ALLOW" not in summary.get("text", ""))
        if model_failed:
            summary = {**summary, "status": "error", "text": "",
                       "error_code": summary.get("error_code", "invalid_model_explanation")}
        report["nexent"] = summary
        report["checks"]["live_model_explanation"] = not model_failed
        require(summary["source_text_sent"] is False
                and summary["context_scope"] == "decision_summary" and not summary["tool_calls"]
                and summary["memory_retrieval_disabled"] is True
                and not summary["event_counts"].get("tool") and not summary["event_counts"].get("tool_call"), "nexent_boundary_failed")
        require(not any(value in summary["text"] for value in ("TEST_PERSON", "TEST_BATCH", "TEST_STORAGE")), "private_identifiers_in_explanation")
        after_export = operator.get("/api/runs/" + run_id + "/export").json()
        require(before_export["run"]["result"]["decision"] == after_export["run"]["result"]["decision"], "model_changed_decision")
        report["checks"].update(container_nexent_connection=True,
                                 private_text_not_sent=True, model_cannot_change_decision=True)
        phase = "logout_and_container_identity"
        update_account(accounts, "viewer", enabled=False)
        require(viewer.get("/api/status").status_code == 401, "account_file_change_not_effective")
        report["checks"]["account_revocation_without_restart"] = True
        for client in clients:
            if client is viewer:
                continue
            require(client.post("/api/auth/logout").status_code == 200, "logout_failed")
            require(client.get("/api/status").status_code == 401, "logout_session_still_valid")
        cid = subprocess.run(compose + ["ps", "-q", "ontolens"], capture_output=True, text=True, timeout=20, check=True).stdout.strip()
        health_deadline = time.monotonic() + 50
        while True:
            info = subprocess.run(["docker", "inspect", cid, "--format", "{{json .State}}"], capture_output=True,
                                  text=True, timeout=20, check=True)
            state = json.loads(info.stdout)
            if state.get("Health", {}).get("Status") == "healthy" or time.monotonic() >= health_deadline:
                break
            time.sleep(2)
        require(state["Status"] == "running" and state.get("Health", {}).get("Status") == "healthy", "container_not_healthy")
        image = subprocess.run(["docker", "inspect", cid, "--format", "{{.Image}}"], capture_output=True,
                               text=True, timeout=20, check=True).stdout.strip()
        report["container"] = {"id": cid, "image_id": image, "health": "healthy", "state": "running"}
        labels = json.loads(subprocess.run(["docker", "image", "inspect", image, "--format", "{{json .Config.Labels}}"],
                              capture_output=True, text=True, timeout=20, check=True).stdout) or {}
        report["build_provenance"] = {key: labels.get(key) for key in (
            "org.opencontainers.image.base.name", "org.opencontainers.image.base.digest", "org.ontolens.pip-index")}
        identity = subprocess.run(["docker", "inspect", cid, "--format", "{{.Config.User}}"], capture_output=True,
                                  text=True, timeout=20, check=True).stdout.strip()
        require(identity == "ontolens", "non_root_user_missing")
        mounts = json.loads(subprocess.run(["docker", "inspect", cid, "--format", "{{json .Mounts}}"],
                            capture_output=True, text=True, timeout=20, check=True).stdout)
        require(any(m["Destination"] == "/config" and m["RW"] is False for m in mounts), "accounts_mount_not_readonly")
        require(any(m["Destination"] == "/state" and m.get("Name") == identifier + "-state" for m in mounts), "state_not_isolated_volume")
        packages = subprocess.run(["docker", "exec", cid, "python", "-c",
            "import sys,json,importlib.metadata as m; print(json.dumps({'python':sys.version.split()[0], 'packages':{n:m.version(n) for n in ['fastapi','uvicorn','httpx','mcp','typesafe-sdk']}}))"],
            capture_output=True, text=True, timeout=30, check=True)
        report["runtime_versions"] = json.loads(packages.stdout)
        report["checks"].update(non_root_process=True, readonly_accounts=True, independent_named_volume=True)
        report["checks"].update(logout_revokes_session=True, actual_docker_health=True)
        require(not model_failed, "nexent_model_explanation_failed")
        report["status"] = "passed"
    except (ValueError, KeyError, TypeError, httpx.HTTPError, subprocess.SubprocessError, OSError) as error:
        report["error"] = {"phase": phase, "type": type(error).__name__}
        if isinstance(error, ValueError) and str(error).replace("_", "").isalnum():
            report["error"]["code"] = str(error)
    finally:
        for client in clients:
            client.close()
        passwords.clear()
        if created and not keep_running:
            stopped = subprocess.run(compose + ["stop"], capture_output=True, text=True, timeout=60)
            report["isolated_container_stopped"] = stopped.returncode == 0
        report["observed_at"] = now()
        (runtime / "receipt.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def refresh_deployment(path: Path, *, invoke_model: bool, keep_running: bool) -> dict:
    """Replace this probe's own container, checking saved state and final static bytes."""
    report = json.loads(path.read_text(encoding="utf-8"))
    base_url = "http://127.0.0.1:" + str(report["port"])
    identifier = report["project"]
    require(bool(re.fullmatch(r"ontolens-qa-[a-f0-9]{10}", identifier)), "invalid_owned_project")
    require(report["status"] == "passed", "refresh_requires_completed_workflow")
    runtime = ROOT / ".runtime/isolateddockerqa" / identifier
    (runtime / ("receipt-before-refresh-" + secrets.token_hex(4) + ".json")).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    compose = ["docker", "compose", "--project-name", identifier,
               "-f", str(ROOT / "deploy/compose.yaml"), "-f", str(ROOT / "deploy/compose.nexent.yaml"),
               "-f", str(runtime / "compose.qa.yaml")]
    refresh = {"started_at": now(), "status": "failed", "model_request_sent": False}
    try:
        password = secrets.token_urlsafe(24)
        update_account(runtime / "accounts.json", "admin", password=password, enabled=True)
        result = subprocess.run(compose + ["up", "-d", "--no-build", "--force-recreate"],
                                capture_output=True, text=True, timeout=90)
        require(result.returncode == 0, "replacement_container_failed")
        with httpx.Client(base_url=base_url, trust_env=False, timeout=180) as client:
            for _ in range(45):
                try:
                    response = client.get("/api/auth/session", timeout=2)
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise ValueError("replacement_health_timeout")
            login = client.post("/api/auth/login", json={"username": "admin", "password": password})
            require(login.status_code == 200, "replacement_login_failed")
            password = ""
            client.headers["X-Peiwu-Token"] = login.json()["csrf_token"]
            hashes = {}
            for source in sorted((ROOT / "src/peiwu/static").iterdir()):
                if source.suffix in {".html", ".css", ".js"}:
                    response = client.get("/" if source.name == "index.html" else "/static/" + source.name)
                    expected = hashlib.sha256(source.read_bytes()).hexdigest()
                    require(response.status_code == 200 and hashlib.sha256(response.content).hexdigest() == expected,
                            "final_static_content_mismatch")
                    hashes[source.name] = expected
            refresh["static_sha256"] = hashes
            for run in report["runs"]:
                exported = client.get("/api/runs/" + run["run_id"] + "/export").json()
                actual = hashlib.sha256(json.dumps(exported, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                # The review case receives its separate authenticated follow-up
                # after the original export, so compare the four decisions exactly.
                if run["action"] is not None:
                    require(actual == run["export_sha256"], "saved_decision_changed_on_replacement")
                require(verify_evidence_export(exported)["passed"], "saved_export_invalid")
            refresh["state_preserved"] = True
            if invoke_model:
                response = client.post("/api/runs/" + report["runs"][0]["run_id"] + "/orchestrate")
                require(response.status_code == 200, "replacement_model_failed")
                summary = response.json()
                require(summary.get("status") == "ready" and bool(summary.get("text", "").strip())
                        and not upstream_error_text(summary["text"]) and "ALLOW" in summary["text"],
                        "replacement_model_failed")
                require(summary["memory_retrieval_disabled"] is True and not summary["tool_calls"]
                        and not summary["event_counts"].get("tool") and not summary["event_counts"].get("tool_call"),
                        "replacement_memory_or_tool_event")
                require(not any(term in summary["text"] for term in ("该数据不是合成数据", "该数据为真实数据", "TEST_PERSON", "TEST_BATCH")),
                        "unverified_data_authenticity_claim")
                report["nexent"] = summary
                refresh["model_request_sent"] = True
            require(client.post("/api/auth/logout").status_code == 200, "replacement_logout_failed")
        cid = subprocess.run(compose + ["ps", "-q", "ontolens"], capture_output=True, text=True,
                             timeout=20, check=True).stdout.strip()
        deadline = time.monotonic() + 50
        while True:
            state = json.loads(subprocess.run(["docker", "inspect", cid, "--format", "{{json .State}}"],
                                capture_output=True, text=True, timeout=20, check=True).stdout)
            if state.get("Health", {}).get("Status") == "healthy" or time.monotonic() > deadline:
                break
            time.sleep(2)
        require(state["Status"] == "running" and state.get("Health", {}).get("Status") == "healthy", "replacement_not_healthy")
        image = subprocess.run(["docker", "inspect", cid, "--format", "{{.Image}}"], capture_output=True,
                               text=True, timeout=20, check=True).stdout.strip()
        report["container"] = {"id": cid, "image_id": image, "health": "healthy", "state": "running"}
        refresh["status"] = "passed"
    except (ValueError, KeyError, TypeError, OSError, httpx.HTTPError, subprocess.SubprocessError) as error:
        report["status"] = "failed"
        refresh["error_type"] = type(error).__name__
        if isinstance(error, ValueError) and str(error).replace("_", "").isalnum():
            refresh["error_code"] = str(error)
    finally:
        if not keep_running:
            stopped = subprocess.run(compose + ["stop"], capture_output=True, text=True, timeout=60)
            report["isolated_container_stopped"] = stopped.returncode == 0
        refresh["observed_at"] = now()
        report.setdefault("refreshes", []).append(refresh)
        report["observed_at"] = now()
        (runtime / "receipt-final.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-running", action="store_true")
    parser.add_argument("--refresh-existing", action="store_true")
    parser.add_argument("--refresh-model", action="store_true")
    parser.add_argument("--image", default="ontolens:0.4.0")
    parser.add_argument("--port", type=int, default=18768)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/operational-deployment-20261008.json")
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.parent == ROOT / "artifacts" and output.name.startswith("operational-deployment-")
            and output.suffix == ".json", "invalid_output_path")
    report = (refresh_deployment(output, invoke_model=args.refresh_model, keep_running=args.keep_running)
              if args.refresh_existing else probe(keep_running=args.keep_running, image=args.image, port=args.port))
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "observed_at": report["observed_at"], "error": report.get("error")}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Exercise review HTTP endpoints in an isolated synthetic database and verify the export."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from peiwu.web import create_app


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    destination = ROOT / "artifacts"
    destination.mkdir(exist_ok=True)
    temp_root = ROOT / ".runtime" / "review-acceptance"
    temp_root.mkdir(parents=True, exist_ok=True)
    bundle_path = destination / "human-review-evidence-export.json"
    report_path = destination / "human-review-export-verification.json"
    checks = {}
    with TemporaryDirectory(prefix="run-", dir=temp_root) as temp:
        database = Path(temp) / "isolated.sqlite3"
        app = create_app(ROOT, database, seed_demo=True)
        with TestClient(app) as client:
            client.headers["X-Peiwu-Token"] = client.get("/api/status").json()["csrf_token"]
            response = client.post("/api/check", json={
                "request_id": "SYNTHETIC-REVIEW-ACCEPTANCE", "requester_id": "unknown_demo_person",
                "lot_id": "lot_eth", "destination_cabinet_id": "cab_flam", "quantity": 100,
                "unit": "mL", "as_of": "2026-09-28",
            })
            response.raise_for_status()
            run = response.json()
            before = app.state.workspace.run(run["run_id"])
            chosen = [next(edge for edge in run["evidence"] if edge["quote"] is not None),
                      next(edge for edge in run["evidence"] if edge["quote"] is None)]
            references = [{key: edge[key] for key in ("source_id", "locator", "sha256", "quote")} |
                          {"unresolved": edge.get("unresolved", False)} for edge in chosen]
            response = client.post(f"/api/runs/{run['run_id']}/review", json={
                "reviewer": "合成演示操作人", "review_status": "evidence_requested",
                "note": "合成验收：核对批次原文，记录人员授权缺失，等待补件。",
                "evidence_references": references,
            })
            response.raise_for_status()
            receipt = response.json()
            export = client.get(f"/api/runs/{run['run_id']}/export")
            export.raise_for_status()
            bundle_path.write_bytes(export.content)
            bundle = export.json()
            stored = bundle["run"]["result"]
            checks["http_created_review"] = response.status_code == 201
            checks["http_exported_package"] = export.status_code == 200
            checks["selected_references_only"] = receipt["evidence_references"] == references
            checks["receipt_persisted"] = stored["review_records"] == [receipt]
            checks["original_decision_unchanged"] = (
                {key: value for key, value in stored.items() if key != "review_records"}
                == {key: value for key, value in before["result"].items() if key != "review_records"}
                and stored["status"] == "needs_review" and stored["decision"] is None)
        # The checker runs in a different process with a different working
        # directory. It only receives the JSON, never a database connection.
        package_hash = sha256(bundle_path)
        command = [sys.executable, str(ROOT / "scripts/verify_evidence_export.py"), str(bundle_path)]
        process = subprocess.run(command, cwd=temp, capture_output=True, text=True, timeout=30)
        verification = json.loads(process.stdout)
        report_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        checks["detached_verifier_passed"] = process.returncode == 0 and verification["passed"]
        checks["package_unchanged"] = package_hash == sha256(bundle_path)
        controls = {}
        for name in ("removed_references", "injected_decision"):
            tampered = copy.deepcopy(bundle)
            record = tampered["run"]["result"]["review_records"][0]
            if name == "removed_references":
                record.pop("evidence_references")
            else:
                record["decision"] = {"action": "ALLOW"}
            path = Path(temp) / (name + ".json")
            path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(command[:-1] + [str(path)], cwd=temp, capture_output=True, text=True, timeout=30)
            checked = json.loads(result.stdout)
            controls[name] = {"exit_code": result.returncode, "passed": checked["passed"],
                              "issue_codes": [item["code"] for item in checked["issues"]]}
            checks[name + "_rejected"] = result.returncode == 1 and checked["passed"] is False
    inputs = ["scripts/verify_review_workflow.py", "scripts/verify_evidence_export.py",
              "src/peiwu/review_verification.py", "src/peiwu/export_verification.py", "src/peiwu/workspace.py",
              "src/peiwu/contracts.py", "src/peiwu/web.py", "data/catalog.yaml", "data/rules/v2.yaml"]
    report = {"schema_version": "peiwu-review-acceptance-1", "generated_at": datetime.now(timezone.utc).isoformat(),
              "scope": "isolated synthetic HTTP workflow plus detached verifier; no operator authentication or professional review",
              "external_request_sent": False, "production_database_used": False,
              "checks": checks, "passed": all(checks.values()), "negative_controls": controls,
              "package_path": bundle_path.relative_to(ROOT).as_posix(), "package_sha256": package_hash,
              "verification_path": report_path.relative_to(ROOT).as_posix(), "verification_sha256": sha256(report_path),
              "run_id": run["run_id"], "review_id": receipt["id"],
              "input_manifest": {path: sha256(ROOT / path) for path in inputs}}
    path = destination / "human-review-acceptance.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": checks, "report": str(path)}, ensure_ascii=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

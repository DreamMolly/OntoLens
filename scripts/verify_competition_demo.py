"""Reproduce the competition demo against an isolated synthetic workbench."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp

from fastapi.testclient import TestClient

from ontolens.config import CONFIG_PREFIXES
from ontolens.web import create_app


ROOT = Path(__file__).resolve().parents[1]
INITIAL = "demo-initial"
REQUEST = {"request_id": "ICT-REVIEW-DEMO", "requester_id": "stu01", "lot_id": "lot_eth",
           "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL", "as_of": "2026-09-23"}


def payload(response):
    response.raise_for_status()
    return response.json()


def run_demo(client: TestClient, output: Path) -> dict:
    status = payload(client.get("/api/status"))
    if status["mode"] != "synthetic_demo" or status["active_id"] != INITIAL:
        raise RuntimeError("The rehearsal requires a fresh synthetic workspace")
    client.headers["X-OntoLens-Token"] = status["csrf_token"]
    before = payload(client.post("/api/check", json=REQUEST))
    document = payload(client.post("/api/documents", data={"kind": "synthetic"}, files={
        "file": ("review-demo-policy.md", "# 合成授权调整\nstu01 授权仅保留 ACID。\n".encode(), "text/plain"),
    }))
    candidate = payload(client.post("/api/candidates", json={
        "parent_id": INITIAL, "requester_id": "stu01", "classes": ["ACID"],
        "source_id": document["id"], "locator": "L2", "note": "ICT 合成演练",
    }))
    candidate_url = f"/api/candidates/{candidate['id']}"
    preview = payload(client.get(candidate_url + "/preview"))
    changes = preview["changes"]
    if len(changes) != 1 or changes[0]["after"]["decision"]["reason_code"] != "CLASS_NOT_AUTHORIZED":
        raise RuntimeError("Preview did not identify the expected authorization impact")
    version = payload(client.post(candidate_url + "/publish", json={
        "expected_active": INITIAL, "note": "确认合成演练", "confirm_demo": True,
    }))
    after = payload(client.post("/api/check", json=REQUEST))
    payload(client.post(f"/api/versions/{INITIAL}/rollback", json={
        "expected_active": version["id"], "note": "恢复合成旧版本", "confirm_demo": True,
    }))
    restored = payload(client.post("/api/check", json=REQUEST))
    runs = [{"run_id": run["run_id"], "action": run["decision"]["action"],
             "version_id": run["version_id"], "snapshot_hash": run["snapshot_hash"]}
            for run in (before, after, restored)]
    expected = [("ALLOW", INITIAL), ("DENY", version["id"]), ("ALLOW", INITIAL)]
    if [(run["action"], run["version_id"]) for run in runs] != expected:
        raise RuntimeError("Decisions or snapshot versions did not match the rehearsal")

    exports = {}
    for phase, run in (("before", before), ("after", after)):
        response = client.get(f"/api/runs/{run['run_id']}/export")
        response.raise_for_status()
        bundle = output / f"{phase}.json"
        bundle.write_bytes(response.content)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_evidence_export.py"), str(bundle)],
            cwd=output, capture_output=True, check=True, timeout=30,
        )
        verification = output / f"{phase}-verification.json"
        verification.write_bytes(result.stdout)
        if not json.loads(result.stdout)["passed"]:
            raise RuntimeError(f"Offline verification failed for {phase}")
        exports[phase] = {"bundle": bundle.name, "verification": verification.name,
                          "sha256": hashlib.sha256(response.content).hexdigest()}
    return {"schema": "ontolens-competition-demo-1", "passed": True, "scope": "synthetic_demo",
            "observed_at": datetime.now(timezone.utc).isoformat(), "request": REQUEST,
            "runs": runs, "exports": exports, "external_request_sent": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".runtime/competition-demo",
                        help="Parent directory for the new rehearsal output")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = Path(mkdtemp(prefix="run-", dir=args.output_dir.resolve()))

    # This CLI always uses disposable fixtures, even on a configured business host.
    for name in tuple(os.environ):
        if name.startswith(CONFIG_PREFIXES):
            del os.environ[name]
    os.environ.update(ONTOLENS_LOAD_ENV="false", ONTOLENS_WORKSPACE_MODE="synthetic")
    with TemporaryDirectory(prefix="db-", dir=output) as temporary:
        app = create_app(ROOT, Path(temporary) / "demo.sqlite3", seed_demo=True)
        with TestClient(app) as client:
            report = run_demo(client, output)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Namespace migration preserves identity, access controls and installed entrypoints."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from fastapi.testclient import TestClient
import httpx
import pytest

from ontolens.config import env_value, load_environment
from ontolens.nexent_runtime import NexentRuntime
from ontolens.web import create_app


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("first,second", [("ontolens", "peiwu"), ("peiwu", "ontolens")])
def test_legacy_imports_share_module_classes_and_audit_context(first, second):
    program = f"""
from importlib import import_module
import sys
left = import_module({first!r})
right = import_module({second!r})
assert left is right and left.__name__ == 'ontolens'
for name in ('workspace', 'web', 'contracts', 'audit_context'):
    old = import_module('peiwu.' + name)
    new = import_module('ontolens.' + name)
    assert old is new and old.__spec__.name == 'ontolens.' + name
assert sys.modules['peiwu.workspace'].Workspace is sys.modules['ontolens.workspace'].Workspace
assert sys.modules['peiwu.audit_context'].audit_actor is sys.modules['ontolens.audit_context'].audit_actor
"""
    result = subprocess.run([sys.executable, "-c", program], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_environment_alias_precedence_preserves_explicit_disable(monkeypatch):
    monkeypatch.setenv("PEIWU_MODEL_NAME", "legacy-fixture")
    assert env_value("MODEL_NAME") == "legacy-fixture"
    monkeypatch.setenv("ONTOLENS_MODEL_NAME", "primary-fixture")
    assert env_value("MODEL_NAME") == "primary-fixture"
    monkeypatch.setenv("ONTOLENS_MODEL_NAME", "")
    assert env_value("MODEL_NAME", "fallback") == ""


def test_dotenv_supports_both_aliases_and_respects_process_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOLENS_LOAD_ENV", "true")
    path = tmp_path / ".env"
    path.write_text('ONTOLENS_MODEL_NAME="primary-file"\nPEIWU_MODEL_NAME=legacy-file\n'
                    'ONTOLENS_MODEL_API_KEY=file-key\nPEIWU_MCP_TOKEN=legacy-file-token\n', encoding="utf-8")
    monkeypatch.setenv("PEIWU_MODEL_API_KEY", "process-fixture-key")
    load_environment(path)
    assert env_value("MODEL_NAME") == "primary-file"
    assert env_value("MODEL_API_KEY") == "process-fixture-key"
    assert "ONTOLENS_MODEL_API_KEY" not in os.environ
    assert env_value("MCP_TOKEN") == "legacy-file-token"
    monkeypatch.setenv("ONTOLENS_LOAD_ENV", "false")
    monkeypatch.delenv("ONTOLENS_MODEL_NAME")
    monkeypatch.delenv("PEIWU_MODEL_NAME")
    load_environment(path)
    assert env_value("MODEL_NAME") is None


def test_nexent_config_supports_dotenv_aliases_and_process_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOLENS_LOAD_ENV", "true")
    (tmp_path / ".env").write_text("ONTOLENS_NEXENT_BASE_URL=http://127.0.0.1:3100\n"
                                    "PEIWU_NEXENT_BASE_URL=http://127.0.0.1:3200\n"
                                    "ONTOLENS_NEXENT_AGENT_ID=2\n"
                                    "ONTOLENS_NEXENT_API_TOKEN=primary-fixture-token\n", encoding="utf-8")
    runtime = NexentRuntime.from_environment(tmp_path)
    assert runtime.base_url == "http://127.0.0.1:3100" and runtime.agent_id == 2
    assert runtime._token == "primary-fixture-token"
    monkeypatch.setenv("PEIWU_NEXENT_BASE_URL", "http://127.0.0.1:3300")
    assert NexentRuntime.from_environment(tmp_path).base_url == "http://127.0.0.1:3300"
    monkeypatch.setenv("ONTOLENS_NEXENT_BASE_URL", "http://127.0.0.1:3400")
    assert NexentRuntime.from_environment(tmp_path).base_url == "http://127.0.0.1:3400"


def test_workbench_uses_primary_database_and_accepts_both_csrf_headers(tmp_path, monkeypatch):
    primary, legacy = tmp_path / "primary.sqlite3", tmp_path / "legacy.sqlite3"
    monkeypatch.setenv("ONTOLENS_ROOT", str(ROOT))
    monkeypatch.setenv("ONTOLENS_DB", str(primary))
    monkeypatch.setenv("PEIWU_DB", str(legacy))
    monkeypatch.setenv("ONTOLENS_WORKSPACE_MODE", "synthetic")
    monkeypatch.setenv("PEIWU_WORKSPACE_MODE", "operational")
    monkeypatch.setenv("PEIWU_MODEL_BASE_URL", "https://fixture.invalid")
    monkeypatch.setenv("PEIWU_MODEL_NAME", "legacy-fixture")
    monkeypatch.setenv("ONTOLENS_MODEL_BASE_URL", "")
    with TestClient(create_app()) as client:
        status = client.get("/api/status").json()
        assert not status["model_configured"]
        token = status["csrf_token"]
        request = {"request_id": "NAMESPACE-FIXTURE", "requester_id": "stu01", "lot_id": "lot_eth",
                   "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL", "as_of": "2026-09-23"}
        for header in ("X-OntoLens-Token", "X-Peiwu-Token"):
            assert client.post("/api/check", json=request, headers={header: token}).status_code == 200
        assert client.post("/api/check", json=request,
                           headers={"X-OntoLens-Token": "", "X-Peiwu-Token": token}).status_code == 403
        assert client.get("/").status_code == 200
        assert "X-OntoLens-Token" in client.get("/static/app.js").text
    assert primary.is_file() and not legacy.exists()


def test_both_module_entrypoints_use_ontolens_cli():
    for package in ("ontolens", "peiwu"):
        result = subprocess.run([sys.executable, "-m", package, "--help"], cwd=ROOT,
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == 0 and result.stdout.startswith("usage: ontolens ")


def test_primary_uvicorn_entrypoint_starts_isolated_business_workspace(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    database = tmp_path / "startup.sqlite3"
    environment = dict(os.environ, ONTOLENS_ROOT=str(ROOT), ONTOLENS_DB=str(database),
                       ONTOLENS_WORKSPACE_MODE="operational", ONTOLENS_LOAD_ENV="false")
    with (tmp_path / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "ontolens.web:create_app", "--factory",
                                   "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=environment,
                                  stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=1) as client:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    try:
                        response = client.get("/api/status")
                        if response.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    assert server.poll() is None
                    time.sleep(0.1)
                else:
                    pytest.fail("Isolated OntoLens startup did not become ready")
                assert response.json()["mode"] == "operational_empty"
                assert client.get("/").status_code == 200
                assert client.get("/static/app.js").status_code == 200
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
    assert database.is_file()

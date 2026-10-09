"""Application configuration, access controls and installed entrypoints."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from fastapi.testclient import TestClient
import httpx
import pytest

from ontolens.config import env_value, load_environment, read_environment
from ontolens.nexent_runtime import NexentRuntime
from ontolens.web import create_app


ROOT = Path(__file__).resolve().parents[1]


def test_imports_use_one_application_package():
    program = """
from importlib import import_module
from pathlib import Path
import sys
package = import_module('ontolens')
for name in ('workspace', 'web', 'contracts', 'audit_context'):
    module = import_module('ontolens.' + name)
    assert module.__spec__.name == 'ontolens.' + name
    assert Path(module.__file__).parent == Path(package.__file__).parent
    assert import_module('ontolens.' + name) is module
assert sys.modules['ontolens.workspace'].Workspace.__module__ == 'ontolens.workspace'
"""
    result = subprocess.run([sys.executable, "-c", program], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_configuration_requires_application_prefix_and_preserves_explicit_disable():
    settings = {"MODEL_NAME": "unprefixed-fixture"}
    assert env_value("MODEL_NAME", "default", environment=settings) == "default"
    settings["ONTOLENS_MODEL_NAME"] = "configured-fixture"
    assert env_value("MODEL_NAME", environment=settings) == "configured-fixture"
    settings["ONTOLENS_MODEL_NAME"] = ""
    assert env_value("MODEL_NAME", "default", environment=settings) == ""


def test_dotenv_respects_process_configuration_and_loading_disable(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOLENS_LOAD_ENV", "true")
    path = tmp_path / ".env"
    path.write_text('ONTOLENS_MODEL_NAME="file-model"\nONTOLENS_MODEL_API_KEY=file-key\n'
                    'ONTOLENS_MCP_TOKEN=file-token\n', encoding="utf-8")
    monkeypatch.setenv("ONTOLENS_MODEL_API_KEY", "process-fixture-key")
    load_environment(path)
    assert env_value("MODEL_NAME") == "file-model"
    assert env_value("MODEL_API_KEY") == "process-fixture-key"
    assert env_value("MCP_TOKEN") == "file-token"
    monkeypatch.setenv("ONTOLENS_LOAD_ENV", "false")
    monkeypatch.delenv("ONTOLENS_MODEL_NAME")
    load_environment(path)
    assert env_value("MODEL_NAME") is None


def test_dotenv_cannot_override_explicitly_empty_process_setting(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOLENS_LOAD_ENV", "true")
    monkeypatch.setenv("ONTOLENS_MODEL_BASE_URL", "")
    path = tmp_path / ".env"
    path.write_text("ONTOLENS_MODEL_BASE_URL=https://fixture.invalid/v1\n", encoding="utf-8")
    load_environment(path)
    assert env_value("MODEL_BASE_URL") == ""


def test_dotenv_reads_allowlisted_settings_and_handles_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOLENS_LOAD_ENV", "true")
    path = tmp_path / ".env"
    assert read_environment(path) == {}
    path.write_text('\ufeff# Application settings\nUNRELATED_SECRET=ignored\nMODEL_NAME=ignored\n'
                    'ONTOLENS_MODEL_NAME="fixture-model"\nTYPESAFE_MODEL=Jev\n', encoding="utf-8")
    assert read_environment(path) == {"ONTOLENS_MODEL_NAME": "fixture-model", "TYPESAFE_MODEL": "Jev"}


def test_nexent_config_reads_dotenv_and_respects_process_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOLENS_LOAD_ENV", "true")
    (tmp_path / ".env").write_text("ONTOLENS_NEXENT_BASE_URL=http://127.0.0.1:3100\n"
                                    "ONTOLENS_NEXENT_AGENT_ID=2\n"
                                    "ONTOLENS_NEXENT_API_TOKEN=fixture-token\n", encoding="utf-8")
    runtime = NexentRuntime.from_environment(tmp_path)
    assert runtime.base_url == "http://127.0.0.1:3100" and runtime.agent_id == 2
    assert runtime._token == "fixture-token"
    monkeypatch.setenv("ONTOLENS_NEXENT_BASE_URL", "http://127.0.0.1:3400")
    assert NexentRuntime.from_environment(tmp_path).base_url == "http://127.0.0.1:3400"


def test_workbench_uses_configured_database_and_requires_csrf_token(tmp_path, monkeypatch):
    database = tmp_path / "configured.sqlite3"
    monkeypatch.setenv("ONTOLENS_ROOT", str(ROOT))
    monkeypatch.setenv("ONTOLENS_DB", str(database))
    monkeypatch.setenv("ONTOLENS_WORKSPACE_MODE", "synthetic")
    monkeypatch.setenv("ONTOLENS_MODEL_BASE_URL", "")
    with TestClient(create_app()) as client:
        status = client.get("/api/status").json()
        assert not status["model_configured"]
        token = status["csrf_token"]
        request = {"request_id": "CONFIGURATION-FIXTURE", "requester_id": "stu01", "lot_id": "lot_eth",
                   "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL", "as_of": "2026-09-23"}
        assert client.post("/api/check", json=request, headers={"X-OntoLens-Token": token}).status_code == 200
        assert client.post("/api/check", json=request).status_code == 403
        assert client.post("/api/check", json=request, headers={"X-OntoLens-Token": ""}).status_code == 403
        assert client.post("/api/check", json=request, headers={"X-OntoLens-Token": "invalid"}).status_code == 403
        assert client.get("/").status_code == 200
        assert "X-OntoLens-Token" in client.get("/static/app.js").text
    assert database.is_file()


def test_module_entrypoint_starts_application_cli():
    result = subprocess.run([sys.executable, "-m", "ontolens", "--help"], cwd=ROOT,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0 and result.stdout.startswith("usage: ontolens ")


def test_uvicorn_entrypoint_starts_isolated_business_workspace(tmp_path):
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

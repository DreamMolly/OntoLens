import hashlib
import io
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.build_nexent_package import build_package, save_package


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "nexent"


def test_nexent_agent_template_has_expected_dependency_contract():
    config = json.loads((PACKAGE / "agent.json").read_text(encoding="utf-8"))
    agent = config["agent_info"][str(config["agent_id"])]
    assert agent["name"] == "ontolens_compliance_review"
    assert agent["name"].isidentifier()
    assert not agent.get("model_ids")
    assert not agent.get("model_names")
    assert {tool["name"] for tool in agent["tools"]} == {
        "asset_recognition", "evidence_lookup", "graph_query", "candidate_suggestions",
        "evidence_rerank_jev", "decision_check", "candidate_review",
    }
    assert all(tool["source"] == "mcp" and tool["usage"] == "ontolens-local"
               and tool["params"] == {} for tool in agent["tools"])
    assert set(agent["skill_names"]) == {
        "ontolens-intake", "ontolens-evidence", "ontolens-decision"
    }
    assert "REPLACE_WITH_ONTOLENS_MCP_TOKEN" not in json.dumps(config)
    assert config["mcp_info"][0]["mcp_server_name"] == "ontolens-local"
    assert "合成演示" in agent["description"]
    assert "未补齐" in agent["constraint_prompt"]


def test_package_contains_frontend_readable_nested_skill_zips():
    payload = build_package(PACKAGE)
    assert payload == build_package(PACKAGE)
    with ZipFile(io.BytesIO(payload)) as archive:
        config = json.loads(archive.read("agent.json"))
        skills = config["agent_info"][str(config["agent_id"])]["skill_names"]
        assert set(archive.namelist()) == {"agent.json", *(f"skills/{name}.zip" for name in skills)}
        for name in skills:
            with ZipFile(io.BytesIO(archive.read(f"skills/{name}.zip"))) as skill:
                assert skill.namelist() == ["SKILL.md"]
                assert skill.read("SKILL.md") == (PACKAGE / "skills" / name / "SKILL.md").read_bytes()


@pytest.mark.parametrize("problem", ["wrong_key", "missing_skill", "path_traversal"])
def test_package_rejects_broken_dependencies(tmp_path, problem):
    package = tmp_path / "nexent"
    shutil.copytree(PACKAGE, package)
    config_file = package / "agent.json"
    config = json.loads(config_file.read_text(encoding="utf-8"))
    root_key = str(config["agent_id"])
    if problem == "wrong_key":
        config["agent_info"]["wrong_name"] = config["agent_info"].pop(root_key)
    else:
        config["agent_info"][root_key]["skill_names"] = [
            "missing-skill" if problem == "missing_skill" else "../../private"
        ]
    config_file.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises((ValueError, FileNotFoundError)):
        build_package(package)


def test_repack_preserves_previous_artifact_and_skips_identical_write(tmp_path):
    destination = tmp_path / "agent.zip"
    destination.write_bytes(b"previous package")
    backup_dir = tmp_path / "backups"
    payload = build_package(PACKAGE)
    digest = save_package(destination, payload, backup_dir)
    assert digest == hashlib.sha256(payload).hexdigest()
    backups = list(backup_dir.glob("*.zip"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"previous package"
    modified = destination.stat().st_mtime_ns
    assert save_package(destination, payload, backup_dir) == digest
    assert destination.stat().st_mtime_ns == modified


def test_nexent_skill_bundle_has_boundary_and_all_tools():
    content = "\n".join(
        (path.read_text(encoding="utf-8") for path in (PACKAGE / "skills").rglob("SKILL.md"))
    )
    assert "decision_check" in content
    assert "evidence_lookup" in content
    assert "graph_query" in content
    assert "candidate_review" in content
    assert "candidate_suggestions" in content
    assert "evidence_rerank_jev" in content or "JEV" in content
    assert "asset_recognition" in content
    assert "needs_review" in content
    assert "不提供化学品" in content
    assert "配制" in content or "使用指导" in content


def test_nexent_service_templates_use_local_or_docker_host_without_real_secret():
    local = json.loads((PACKAGE / "mcp-service.local.json").read_text(encoding="utf-8"))
    docker = json.loads((PACKAGE / "mcp-service-docker.json").read_text(encoding="utf-8"))
    assert local["url"] == "http://127.0.0.1:8765/mcp/"
    assert docker["url"].startswith("http://host.docker.internal:")
    assert "REPLACE_WITH_ONTOLENS_MCP_TOKEN" in docker["headers"]["Authorization"]

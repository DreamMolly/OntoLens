import copy
import json

import httpx
import pytest

from scripts.build_nexent_package import build_package
from scripts.import_nexent_agent import ROOT, import_lock, load_bundle, reconcile


@pytest.fixture
def bundle(tmp_path):
    path = tmp_path / "agent.zip"
    path.write_bytes(build_package(ROOT / "nexent"))
    return load_bundle(path)


class Platform:
    def __init__(self, bundle, present=False):
        self.bundle = bundle
        self.present = present
        self.mutations = []
        self.failure = None
        self.skill_conflict = False
        self.agent_conflict = None
        self.duplicate = False
        self.missing_tools = False
        self.ambiguous_tools = False
        self.attached_tools = False
        self.skills = self.expected_skills() if present else []

    def expected_skills(self):
        return [{"skill_id": index + 1, "name": skill["name"], "description": skill["description"],
                 "content": skill["content"]} for index, skill in enumerate(self.bundle["skills"])]

    def handle(self, request):
        path = request.url.path
        agent = self.bundle["agent"]
        if path == "/api/mcp/list":
            service = self.bundle["config"]["mcp_info"][0]
            return httpx.Response(200, json={"remote_mcp_server_list": [{"enabled": True,
                "remote_mcp_server_name": service["mcp_server_name"], "remote_mcp_server": service["mcp_url"],
                "authorization_token": "must-not-appear-in-report"}]})
        if path == "/api/tool/list":
            tools = [] if self.missing_tools else [{**tool, "is_available": True} for tool in agent["tools"]]
            if self.ambiguous_tools:
                tools.append({**tools[0], "usage": "another-mcp"})
            return httpx.Response(200, json=tools)
        if path == "/api/skills":
            skills = copy.deepcopy(self.skills)
            if self.skill_conflict:
                skills[0]["content"] = "unrelated user content"
            if self.attached_tools:
                skills[0]["tool_ids"] = [999]
            return httpx.Response(200, json={"skills": skills})
        if path == "/api/agent/list":
            agents = [{"agent_id": 7, "name": agent["name"], "display_name": agent["display_name"]}] if self.present else []
            return httpx.Response(200, json=agents * 2 if self.duplicate else agents)
        if path == "/api/agent/search_info":
            detail = {**agent, "agent_id": 7, "model_ids": [], "sub_agent_id_list": [],
                      "skills": [{"skill_id": skill["skill_id"], "enabled": True} for skill in self.skills],
                      "tools": [{**tool, "enabled": True, "params": []} for tool in agent["tools"]]}
            if self.agent_conflict == "prompt":
                detail["duty_prompt"] = "custom user prompt"
            elif self.agent_conflict == "model":
                detail["model_ids"] = [42]
            elif self.agent_conflict == "model_name":
                detail["model_names"] = ["team-selected-model"]
            elif self.agent_conflict == "tools":
                detail["tools"][0]["enabled"] = False
            return httpx.Response(200, json=detail)
        if path == "/api/agent/import":
            payload = json.loads(request.content)
            self.mutations.append(payload)
            assert payload["force_import"] is True
            assert not payload["agent_info"]["agent_info"][str(payload["agent_info"]["agent_id"])].get("model_ids")
            if self.failure == "timeout":
                raise httpx.ReadTimeout("simulated response timeout", request=request)
            self.skills = self.expected_skills()
            if self.failure == "partial_skills":
                return httpx.Response(500, json={"message": "simulated partial import"})
            self.present = True
            return httpx.Response(200, json={"agent_id": 7})
        pytest.fail("Unexpected API operation: " + request.method + " " + path)

    def client(self):
        return httpx.Client(base_url="http://localhost/api", transport=httpx.MockTransport(self.handle))


def test_tampered_package_is_not_uploaded(tmp_path):
    path = tmp_path / "agent.zip"
    path.write_bytes(build_package(ROOT / "nexent") + b"untrusted")
    with pytest.raises(ValueError, match="differs"):
        load_bundle(path)


def test_inspection_does_not_import_absent_agent(bundle, tmp_path):
    platform = Platform(bundle)
    with platform.client() as client:
        result = reconcile(client, bundle, apply=False, journal=tmp_path / "journal.json")
    assert result["status"] == "ready_to_import"
    assert platform.mutations == []


def test_serial_apply_creates_once_and_then_reuses(bundle, tmp_path):
    platform = Platform(bundle)
    with platform.client() as client:
        first = reconcile(client, bundle, apply=True, journal=tmp_path / "journal.json")
        second = reconcile(client, bundle, apply=True, journal=tmp_path / "journal.json")
    assert first["status"] == "created"
    assert second["status"] == "already_present"
    assert first["agent_id"] == second["agent_id"] == 7
    assert len(platform.mutations) == 1
    assert "must-not-appear-in-report" not in json.dumps(second)


@pytest.mark.parametrize("change", ["prompt", "model", "model_name", "tools"])
def test_existing_agent_customization_is_not_overwritten(bundle, tmp_path, change):
    platform = Platform(bundle, present=True)
    platform.agent_conflict = change
    with platform.client() as client, pytest.raises(ValueError, match="Existing agent conflict"):
        reconcile(client, bundle, apply=True, journal=tmp_path / "journal.json")
    assert platform.mutations == []


def test_same_named_skill_with_different_content_is_not_reused(bundle, tmp_path):
    platform = Platform(bundle, present=True)
    platform.skill_conflict = True
    with platform.client() as client, pytest.raises(ValueError, match="skill content conflict"):
        reconcile(client, bundle, apply=True, journal=tmp_path / "journal.json")
    assert platform.mutations == []


def test_duplicate_agents_are_not_silently_selected(bundle, tmp_path):
    platform = Platform(bundle, present=True)
    platform.duplicate = True
    with platform.client() as client, pytest.raises(ValueError, match="Duplicate agent"):
        reconcile(client, bundle, apply=True, journal=tmp_path / "journal.json")
    assert platform.mutations == []


def test_missing_registered_tools_prevents_partial_skill_import(bundle, tmp_path):
    platform = Platform(bundle)
    platform.missing_tools = True
    with platform.client() as client, pytest.raises(ValueError, match="registered tools"):
        reconcile(client, bundle, apply=True, journal=tmp_path / "journal.json")
    assert platform.mutations == []


def test_ambiguous_mcp_names_are_rejected_before_server_class_lookup(bundle, tmp_path):
    platform = Platform(bundle)
    platform.ambiguous_tools = True
    with platform.client() as client, pytest.raises(ValueError, match="Ambiguous registered"):
        reconcile(client, bundle, apply=True, journal=tmp_path / "journal.json")
    assert platform.mutations == []


def test_identical_skill_text_cannot_hide_extra_tool_permissions(bundle, tmp_path):
    platform = Platform(bundle, present=True)
    platform.attached_tools = True
    with platform.client() as client, pytest.raises(ValueError, match="unexpected attached tools"):
        reconcile(client, bundle, apply=True, journal=tmp_path / "journal.json")
    assert platform.mutations == []


def test_partial_skill_import_is_reused_after_failure(bundle, tmp_path):
    platform = Platform(bundle)
    platform.failure = "partial_skills"
    journal = tmp_path / "journal.json"
    with platform.client() as client:
        with pytest.raises(httpx.HTTPStatusError):
            reconcile(client, bundle, apply=True, journal=journal)
        platform.failure = None
        result = reconcile(client, bundle, apply=True, journal=journal)
    assert result["status"] == "created"
    assert len(platform.mutations[-1]["skill_resolutions"]) == 3
    assert all(item["action"] == "use_existing" for item in platform.mutations[-1]["skill_resolutions"])


def test_timeout_does_not_trigger_blind_import_retry(bundle, tmp_path):
    platform = Platform(bundle)
    platform.failure = "timeout"
    journal = tmp_path / "journal.json"
    with platform.client() as client:
        with pytest.raises(httpx.ReadTimeout):
            reconcile(client, bundle, apply=True, journal=journal)
        assert json.loads(journal.read_text())["state"] == "pending"
        with pytest.raises(ValueError, match="outcome is unknown"):
            reconcile(client, bundle, apply=True, journal=journal)
    assert len(platform.mutations) == 1


def test_pending_import_is_reconciled_when_agent_is_already_persisted(bundle, tmp_path):
    platform = Platform(bundle, present=True)
    journal = tmp_path / "journal.json"
    journal.write_text(json.dumps({"state": "pending"}), encoding="utf-8")
    with platform.client() as client:
        result = reconcile(client, bundle, apply=True, journal=journal)
    assert result["status"] == "already_present"
    assert result["import_posts"] == 0
    assert json.loads(journal.read_text())["state"] == "reconciled"


def test_parallel_project_import_is_refused(tmp_path):
    path = tmp_path / "import.lock"
    with import_lock(path):
        with pytest.raises(RuntimeError, match="Another project import"):
            with import_lock(path):
                pytest.fail("Concurrent imports must not share the lock")

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import httpx
import yaml

if __package__:
    from .build_nexent_package import build_package
    from .verify_nexent import ROOT, SKILL_NAMES, TOOL_NAMES, local_url, require
else:
    from build_nexent_package import build_package
    from verify_nexent import ROOT, SKILL_NAMES, TOOL_NAMES, local_url, require


@contextmanager
def import_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("Another project import is active; inspect its result first") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_bundle(path: Path, package: Path = ROOT / "nexent") -> dict:
    content = path.read_bytes()
    require(content == build_package(package), "Bundle differs from current source; run nexent/package.ps1 first")
    with ZipFile(io.BytesIO(content)) as archive:
        config = json.loads(archive.read("agent.json"))
        agent = config["agent_info"][str(config["agent_id"])]
        require(len(config["agent_info"]) == 1 and not agent["managed_agents"], "Only the single Peiwu agent is supported")
        require(not agent.get("model_ids") and not agent.get("model_names")
                and not agent.get("business_logic_model_id") and not agent.get("business_logic_model_name"),
                "Starter import must not configure or select a model")
        require({tool["class_name"] for tool in agent["tools"]} == TOOL_NAMES
                and len(agent["tools"]) == len(TOOL_NAMES), "Unexpected starter tools")
        require(set(agent["skill_names"]) == SKILL_NAMES, "Unexpected starter skills")
        skills = []
        for name in sorted(SKILL_NAMES):
            raw = archive.read(f"skills/{name}.zip")
            with ZipFile(io.BytesIO(raw)) as skill_archive:
                text = skill_archive.read("SKILL.md").decode("utf-8").replace("\r\n", "\n")
            header, body = text.removeprefix("---\n").split("\n---\n", 1)
            metadata = yaml.safe_load(header)
            require(metadata["name"] == name, "Skill metadata differs from bundle name")
            skills.append({"name": name, "description": metadata["description"], "content": body.strip(),
                           "skill_zip_base64": base64.b64encode(raw).decode()})
    return {"sha256": hashlib.sha256(content).hexdigest(), "config": config, "agent": agent, "skills": skills}


def request_json(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def agent_conflicts(actual: dict, expected: dict, skills_by_id: dict) -> list[str]:
    fields = ("name", "display_name", "description", "author", "max_steps", "enabled", "is_main_agent",
              "provide_run_summary", "allow_chat_metadata", "duty_prompt", "constraint_prompt", "few_shots_prompt")
    conflicts = [name for name in fields if actual.get(name) != expected.get(name)]
    if (actual.get("model_ids") or actual.get("model_names") or actual.get("business_logic_model_id")
            or actual.get("business_logic_model_name")):
        conflicts.append("model_configuration")
    if actual.get("sub_agent_id_list") or actual.get("external_sub_agent_id_list"):
        conflicts.append("collaborators")
    actual_tools = actual.get("tools", [])
    actual_keys = {(tool["class_name"], tool["source"], tool.get("usage")) for tool in actual_tools}
    expected_keys = {(tool["class_name"], tool["source"], tool.get("usage")) for tool in expected["tools"]}
    if (actual_keys != expected_keys or len(actual_tools) != len(expected_keys)
            or any(tool.get("enabled") is not True or tool.get("params") for tool in actual_tools)):
        conflicts.append("tool_bindings")
    bindings = actual.get("skills", [])
    names = {skills_by_id.get(binding["skill_id"], {}).get("name") for binding in bindings}
    if names != SKILL_NAMES or len(bindings) != len(SKILL_NAMES) or any(binding.get("enabled") is not True for binding in bindings):
        conflicts.append("skill_bindings")
    return conflicts


def inspect_target(client: httpx.Client, bundle: dict) -> dict:
    service_info = bundle["config"]["mcp_info"][0]
    services = request_json(client, "GET", "/mcp/list")["remote_mcp_server_list"]
    services = [item for item in services if item["remote_mcp_server_name"] == service_info["mcp_server_name"]]
    require(len(services) == 1 and services[0].get("enabled") is True, "Prepare exactly one enabled peiwu-local MCP service first")
    require(services[0]["remote_mcp_server"].rstrip("/") == service_info["mcp_url"].rstrip("/"), "MCP URL conflicts with bundle")
    tools = request_json(client, "GET", "/tool/list")
    available = {tool["name"] for tool in tools if tool["source"] == "mcp" and tool.get("usage") == "peiwu-local"
                 and tool.get("is_available") is True}
    require(TOOL_NAMES.issubset(available), "Missing registered tools; use the Nexent tool scan before importing")
    for name in TOOL_NAMES:
        candidates = [tool for tool in tools if tool["source"] == "mcp" and tool["name"] == name]
        require(len(candidates) == 1, "Ambiguous registered MCP tool name: " + name)
    skills = request_json(client, "GET", "/skills")["skills"]
    expected_skills = {skill["name"]: skill for skill in bundle["skills"]}
    matching = {}
    for skill in skills:
        name = skill["name"]
        if name not in expected_skills:
            continue
        require(name not in matching, "Duplicate skill name: " + name)
        wanted = expected_skills[name]
        require(skill.get("description", "").strip() == wanted["description"].strip()
                and skill.get("content", "").replace("\r\n", "\n").strip() == wanted["content"],
                "Existing skill content conflict: " + name)
        require(not skill.get("tool_ids"), "Existing skill has unexpected attached tools: " + name)
        matching[name] = skill
    expected = bundle["agent"]
    agents = request_json(client, "GET", "/agent/list")
    named = [agent for agent in agents if agent["name"] == expected["name"]]
    require(len(named) <= 1, "Duplicate agent name; refusing to select or overwrite one")
    if not named:
        require(not any(agent.get("display_name") == expected["display_name"] for agent in agents), "Agent display name conflict")
        return {"agent_id": None, "matching_skills": matching}
    actual = request_json(client, "POST", "/agent/search_info", json={"agent_id": named[0]["agent_id"]})
    differences = agent_conflicts(actual, expected, {skill["skill_id"]: skill for skill in skills})
    require(not differences, "Existing agent conflict: " + ", ".join(differences))
    return {"agent_id": actual["agent_id"], "matching_skills": matching}


def save_journal(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def reconcile(client: httpx.Client, bundle: dict, *, apply: bool, journal: Path) -> dict:
    state = inspect_target(client, bundle)
    result = {"bundle_sha256": bundle["sha256"], "agent_id": state["agent_id"], "import_posts": 0,
              "skill_names": sorted(state["matching_skills"]), "model_calls": 0, "apply_requested": apply}
    if state["agent_id"] is not None:
        if apply and journal.exists():
            save_journal(journal, {"state": "reconciled", "agent_id": state["agent_id"], "bundle_sha256": bundle["sha256"]})
        return {**result, "status": "already_present", "changed": False}
    if not apply:
        return {**result, "status": "ready_to_import", "changed": False}
    if journal.exists():
        previous = json.loads(journal.read_text(encoding="utf-8"))
        require(previous.get("state") != "pending", "Earlier import outcome is unknown; inspect platform state before retrying")
    payload = {"agent_info": bundle["config"], "force_import": True,
               "skills": [{"skill_name": skill["name"], "skill_zip_base64": skill["skill_zip_base64"]} for skill in bundle["skills"]],
               "skill_resolutions": [{"skill_name": name, "action": "use_existing"} for name in state["matching_skills"]]}
    operation = {"state": "pending", "time": datetime.now(timezone.utc).isoformat(),
                 "origin": str(client.base_url), "bundle_sha256": bundle["sha256"]}
    save_journal(journal, operation)
    response = client.post("/agent/import", json=payload)
    if response.is_error:
        save_journal(journal, {**operation, "state": "http_error", "http_status": response.status_code})
        response.raise_for_status()
    imported = response.json()
    verified = inspect_target(client, bundle)
    require(verified["agent_id"] is not None and verified["agent_id"] == imported["agent_id"], "Import response differs from persisted agent")
    save_journal(journal, {**operation, "state": "verified", "agent_id": verified["agent_id"]})
    return {**result, "status": "created", "changed": True, "agent_id": verified["agent_id"], "import_posts": 1,
            "skill_names": sorted(verified["matching_skills"])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=local_url, default="http://127.0.0.1:3000")
    parser.add_argument("--package", type=Path, default=ROOT / "artifacts/peiwu-nexent-agent.zip")
    parser.add_argument("--apply", action="store_true", help="Import only if absent and dependencies match; never overwrite")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/nexent-import-report.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error("Report must stay inside the project")
    report = {"status": "failed", "time": datetime.now(timezone.utc).isoformat(),
              "scope": "Repository starter import only; not model orchestration or deployment readiness"}
    exit_code = 1
    try:
        bundle = load_bundle(args.package)
        with import_lock(ROOT / ".runtime/nexent-import.lock"), \
                httpx.Client(base_url=args.url + "/api", trust_env=False, timeout=60) as client:
            report.update(reconcile(client, bundle, apply=args.apply, journal=ROOT / ".runtime/nexent-import-journal.json"))
        exit_code = 0
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

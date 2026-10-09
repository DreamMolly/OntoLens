from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx

if __package__:
    from .verify_model_explain import load_local_env
    from .verify_nexent import ROOT, SKILL_NAMES, TOOL_NAMES, local_url, require
else:
    from verify_model_explain import load_local_env
    from verify_nexent import ROOT, SKILL_NAMES, TOOL_NAMES, local_url, require


def model_payload() -> dict:
    name = os.getenv("PEIWU_MODEL_NAME", "").strip()
    base_url = os.getenv("PEIWU_MODEL_BASE_URL", "").strip()
    api_key = os.getenv("PEIWU_MODEL_API_KEY", "").strip()
    require(bool(name and base_url and api_key), "PEIWU model name, base URL and API key are required")
    parsed = urlsplit(base_url)
    require(parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment,
            "Model base URL must not contain embedded credentials, query parameters or fragments")
    return {"model_factory": "OpenAI-API-Compatible", "model_name": name, "model_type": "llm",
            "api_key": api_key, "base_url": base_url, "max_tokens": 0, "used_token": 0,
            "display_name": name, "connect_status": "not_detected"}


def redacted_configuration(payload: dict) -> dict:
    return {"model_factory": payload["model_factory"], "model_name": payload["model_name"],
            "model_type": payload["model_type"], "base_url_present": bool(payload["base_url"]),
            "api_key_present": bool(payload["api_key"])}


def normalized_url(value: str) -> str:
    parsed = urlsplit(value.rstrip("/"))
    hostname = parsed.hostname or ""
    if hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
        hostname = "host.docker.internal"
    host = hostname.lower()
    if parsed.port is not None:
        host += ":" + str(parsed.port)
    return urlunsplit((parsed.scheme.lower(), host, parsed.path.rstrip("/"), "", ""))


def model_matches(actual: dict, expected: dict) -> bool:
    return (actual.get("display_name") == expected["display_name"]
            and actual.get("model_name") == expected["model_name"]
            and actual.get("model_factory") == expected["model_factory"]
            and actual.get("model_type") == expected["model_type"]
            and normalized_url(actual.get("base_url") or "") == normalized_url(expected["base_url"]))


def expected_agent_id() -> int:
    readiness = json.loads((ROOT / "artifacts" / "nexent-model-readiness.json").read_text(encoding="utf-8"))
    agent_id = readiness.get("agent_id")
    require(type(agent_id) is int and agent_id > 0, "Model-readiness evidence has no valid Agent ID")
    return agent_id


def configure(client: httpx.Client, payload: dict, *, apply: bool, state: dict | None = None) -> dict:
    result = state if state is not None else {}
    models_response = client.get("/model/list")
    models_response.raise_for_status()
    models = models_response.json()["data"]
    matching = [item for item in models if item.get("display_name") == payload["display_name"]]
    require(len(matching) <= 1, "Duplicate model display name; refusing to select one")
    if matching:
        require(model_matches(matching[0], payload), "Existing model display name points to another model or endpoint")
    agents_response = client.get("/agent/list")
    agents_response.raise_for_status()
    wanted_agent_id = expected_agent_id()
    agents = [item for item in agents_response.json()
              if item.get("name") == "peiwu_compliance_review" and item.get("agent_id") == wanted_agent_id]
    require(len(agents) == 1, "Expected exactly one Peiwu Agent")
    detail_response = client.post("/agent/search_info", json={"agent_id": wanted_agent_id})
    detail_response.raise_for_status()
    detail = detail_response.json()
    skills_response = client.get("/skills")
    skills_response.raise_for_status()
    skill_names = {item["skill_id"]: item["name"] for item in skills_response.json()["skills"]}
    bound_skills = {skill_names.get(item.get("skill_id")) for item in detail.get("skills", []) if item.get("enabled")}
    bound_tools = {item.get("name") for item in detail.get("tools", []) if item.get("enabled")}
    require(detail.get("permission") == "EDIT" and bound_skills == SKILL_NAMES and bound_tools == TOOL_NAMES,
            "Peiwu Agent is not the editable seven-tool, three-Skill instance")
    previous_model_ids = detail.get("model_ids") or []
    result.update({"applied": False, "model_created": False, "healthcheck_sent": False,
                   "temporary_healthcheck_attempted": False, "model_create_attempted": False,
                   "model_update_attempted": False, "agent_update_attempted": False,
                   "agent_id": wanted_agent_id,
                   "previous_model_ids": previous_model_ids})
    if not apply:
        model_id = matching[0].get("model_id") if matching else None
        if matching and previous_model_ids == [model_id] and agents[0].get("is_available") is True:
            status = "already_configured"
        elif matching:
            status = "ready_to_bind"
        else:
            status = "ready_to_configure"
        result.update({"status": status, "model_id": model_id})
        return result
    result["temporary_healthcheck_attempted"] = True
    probe = client.post("/model/temporary_healthcheck", json=payload)
    probe.raise_for_status()
    probe_data = probe.json().get("data") or {}
    require(probe_data.get("connectivity") is True, "Temporary model connectivity check failed")
    result["temporary_connectivity"] = True
    if not matching:
        result["model_create_attempted"] = True
        created = client.post("/model/create", json=payload)
        created.raise_for_status()
        result["model_created"] = True
        models = client.get("/model/list").json()["data"]
        matching = [item for item in models if item.get("display_name") == payload["display_name"]]
        require(len(matching) == 1 and model_matches(matching[0], payload),
                "Created model was not uniquely visible with the expected endpoint")
    else:
        result["model_update_attempted"] = True
        update_model = client.post("/model/update", params={"display_name": payload["display_name"]},
                                   json={key: payload[key] for key in
                                         ("model_factory", "model_name", "model_type", "api_key", "base_url")})
        update_model.raise_for_status()
        result["model_update_confirmed"] = True
        refreshed_models = client.get("/model/list")
        refreshed_models.raise_for_status()
        matching = [item for item in refreshed_models.json()["data"]
                    if item.get("display_name") == payload["display_name"]]
        require(len(matching) == 1 and model_matches(matching[0], payload),
                "Updated model does not match the expected endpoint")
    model_id = matching[0]["model_id"]
    require(previous_model_ids in ([], [model_id]), "Agent has another model binding; refusing to replace it")
    health = client.post("/model/healthcheck",
                         params={"display_name": payload["display_name"], "model_type": "llm"})
    health.raise_for_status()
    health_data = health.json().get("data") or {}
    require(health_data.get("connectivity") is True, "Persisted model connectivity check failed")
    result["healthcheck_sent"] = True
    if previous_model_ids != [model_id]:
        result["agent_update_attempted"] = True
        update = client.post("/agent/update", json={"agent_id": wanted_agent_id, "model_ids": [model_id]})
        update.raise_for_status()
        result["agent_update_confirmed"] = True
    refreshed_response = client.post("/agent/search_info", json={"agent_id": wanted_agent_id})
    refreshed_response.raise_for_status()
    agent = refreshed_response.json()
    require(agent.get("model_ids") == [model_id] and agent.get("is_available") is True,
            "Agent model binding did not become available")
    result.update({"status": "configured", "applied": True, "model_id": model_id,
                   "connectivity": True, "agent_available": True,
                   "reasoning_capability": matching[0].get("reasoning_capability")})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore the local Nexent model binding without printing credentials")
    parser.add_argument("--url", type=local_url, default="http://127.0.0.1:3000")
    parser.add_argument("--apply", action="store_true", help="Probe, create if absent, health-check and bind the model")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/nexent-model-configuration-report.json")
    args = parser.parse_args()
    output = args.output.resolve()
    artifacts = (ROOT / "artifacts").resolve()
    if (output.parent != artifacts or output.suffix.lower() != ".json"
            or not output.name.startswith("nexent-model-configuration-")):
        parser.error("Report must be a nexent-model-configuration-*.json file directly inside artifacts")
    load_local_env(ROOT / ".env")
    report = {"status": "failed", "time": datetime.now(timezone.utc).isoformat(),
              "scope": "Local Nexent model recovery; credentials are neither printed nor written to the report"}
    exit_code = 1
    try:
        payload = model_payload()
        report["configuration"] = redacted_configuration(payload)
        with httpx.Client(base_url=args.url + "/api", timeout=90, trust_env=False) as client:
            configure(client, payload, apply=args.apply, state=report)
        exit_code = 0
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"configuration"}}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

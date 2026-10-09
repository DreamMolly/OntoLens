from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile

import httpx


ROOT = Path(__file__).resolve().parents[1]
TOOL_NAMES = {"asset_recognition", "evidence_lookup", "graph_query", "candidate_suggestions",
              "evidence_rerank_jev", "decision_check", "candidate_review"}
SKILL_NAMES = {"peiwu-intake", "peiwu-evidence", "peiwu-decision"}


def local_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
        raise argparse.ArgumentTypeError("Only a local HTTP origin is allowed")
    return value.rstrip("/")


def tool_payload(response: httpx.Response) -> dict:
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("Nexent tool response is not a JSON object")
    return payload


def require(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


def load_agent_run_evidence(path: Path | None = None) -> dict | None:
    candidate = path or (ROOT / "artifacts/nexent-agent-run-20260924.json")
    if not candidate.is_file():
        return None
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    require(payload.get("format") == "peiwu-nexent-agent-run-1", "Invalid Agent run evidence format")
    require(payload.get("model_orchestration_verified") is True, "Agent run is not marked verified")
    require(payload.get("final_status") == "ready", "Agent run did not finish ready")
    decision = payload.get("decision") or {}
    require(decision.get("action") in {"ALLOW", "DENY", "LIMIT", "ISOLATE"}, "Agent run action is invalid")
    calls = payload.get("tool_calls") or {}
    require(calls.get("decision_check", 0) >= 1 and calls.get("evidence_lookup", 0) >= 1,
            "Agent run did not prove evidence-to-decision calls")
    evidence = {key: payload.get(key) for key in (
        "agent_id", "model_id", "reasoning_effort", "mode", "final_status", "decision",
        "version_id", "snapshot_hash", "evidence_count", "tool_calls", "notice")}
    evidence["source"] = str(candidate.relative_to(ROOT)) if candidate.is_relative_to(ROOT) else candidate.name
    evidence["artifact_sha256"] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    return evidence


def export_agent_zip(client: httpx.Client, agent_id: int, runner=subprocess.run):
    response = client.post("/agent/export", json={"agent_id": agent_id})
    response.raise_for_status()
    metadata = {"host_http_status": response.status_code, "host_reason": response.reason_phrase,
                "transport": "web_proxy", "interceptor": None}
    if response.status_code != 204:
        require(response.status_code == 200 and bool(response.content), "Empty or unexpected export response")
        return response.content, metadata
    require("IDM Advanced Integration" in response.reason_phrase,
            "Unknown empty export response; refusing to assume IDM interception")
    code = ("const http=require('node:http'); "
            "const request=http.request('http://127.0.0.1:3000/api/agent/export',"
            "{method:'POST',headers:{'Content-Type':'application/json'}},response=>{"
            "const chunks=[];response.on('data',chunk=>chunks.push(chunk));"
            "response.on('end',()=>{if(response.statusCode!==200){process.exitCode=1;return;}"
            "process.stdout.write(Buffer.concat(chunks).toString('base64'));});});"
            "request.on('error',()=>{process.exitCode=1;});"
            "request.setTimeout(30000,()=>request.destroy(new Error('timeout')));"
            f"request.end(JSON.stringify({{agent_id:{int(agent_id)}}}));")
    result = runner(["docker", "exec", "nexent-web", "node", "-e", code],
                    capture_output=True, text=True, timeout=40, check=True)
    content = base64.b64decode(result.stdout.strip(), validate=True)
    require(bool(content), "Container Web export returned no data")
    metadata.update({"transport": "nexent-web_container_loopback", "container_web_http_status": 200,
                     "interceptor": "IDM Advanced Integration"})
    return content, metadata


def container_state() -> list[dict]:
    listing = subprocess.run(["docker", "ps", "-a", "--filter", "label=com.docker.compose.project=nexent",
                              "--format", "{{.ID}}"], capture_output=True, text=True, timeout=20, check=True)
    identifiers = listing.stdout.split()
    if not identifiers:
        return []
    result = subprocess.run(["docker", "inspect", *identifiers], capture_output=True, text=True,
                            timeout=20, check=True)
    return [{"name": item["Name"].lstrip("/"), "image": item["Config"]["Image"],
             "image_id": item["Image"], "status": item["State"]["Status"],
             "health": item["State"].get("Health", {}).get("Status"),
             "mounts": [{"source": mount["Source"], "destination": mount["Destination"],
                         "type": mount["Type"]} for mount in item["Mounts"]]}
            for item in json.loads(result.stdout)]


def verify(platform_url: str, workbench_url: str, report: dict):
    with httpx.Client(base_url=platform_url + "/api", timeout=60, trust_env=False) as nexent, \
            httpx.Client(base_url=workbench_url + "/api", timeout=30, trust_env=False) as workbench:
        status = workbench.get("/status"); status.raise_for_status()
        require(status.json()["mode"] == "synthetic_demo", "Verification requires the synthetic workbench")
        active_before = status.json()["active_id"]
        services = nexent.get("/mcp/list"); services.raise_for_status()
        service = next(item for item in services.json()["remote_mcp_server_list"]
                       if item["remote_mcp_server_name"] == "peiwu-local")
        mcp_id = service["mcp_id"]
        health = nexent.get("/mcp/healthcheck", params={"mcp_id": mcp_id}); health.raise_for_status()
        require(health.json()["data"]["health_status"] == "healthy", "OntoLens legacy MCP service is not healthy")
        tools = nexent.get("/mcp/tools", params={"mcp_id": mcp_id}); tools.raise_for_status()
        require({item["name"] for item in tools.json()["tools"]} == TOOL_NAMES, "Unexpected MCP tool set")
        report["mcp"] = {"id": mcp_id, "health": "healthy", "tools": sorted(TOOL_NAMES)}
        agents = nexent.get("/agent/list"); agents.raise_for_status()
        agent = next(item for item in agents.json() if item["name"] == "peiwu_compliance_review")
        report["agent"] = {key: agent.get(key) for key in
                           ("agent_id", "name", "model_ids", "is_available", "unavailable_reasons")}
        detail = nexent.post("/agent/search_info", json={"agent_id": agent["agent_id"]}); detail.raise_for_status()
        require({item["name"] for item in detail.json()["tools"] if item["enabled"]} == TOOL_NAMES,
                "Agent tool bindings differ from the seven-tool contract")
        skills = nexent.get("/skills"); skills.raise_for_status()
        skill_by_id = {item["skill_id"]: item["name"] for item in skills.json()["skills"]}
        bound = {skill_by_id[item["skill_id"]] for item in detail.json()["skills"] if item["enabled"]}
        require(bound == SKILL_NAMES, "Agent skill bindings are incomplete")
        report["agent"]["skills"] = sorted(bound)
        models = nexent.get("/model/llm_list"); models.raise_for_status()
        report["models"] = [{key: item.get(key) for key in ("model_id", "model_name", "display_name")}
                            for item in models.json()["data"]]
        export_bytes, export_metadata = export_agent_zip(nexent, agent["agent_id"])
        with ZipFile(io.BytesIO(export_bytes)) as archive:
            exported_config = json.loads(archive.read("agent.json"))
            exported_agent = exported_config["agent_info"][str(exported_config["agent_id"])]
            require(set(exported_agent["skill_names"]) == SKILL_NAMES, "Export lost skill bindings")
            require({item["class_name"] for item in exported_agent["tools"]} == TOOL_NAMES, "Export lost tools")
        report["export"] = {"sha256": hashlib.sha256(export_bytes).hexdigest(),
                            **export_metadata,
                            "agent_config": exported_config, "skill_count": len(bound)}
        (ROOT / "artifacts/nexent-agent-export.zip").write_bytes(export_bytes)
        report["calls"] = []

        def call(name: str, inputs: dict) -> dict:
            response = nexent.post("/tool/validate", json={"name": name, "source": "mcp",
                                                          "usage": "peiwu-local", "inputs": inputs, "params": {}})
            payload = tool_payload(response)
            report["calls"].append({"tool": name, "http_status": response.status_code,
                                    "inputs": inputs, "result": payload})
            return payload

        lookup = call("evidence_lookup", {"query": "stu03", "version_id": "demo-initial"})
        require(bool(lookup["results"]), "No evidence found")
        source_id = lookup["results"][0]["id"]
        assets = call("asset_recognition", {"source_id": source_id})
        require(assets["schema"]["version"] == "peiwu-ontology-1", "Unexpected ontology version")
        versions = workbench.get("/versions"); versions.raise_for_status()
        candidates = [item for item in versions.json()["candidates"] if item["parent_id"] == "demo-initial"]
        require(bool(candidates), "Run the synthetic browser demonstration first to prepare a candidate")
        candidate = candidates[0]
        source = workbench.get("/documents/" + candidate["patch"]["source_id"]); source.raise_for_status()
        require(source.json()["kind"] == "synthetic", "Candidate must use synthetic evidence")
        suggestions = call("candidate_suggestions", {"source_id": source.json()["id"]})
        require(bool(suggestions["candidates"]), "Expected proposed candidates from the synthetic policy")
        graph = call("graph_query", {"requester_id": "stu03", "lot_id": "lot_eth",
                                     "cabinet_id": "cab_flam", "version_id": "demo-initial"})
        require(len(graph["edges"]) == 6, "Incomplete graph evidence")
        reranked = call("evidence_rerank_jev", {"query": "stu03", "version_id": "demo-initial", "limit": 5})
        require(reranked["status"] == "unavailable" and reranked["request_count"] == 0, "JEV must stay offline")
        request = {"request_id": "NEXENT-VERIFY", "requester_id": "stu01", "lot_id": "lot_eth",
                   "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL",
                   "as_of": "2026-09-23", "version_id": "demo-initial"}
        decisions = {}
        for action, changes in [("ALLOW", {}), ("DENY", {"requester_id": "stu03"}),
                                ("LIMIT", {"quantity": 300}), ("ISOLATE", {"lot_id": "lot_eth_exp"})]:
            decision = call("decision_check", {"request": {**request, **changes}})
            require(decision["status"] == "ready" and decision["decision"]["action"] == action, "Decision mismatch")
            require(decision["mode"] == "synthetic_demo" and decision["human_reviewer"] is None, "Demo boundary missing")
            for edge in decision["evidence"]:
                document = workbench.get("/documents/" + edge["source_id"]); document.raise_for_status()
                require(document.json()["sha256"] == edge["sha256"], "Evidence hash mismatch")
                require(any(chunk["locator"] == edge["locator"] and chunk["text"] == edge["quote"]
                            for chunk in document.json()["chunks"]), "Evidence locator/quote mismatch")
            decisions[action] = decision["decision"]
        repeat = call("decision_check", {"request": request})
        require(repeat["decision"] == decisions["ALLOW"], "Repeated decision JSON changed")
        references = [{key: edge[key] for key in ("source_id", "locator", "quote", "sha256")}
                      for edge in repeat["evidence"]]
        citation_review = call("evidence_rerank_jev", {"query": "合成资料中的 stu01 授权", "version_id": "demo-initial",
                                                      "limit": len(references), "citations": references})
        require(citation_review["citation_check"]["status"] == "passed", "Citation integrity check failed")
        require(citation_review["status"] == "unavailable" and citation_review["request_count"] == 0, "Citation review must stay offline")
        missing = call("decision_check", {"request": {**request, "requester_id": "unknown_demo_person"}})
        require(missing["status"] == "needs_review" and missing["decision"] is None, "Unknown input was decided")
        preview = call("candidate_review", {"candidate_id": candidate["id"]})
        require(preview["parent_id"] == "demo-initial" and "semantic_review" in preview, "Invalid review result")
        require(workbench.get("/status").json()["active_id"] == active_before, "Verification changed active version")
        report["checks"] = {"seven_tools": True, "four_decisions": True, "needs_review": True,
                            "evidence_quotes_and_hashes": True, "repeat_decision": True, "no_model_request": True,
                            "offline_citation_check": True, "agent_model_orchestration": False}
        agent_run = load_agent_run_evidence()
        if agent_run is not None:
            report["agent_run"] = agent_run
            report["checks"]["agent_model_orchestration"] = True
            report["checks"]["agent_run_synthetic"] = True
            report["status"] = "platform_tools_and_synthetic_model_run_passed"
            report["remaining"] = ["真实行业资料、独立审核、部署健康和正式材料仍待补"]
        else:
            report["status"] = "platform_tools_passed_model_pending"
            report["remaining"] = ["模型配置和费用授权待队员；尚未验证模型驱动的 Agent 编排"]
        if export_metadata["interceptor"]:
            report["remaining"].append("宿主机 IDM 拦截 ZIP；容器内真实 Web 导出已通过。IDM 例外设置待队员确认")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=local_url, default="http://127.0.0.1:3000")
    parser.add_argument("--workbench-url", type=local_url, default="http://127.0.0.1:8765")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/nexent-integration-report.json")
    args = parser.parse_args()
    output = args.output.resolve()
    artifacts = (ROOT / "artifacts").resolve()
    if (output.parent != artifacts or output.suffix.lower() != ".json"
            or not output.name.startswith("nexent-integration-report")):
        parser.error("Report must be a nexent-integration-report*.json file directly inside artifacts")
    report = {"status": "failed", "time": datetime.now(timezone.utc).isoformat(),
              "scope": "真实 Nexent 平台 API 复测；合成数据；历史合成 Agent/run 证据单独标记",
              "source_commit": (ROOT / "third_party/nexent/.pinned-commit").read_text().strip(),
              "package_sha256": hashlib.sha256((ROOT / "artifacts/peiwu-nexent-agent.zip").read_bytes()).hexdigest()}
    exit_code = 1
    try:
        report["containers"] = container_state()
        verify(args.url, args.workbench_url, report)
        exit_code = 0
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": report.get("checks"),
                      "error": report.get("error"), "report": str(output)}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

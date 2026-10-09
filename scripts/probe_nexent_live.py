"""Current synthetic Nexent verification; never reuses a historical Agent run."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from ontolens.nexent_runtime import NexentRuntime, TOOL_NAMES, observed_now


ROOT = Path(__file__).resolve().parents[1]
EXPLAINER_NAME = "ontolens_result_explainer"


async def provision_explainer(client: httpx.AsyncClient) -> int:
    response = await client.get("agent/list")
    response.raise_for_status()
    agents = response.json()
    existing = [a for a in agents if a.get("name") == EXPLAINER_NAME]
    if len(existing) > 1:
        raise ValueError("duplicate_explainer")
    if existing:
        return existing[0]["agent_id"]
    source = [a for a in agents if a.get("name") == "ontolens_compliance_review"]
    if len(source) != 1 or not source[0].get("model_ids"):
        raise ValueError("synthetic_agent_model_missing")
    response = await client.post("agent/update", json={
        "name": EXPLAINER_NAME, "display_name": "OntoLens 核验结果辅助说明",
        "description": "仅解释已脱敏程序结果；无工具、无资料检索、无技能或协作 Agent。",
        "model_ids": source[0]["model_ids"], "max_steps": 2, "enabled": True,
        "is_main_agent": True, "provide_run_summary": False, "allow_chat_metadata": False,
        "enabled_tool_ids": [], "enabled_skill_ids": [], "related_agent_ids": [],
        "related_external_agent_ids": [], "requested_output_tokens": 1600,
        "duty_prompt": "用中文简短解释给定的程序决定，仅用给定的枚举和计数。",
        "constraint_prompt": "不调用工具、不读取资料、不推测姓名或编号；不能改变程序决定。"
                             "needs_review 时等待人工核验，不声称已经人工审核或实际出库。",
        "few_shots_prompt": "",
    })
    response.raise_for_status()
    response = await client.get("agent/list")
    response.raise_for_status()
    found = [a for a in response.json() if a.get("name") == EXPLAINER_NAME]
    if len(found) != 1:
        raise ValueError("explainer_creation_unverified")
    return found[0]["agent_id"]


async def probe(*, provision: bool, agent_run: bool) -> dict:
    runtime = NexentRuntime.from_environment(ROOT)
    report = {"format": "ontolens-nexent-live-1", "started_at": observed_now(), "status": "failed",
              "scope": "Current live Nexent requests using synthetic inputs only; not industry evaluation or professional review.",
              "historical_agent_run_used": False, "calls": []}
    try:
        async with runtime._client(90) as client, httpx.AsyncClient(
                base_url="http://127.0.0.1:8765/api/", trust_env=False, timeout=30) as workbench:
            if provision:
                report["explainer_agent_id"] = await provision_explainer(client)
            report["integration"] = await runtime.status(force=True)
            status_response = await workbench.get("status")
            status_response.raise_for_status()
            if status_response.json().get("mode") != "synthetic_demo":
                raise ValueError("synthetic_workbench_required")
            active_before = status_response.json()["active_id"]

            async def call(name: str, inputs: dict) -> dict:
                started = observed_now()
                response = await client.post("tool/validate", json={"name": name, "source": "mcp",
                    "usage": "ontolens-local", "inputs": inputs, "params": {}})
                response.raise_for_status()
                result = response.json()
                if isinstance(result, str):
                    result = json.loads(result)
                if not isinstance(result, dict):
                    raise ValueError("tool_response_invalid")
                report["calls"].append({"tool": name, "started_at": started, "observed_at": observed_now(),
                                        "http_status": response.status_code, "result": result})
                return result

            lookup = await call("evidence_lookup", {"query": "stu01", "version_id": "demo-initial"})
            if not lookup.get("results"):
                raise ValueError("synthetic_evidence_missing")
            await call("asset_recognition", {"source_id": lookup["results"][0]["id"]})
            await call("graph_query", {"requester_id": "stu01", "lot_id": "lot_eth",
                                       "cabinet_id": "cab_flam", "version_id": "demo-initial"})
            versions_response = await workbench.get("versions")
            versions_response.raise_for_status()
            candidates = [c for c in versions_response.json().get("candidates", []) if c.get("parent_id") == "demo-initial"]
            if not candidates:
                raise ValueError("synthetic_candidate_missing")
            candidate = candidates[0]
            source_response = await workbench.get("documents/" + candidate["patch"]["source_id"])
            source_response.raise_for_status()
            if source_response.json().get("kind") != "synthetic":
                raise ValueError("candidate_source_must_be_synthetic")
            await call("candidate_suggestions", {"source_id": source_response.json()["id"]})
            await call("candidate_review", {"candidate_id": candidate["id"]})
            await call("evidence_rerank_jev", {"query": "stu01", "version_id": "demo-initial", "limit": 5})
            request = {"request_id": "NEXENT-LIVE-SYNTHETIC", "requester_id": "stu01", "lot_id": "lot_eth",
                       "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL",
                       "as_of": "2026-09-23", "version_id": "demo-initial"}
            decision = await call("decision_check", {"request": request})
            if decision.get("status") != "ready" or decision.get("decision", {}).get("action") != "ALLOW":
                raise ValueError("synthetic_decision_mismatch")
            report["seven_tools_verified"] = {c["tool"] for c in report["calls"]} == TOOL_NAMES
            report["explanation"] = await runtime.explain_run(decision)
            if agent_run:
                synthetic = NexentRuntime(runtime.base_url, token=runtime._token, timeout=420,
                    agent_name="ontolens_compliance_review", allow_tools=True)
                report["synthetic_agent_run"] = await synthetic.invoke(
                    "只核验现成合成示例，不访问其他资料。版本固定 demo-initial，日期2026-09-23。"
                    "申请为合成人员 stu01，批次 lot_eth，目标柜 cab_flam，100mL。"
                    "必须先调用 evidence_lookup(query='stu01',version_id='demo-initial') 与 "
                    "graph_query(requester_id='stu01',lot_id='lot_eth',cabinet_id='cab_flam',version_id='demo-initial')，"
                    "然后调用 decision_check，request_id='NEXENT-LIVE-SYNTHETIC'，其余参数如上。"
                    "最终只输出decision_check返回的status、decision、mode和证据数量；不能自行改判。"
                    "注明本轮实际模型与工具调用使用合成输入，不代表行业验证或人工审核。")
            final = await workbench.get("status")
            final.raise_for_status()
            if final.json()["active_id"] != active_before:
                raise ValueError("active_version_changed")
            report["active_version_unchanged"] = True
            good = report["seven_tools_verified"] and report["explanation"]["status"] == "ready"
            if agent_run:
                result = report["synthetic_agent_run"]
                good = good and result["status"] == "ready" and all(
                    result["tool_calls"].get(name, 0) > 0 for name in ("evidence_lookup", "graph_query", "decision_check"))
            report["status"] = "passed" if good else "incomplete"
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        report["error_code"] = type(error).__name__
    report["observed_at"] = observed_now()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provision-explainer", action="store_true")
    parser.add_argument("--agent-run", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/nexent-live-runtime-20261008.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != ROOT / "artifacts" or not output.name.startswith("nexent-live-") or output.suffix != ".json":
        parser.error("Use artifacts/nexent-live-*.json")
    report = asyncio.run(probe(provision=args.provision_explainer, agent_run=args.agent_run))
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("status", "observed_at", "seven_tools_verified", "error_code")}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

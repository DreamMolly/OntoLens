"""Live Nexent observations and bounded, non-authoritative Agent explanations.

No readiness is loaded from historical receipts. The token is held only in memory;
the adapter never persists model credentials, prompts, or reasoning traces.
"""
from __future__ import annotations

import asyncio
import copy
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ontolens.model_context import REASONS
from ontolens.config import env_value, read_environment


TOOL_NAMES = {"asset_recognition", "evidence_lookup", "graph_query", "candidate_suggestions",
              "evidence_rerank_jev", "decision_check", "candidate_review"}


def observed_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upstream_error_text(value: str) -> bool:
    """Nexent can wrap provider exceptions and max-step failures as final answers."""
    text = value.strip().lower()
    return bool(re.match(r"(?:error in generating (?:final llm|model) output\b|"
                         r"error in final answer generation\b|error code:\s*\d{3}\b|"
                         r"the agent was unable to generate a valid response\b)", text))


def _origin(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {
            "localhost", "127.0.0.1", "::1", "nexent-web", "host.docker.internal"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise ValueError("Nexent requires a loopback or approved internal HTTP origin without credentials")
    return value.rstrip("/")


def explanation_context(run: dict) -> dict:
    """Extract enums and counts only: never forward evidence, IDs or arbitrary text."""
    run = run.get("result", run)
    decision = run.get("decision") or {}
    action = decision.get("action")
    status = run.get("status")
    reason = decision.get("reason_code") or (run.get("review") or {}).get("reason_code")
    return {
        "status": status if status in {"ready", "needs_review"} else "needs_review",
        "action": action if action in {"ALLOW", "DENY", "LIMIT", "ISOLATE"} else None,
        "reason_code": reason if reason in REASONS else "REVIEW_REQUIRED",
        "evidence_count": len(run.get("evidence", [])) if isinstance(run.get("evidence"), list) else 0,
        "synthetic": True if run.get("mode") == "synthetic_demo" else None,
        "data_authenticity": "not_assessed",
        "human_review_required": True,
    }


class NexentRuntime:
    def __init__(self, base_url: str = "http://127.0.0.1:13000", *, token: str = "",
                 agent_id: int | None = None, transport=None, cache_seconds: float = 10,
                 timeout: float = 180, agent_name: str = "ontolens_result_explainer", allow_tools: bool = False):
        self.base_url = _origin(base_url)
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.allow_tools = allow_tools
        self._last_model_success: str | None = None
        self._token = token
        self._transport = transport
        self._cache_seconds = cache_seconds
        self._timeout = timeout
        self._cached: dict | None = None
        self._cached_at = 0.0
        self._status_lock = asyncio.Lock()
        self._run_lock = asyncio.Lock()

    @classmethod
    def from_environment(cls, root: Path | None = None) -> "NexentRuntime":
        root = root or Path(__file__).resolve().parents[2]
        settings = read_environment(root / ".env")

        def value(name: str, default: str = "") -> str:
            file_value = env_value("NEXENT_" + name, default, environment=settings)
            return env_value("NEXENT_" + name, file_value)

        agent_id = value("AGENT_ID")
        return cls(value("BASE_URL", "http://127.0.0.1:13000"), token=value("API_TOKEN"),
                   agent_id=int(agent_id) if agent_id else None,
                   agent_name=value("AGENT_NAME", "ontolens_result_explainer"))

    def _client(self, timeout: float = 6) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url + "/api/", trust_env=False,
                                 follow_redirects=False, timeout=timeout, transport=self._transport,
                                 headers={"Authorization": "Bearer " + self._token} if self._token else {})

    async def status(self, force: bool = False) -> dict:
        async with self._status_lock:
            if not force and self._cached is not None and time.monotonic() - self._cached_at < self._cache_seconds:
                return copy.deepcopy(self._cached)
            result = {"connected": False, "model_ready": False, "model_bound": False,
                      "model_verified_at": self._last_model_success, "base_url": self.base_url,
                      "agent_id": self.agent_id, "observed_at": observed_now(), "checks": {},
                      "notice": "Nexent 当前不可达；本地程序核验仍可使用。"}
            try:
                async with self._client() as client:
                    async def get(path: str):
                        response = await client.get(path)
                        response.raise_for_status()
                        return response.json()

                    agents, models = await asyncio.gather(
                        get("agent/list"), get("model/llm_list"))
                    result["connected"] = True
                    matches = [a for a in agents if a.get("name") == self.agent_name
                               and (self.agent_id is None or a.get("agent_id") == self.agent_id)]
                    agent = matches[0] if len(matches) == 1 else {}
                    result["agent_id"] = agent.get("agent_id", self.agent_id)
                    # Nexent exposes draft bindings at version 0 while a normal
                    # run defaults to the published version. Pin both probes and
                    # the later run to the same configured draft snapshot.
                    version_no = 0
                    model_ids = []
                    tool_free = False
                    info = {}
                    if agent:
                        detail = await client.post("agent/search_info", json={
                            "agent_id": agent["agent_id"], "version_no": version_no})
                        detail.raise_for_status()
                        info = detail.json()
                        model_ids = info.get("model_ids") or []
                        tool_free = (info.get("tools") == [] and info.get("skills") == []
                                     and not info.get("sub_agent_id_list")
                                     and not info.get("external_sub_agent_id_list")
                                     and not info.get("allow_chat_metadata"))
                    result["tool_free"] = tool_free
                    result["version_no"] = version_no
                    result["model_ids"] = list(model_ids)
                    result["model_id"] = next((model_id for model_id in model_ids
                                                if any(m.get("model_id") == model_id
                                                       for m in models.get("data", []))), None)
                    model_found = result["model_id"] is not None
                    mcp_ok = False
                    # MCP is required for tool-enabled agents only. A transient
                    # MCP outage must not mask a ready tool-free explanation run.
                    try:
                        services = await get("mcp/list")
                        registered = [s for s in services.get("remote_mcp_server_list", [])
                                      if s.get("remote_mcp_server_name") == "ontolens-local" and s.get("enabled")]
                        if len(registered) == 1:
                            response = await client.get("mcp/healthcheck", params={"mcp_id": registered[0]["mcp_id"]})
                            response.raise_for_status()
                            mcp_ok = response.json().get("data", {}).get("health_status") == "healthy"
                    except (httpx.HTTPError, ValueError, TypeError, KeyError):
                        mcp_ok = False
                    result["checks"] = {"agent_available": agent.get("is_available") is True,
                                        "model_bound": model_found, "mcp_healthy": mcp_ok}
                    result["model_bound"] = model_found
                    result["model_ready"] = bool(agent.get("is_available") is True and model_found
                                                 and (tool_free or self.allow_tools)
                                                 and (mcp_ok or tool_free))
                    result["notice"] = ("已实时连接 Nexent；模型已绑定。本次生成是否成功以调用结果为准。"
                                        if result["model_ready"] else "Nexent 可连接，但 Agent、模型绑定或 MCP 尚未就绪。")
            except (httpx.HTTPError, ValueError, TypeError, KeyError) as error:
                result["error_code"] = type(error).__name__
                result["model_ready"] = False
            result["observed_at"] = observed_now()
            self._cached, self._cached_at = result, time.monotonic()
            return copy.deepcopy(result)

    async def explain_run(self, run: dict) -> dict:
        live = await self.status(force=True)
        if not live.get("tool_free"):
            return {"status": "unavailable", "text": "", "provider": "nexent",
                    "observed_at": live["observed_at"], "agent_id": live["agent_id"],
                    "tool_calls": {}, "model_request_sent": False, "authoritative": False,
                    "error_code": "tool_free_agent_required",
                    "notice": "辅助说明需要无工具、无技能和无协作 Agent 的专用实例，当前未验证通过。"}
        context = explanation_context(run)
        prompt = (
            "你正在生成程序核验结果的辅助说明。只使用下列已脱敏枚举和数量，"
            "不要调用任何工具，不要搜索或读取资料，不要推测姓名、申请编号、来源或缺失事实。"
            "不得改变或替代程序决定，不得宣称已人工审核或可实际出库。"
            "用中文简短说明当前动作的含义和人工核对下一步；needs_review时明确等待人工。"
            "合成数据必须明确标注。只返回最终说明，不输出推理过程。\n"
            "synthetic 为 null 仅表示资料性质未判定，工作区模式不能证明真实性；"
            "禁止声称资料是真实数据、非合成数据或已获行业验证。\n"
            + json.dumps(context, ensure_ascii=False)
        )
        return await self.invoke(prompt, require_tool_free=True)

    async def invoke(self, prompt: str, *, require_tool_free: bool = False) -> dict:
        """Invoke the configured Agent. Callers must authorize and sanitize any custom prompt."""
        receipt = {"status": "unavailable", "text": "", "provider": "nexent",
                   "observed_at": observed_now(), "agent_id": None, "tool_calls": {},
                   "event_counts": {},
                   "model_request_sent": False, "authoritative": False,
                   "memory_retrieval_disabled": require_tool_free,
                   "notice": "Nexent 辅助说明不能改变程序决定，也不能替代人工审核。"}
        if self._run_lock.locked():
            return {**receipt, "error_code": "busy", "notice": "另一个 Nexent 请求正在运行，请稍后重试。"}
        async with self._run_lock:
            live = await self.status(force=True)
            receipt["agent_id"] = live["agent_id"]
            if require_tool_free and not live.get("tool_free"):
                return {**receipt, "error_code": "tool_free_agent_required"}
            if not live["model_ready"]:
                return {**receipt, "observed_at": live["observed_at"], "notice": live["notice"]}
            try:
                async with asyncio.timeout(self._timeout):
                    async with self._client(self._timeout) as client:
                        async with client.stream("POST", "agent/run", json={
                            "agent_id": live["agent_id"], "model_id": live["model_id"],
                            "version_no": live["version_no"], "query": prompt, "history": [],
                            # Nexent's ephemeral execution path disables automatic
                            # memory retrieval/storage in addition to our empty
                            # configured tool/skill/Agent bindings.
                            "is_debug": require_tool_free, "enable_automation_tool": False,
                            "requested_output_tokens": 1600,
                        }) as response:
                            response.raise_for_status()
                            receipt["model_request_sent"] = True
                            total = 0
                            async for line in response.aiter_lines():
                                total += len(line)
                                if total > 2_000_000:
                                    raise ValueError("stream_limit")
                                if not line.startswith("data:"):
                                    continue
                                raw = line[5:].strip()
                                if raw == "[DONE]":
                                    continue
                                event = json.loads(raw)
                                kind = event.get("type", "")
                                if isinstance(kind, str) and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,63}", kind):
                                    receipt["event_counts"][kind] = receipt["event_counts"].get(kind, 0) + 1
                                if (kind in {"error", "model_error", "agent_error"}
                                        or event.get("error") or event.get("status") in {"error", "failed"}):
                                    raise ValueError("agent_error")
                                if kind == "final_answer" and isinstance(event.get("content"), str):
                                    if upstream_error_text(event["content"]):
                                        raise ValueError("upstream_final_answer_error")
                                    receipt["text"] = event["content"].strip()[:20000]
                                if kind in {"tool_call", "tool"}:
                                    name = event.get("name") or event.get("tool_name")
                                    if isinstance(name, str) and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,63}", name):
                                        receipt["tool_calls"][name] = receipt["tool_calls"].get(name, 0) + 1
                                    if require_tool_free and name != "final_answer":
                                        raise ValueError("unexpected_tool_call")
                            if not receipt["text"]:
                                raise ValueError("empty_final_answer")
                            receipt["status"] = "ready"
                            self._last_model_success = observed_now()
                            self._cached = None
            except (httpx.HTTPError, ValueError, TypeError, TimeoutError) as error:
                code = str(error) if isinstance(error, ValueError) and str(error) in {
                    "agent_error", "upstream_final_answer_error", "empty_final_answer",
                    "unexpected_tool_call", "stream_limit"} else type(error).__name__
                receipt.update(status="error", text="", error_code=code)
                self._last_model_success = None
                self._cached = None
            receipt["observed_at"] = observed_now()
            return receipt

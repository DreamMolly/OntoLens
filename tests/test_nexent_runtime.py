import asyncio
import json

import httpx
import pytest

from ontolens.nexent_runtime import NexentRuntime, explanation_context


def runtime_with(handler, **kwargs):
    return NexentRuntime(transport=httpx.MockTransport(handler), **kwargs)


def responses(request, *, tools=None):
    path = request.url.path
    if path.endswith("/agent/list"):
        return httpx.Response(200, json=[{"name": "ontolens_result_explainer", "agent_id": 2,
                                        "model_ids": [1], "is_available": True}])
    if path.endswith("/agent/search_info"):
        return httpx.Response(200, json={"model_ids": [1], "tools": tools or [], "skills": [],
                                        "allow_chat_metadata": False})
    if path.endswith("/model/llm_list"):
        return httpx.Response(200, json={"data": [{"model_id": 1}]})
    if path.endswith("/mcp/list"):
        return httpx.Response(200, json={"remote_mcp_server_list": [
            {"remote_mcp_server_name": "ontolens-local", "enabled": True, "mcp_id": 1}]})
    if path.endswith("/mcp/healthcheck"):
        return httpx.Response(200, json={"data": {"health_status": "healthy"}})
    raise AssertionError(path)


def test_live_status_cache_preserves_observation_and_rechecks_failure():
    calls = []

    def handler(request):
        calls.append(request)
        return responses(request)

    runtime = runtime_with(handler)

    async def scenario():
        first = await runtime.status()
        count = len(calls)
        second = await runtime.status()
        assert first == second and first["connected"] and first["model_ready"] and first["tool_free"]
        assert len(calls) == count
        second["checks"]["mcp_healthy"] = False
        assert (await runtime.status())["checks"]["mcp_healthy"]
        runtime._transport = httpx.MockTransport(
            lambda req: httpx.Response(503) if req.url.path.endswith("/mcp/list") else responses(req))
        mcp_failed = await runtime.status(force=True)
        assert mcp_failed["connected"] and mcp_failed["model_ready"] and mcp_failed["tool_free"]
        assert mcp_failed["checks"]["mcp_healthy"] is False
        runtime._transport = httpx.MockTransport(lambda req: httpx.Response(503))
        failed = await runtime.status(force=True)
        assert not failed["connected"] and not failed["model_ready"]
        assert failed["error_code"] == "HTTPStatusError" and failed["observed_at"]

    asyncio.run(scenario())


def test_run_pins_the_same_draft_version_and_model_checked_by_status():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/agent/search_info"):
            return httpx.Response(200, json={"model_ids": [2], "tools": [{"name": "decision_check"}],
                                            "skills": [], "allow_chat_metadata": False})
        if request.url.path.endswith("/model/llm_list"):
            return httpx.Response(200, json={"data": [{"model_id": 1}, {"model_id": 2}]})
        if request.url.path.endswith("/agent/run"):
            body = json.loads(request.content)
            assert body["version_no"] == 0 and body["model_id"] == 2
            assert body["is_debug"] is False
            return httpx.Response(200, text='data: {"type":"final_answer","content":"固定版本说明"}\n\n')
        return responses(request)

    result = asyncio.run(runtime_with(handler, allow_tools=True).invoke("TEST FIXTURE"))
    assert result["status"] == "ready" and result["text"] == "固定版本说明"
    search = [request for request in requests if request.url.path.endswith("/agent/search_info")]
    assert len(search) == 1
    assert all(json.loads(request.content)["version_no"] == 0 for request in search)


def test_private_input_never_leaves_allowlist_and_output_cannot_change_decision():
    original = {"status": "ready", "mode": "business", "request": {"requester_id": "private-person"},
                "decision": {"action": "DENY", "reason_code": "private-reason"},
                "evidence": [{"quote": "private-source", "source_id": "private-doc"}], "run_id": "private-run"}
    prompts = []

    def handler(request):
        if request.url.path.endswith("/agent/run"):
            body = json.loads(request.content)
            assert body["is_debug"] is True and body["enable_automation_tool"] is False
            prompts.append(body["query"])
            return httpx.Response(200, text='data: {"type":"model_output_thinking","content":"hidden"}\n\n'
                                 'data: {"type":"final_answer","content":"辅助说明"}\n\n')
        return responses(request)

    result = asyncio.run(runtime_with(handler).explain_run({"result": original, "id": "private-wrapper"}))
    assert result["status"] == "ready" and result["text"] == "辅助说明"
    assert result["model_request_sent"] and not result["authoritative"]
    assert all("private" not in p for p in prompts)
    assert original["decision"]["action"] == "DENY"
    assert explanation_context(original)["evidence_count"] == 1
    assert explanation_context(original)["reason_code"] == "REVIEW_REQUIRED"
    assert explanation_context({"status": "needs_review", "review": {"reason_code": "UNIT_MISMATCH"}})["reason_code"] == "UNIT_MISMATCH"


def test_agent_with_tools_cannot_receive_private_explanation():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return responses(request, tools=[{"enabled": True, "name": "evidence_lookup"}])

    result = asyncio.run(runtime_with(handler).explain_run({"mode": "business"}))
    assert result["error_code"] == "tool_free_agent_required"
    assert not result["model_request_sent"]
    assert "/api/agent/run" not in calls


def test_unexpected_runtime_tool_event_fails_closed():
    def handler(request):
        if request.url.path.endswith("/agent/run"):
            return httpx.Response(200, text='data: {"type":"tool","tool_name":"read_skill_md"}\n'
                                 'data: {"type":"final_answer","content":"unsafe answer"}\n')
        return responses(request)

    result = asyncio.run(runtime_with(handler).explain_run({"mode": "business"}))
    assert result["status"] == "error" and result["text"] == ""
    assert result["tool_calls"] == {"read_skill_md": 1}


@pytest.mark.parametrize("stream", [
    'data: {"type":"model_output_thinking","content":"not a final answer"}\n',
    'data: {"type":"final_answer","content":"partial"}\ndata: {"type":"error","content":"secret"}\n',
    'data: invalid-json-secret\n',
])
def test_incomplete_or_failed_stream_never_reports_success_or_leaks_error(stream):
    def handler(request):
        if request.url.path.endswith("/agent/run"):
            return httpx.Response(200, text=stream)
        return responses(request)

    result = asyncio.run(runtime_with(handler).explain_run({}))
    assert result["status"] == "error" and result["text"] == ""
    assert "secret" not in json.dumps(result)


def test_config_rejects_remote_and_embedded_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOLENS_LOAD_ENV", "true")
    for name in list(__import__("os").environ):
        if name.startswith(("ONTOLENS_NEXENT_", "NEXENT_")):
            monkeypatch.delenv(name)
    (tmp_path / ".env").write_text("ONTOLENS_NEXENT_BASE_URL=http://127.0.0.1:3001\n"
                                    "ONTOLENS_NEXENT_API_TOKEN=private-token\nONTOLENS_NEXENT_AGENT_ID=2\n")
    runtime = NexentRuntime.from_environment(tmp_path)
    assert runtime.base_url == "http://127.0.0.1:3001" and runtime.agent_id == 2
    for origin in ["https://remote.example", "http://user:secret@localhost", "http://localhost?token=x"]:
        with pytest.raises(ValueError):
            NexentRuntime(origin)


@pytest.mark.parametrize("event", [
    {"type": "final_answer", "content": "Error in generating final LLM output: Error code: 404 - secret-provider-data"},
    {"type": "final_answer", "content": "Error in generating model output:\nsecret-provider-data"},
    {"type": "final_answer", "content": "The agent was unable to generate a valid response after reaching the maximum number of steps."},
    {"type": "final_answer", "content": "   "},
    {"type": "final_answer", "content": "visible partial", "error": {"message": "secret-provider-data"}},
    {"type": "final_answer", "content": "visible partial", "status": "failed"},
])
def test_provider_error_wrapped_as_final_answer_fails_closed(event):
    def handler(request):
        if request.url.path.endswith("/agent/run"):
            return httpx.Response(200, text="data: " + json.dumps(event) + "\n\n")
        return responses(request)

    runtime = runtime_with(handler)
    runtime._last_model_success = "historical-success"
    result = asyncio.run(runtime.explain_run({}))
    assert result["status"] == "error" and result["text"] == ""
    assert result["model_request_sent"] is True
    assert "secret-provider-data" not in json.dumps(result)
    assert runtime._last_model_success is None

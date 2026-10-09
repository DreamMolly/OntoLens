import argparse
import base64
import json
from types import SimpleNamespace

import httpx
import pytest

from scripts.verify_nexent import export_agent_zip, load_agent_run_evidence, local_url, tool_payload


@pytest.mark.parametrize("url", ["https://example.com", "http://example.com", "http://user:secret@localhost",
                                 "http://localhost/?key=private", "http://localhost/api"])
def test_platform_verification_refuses_nonlocal_or_credential_urls(url):
    with pytest.raises(argparse.ArgumentTypeError):
        local_url(url)


def test_platform_tool_response_handles_nexent_json_string():
    result = {"status": "needs_review", "decision": None}
    assert tool_payload(httpx.Response(200, json=json.dumps(result), request=httpx.Request("POST", "http://localhost"))) == result


def test_platform_tool_http_failure_is_not_counted_as_success():
    with pytest.raises(httpx.HTTPStatusError):
        tool_payload(httpx.Response(500, json={"message": "failed"}, request=httpx.Request("POST", "http://localhost")))


def test_regular_export_does_not_invoke_container():
    def no_container(*args, **kwargs):
        pytest.fail("A successful host export must not use a fallback")
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"test-zip"))
    with httpx.Client(base_url="http://localhost/api", transport=transport) as client:
        content, metadata = export_agent_zip(client, 1, no_container)
    assert content == b"test-zip"
    assert metadata["transport"] == "web_proxy"
    assert metadata["interceptor"] is None


def test_idm_interception_is_distinguished_from_platform_failure():
    def container(command, **kwargs):
        assert command[:5] == ["docker", "exec", "nexent-web", "node", "-e"]
        assert "127.0.0.1:3000/api/agent/export" in command[-1]
        return SimpleNamespace(stdout=base64.b64encode(b"actual-web-export").decode())
    transport = httpx.MockTransport(lambda request: httpx.Response(204, extensions={
        "reason_phrase": b"Intercepted by the IDM Advanced Integration"
    }))
    with httpx.Client(base_url="http://localhost/api", transport=transport) as client:
        content, metadata = export_agent_zip(client, 1, container)
    assert content == b"actual-web-export"
    assert metadata["interceptor"] == "IDM Advanced Integration"
    assert metadata["container_web_http_status"] == 200


def test_unknown_empty_export_is_not_silently_bypassed():
    def no_container(*args, **kwargs):
        pytest.fail("Unknown empty responses must be investigated")
    transport = httpx.MockTransport(lambda request: httpx.Response(204))
    with httpx.Client(base_url="http://localhost/api", transport=transport) as client:
        with pytest.raises(ValueError, match="Unknown empty"):
            export_agent_zip(client, 1, no_container)


def test_model_run_evidence_requires_real_synthetic_agent_contract(tmp_path):
    record = tmp_path / "run.json"
    record.write_text(json.dumps({
        "format": "ontolens-nexent-agent-run-1",
        "model_orchestration_verified": True,
        "final_status": "ready",
        "decision": {"action": "ALLOW"},
        "tool_calls": {"evidence_lookup": 1, "decision_check": 1},
    }), encoding="utf-8")
    evidence = load_agent_run_evidence(record)
    assert evidence["decision"]["action"] == "ALLOW"
    assert len(evidence["artifact_sha256"]) == 64


def test_model_run_evidence_rejects_missing_decision_chain(tmp_path):
    record = tmp_path / "run.json"
    record.write_text(json.dumps({
        "format": "ontolens-nexent-agent-run-1",
        "model_orchestration_verified": True,
        "final_status": "ready",
        "decision": {"action": "ALLOW"},
        "tool_calls": {"evidence_lookup": 0, "decision_check": 0},
    }), encoding="utf-8")
    with pytest.raises(ValueError):
        load_agent_run_evidence(record)

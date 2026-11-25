import json

import pytest

from scripts.probe_nexent_live import agent_run_checks


@pytest.fixture
def observed_run():
    result = {
        "status": "ready", "mode": "synthetic_demo", "version_id": "demo-initial",
        "snapshot_hash": "a" * 64, "decision": {"action": "ALLOW", "approved_quantity": 100},
        "evidence": [{"source_id": "synthetic"}],
    }
    answer = {key: value for key, value in result.items() if key != "evidence"}
    answer["evidence_count"] = 1
    run = {
        "status": "ready", "model_request_sent": True,
        "tool_calls": {"read_skill_md": 1, "evidence_lookup": 1, "graph_query": 1, "decision_check": 1},
        "text": json.dumps(answer),
    }
    return result, answer, run


def test_live_agent_receipt_requires_skill_trace_and_program_result(observed_run):
    result, _, run = observed_run
    checks = agent_run_checks(run, result)
    assert checks and all(checks.values())
    run["tool_calls"].pop("read_skill_md")
    assert not agent_run_checks(run, result)["skill_read_observed"]


@pytest.mark.parametrize("key, value", [
    ("decision", {"action": "DENY"}),
    ("snapshot_hash", "b" * 64),
    ("version_id", "archived"),
    ("evidence_count", True),
])
def test_live_agent_rejects_answer_changed_from_reference(observed_run, key, value):
    result, answer, run = observed_run
    answer[key] = value
    run["text"] = json.dumps(answer)
    assert not agent_run_checks(run, result)["answer_matches_program_result"]


def test_live_agent_identifies_incomplete_and_fenced_answer(observed_run):
    result, _, run = observed_run
    run["text"] = "```json\n" + run["text"] + "\n```"
    assert all(agent_run_checks(run, result).values())
    run["model_request_sent"] = False
    assert not agent_run_checks(run, result)["model_request_completed"]
    run["text"] = "模型称核验通过"
    assert not agent_run_checks(run, result)["answer_matches_program_result"]

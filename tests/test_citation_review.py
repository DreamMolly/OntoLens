import json
from types import SimpleNamespace

import pytest

from ontolens.jev import CITATION_QUESTION_VERSION, JevReranker
from ontolens.workspace import Workspace, digest
from tests.test_workbench import ROOT, client, request, source


@pytest.fixture(autouse=True)
def isolated_jev_environment(monkeypatch):
    for name in ("TYPESAFE_API_KEY", "TYPESAFE_MODEL", "TYPESAFE_BASE_URL", "TYPESAFE_ENDPOINT",
                 "TYPESAFE_JEV_REVIEW_THRESHOLD"):
        monkeypatch.delenv(name, raising=False)


def references(report):
    return [{key: edge[key] for key in ("source_id", "locator", "quote", "sha256")} for edge in report["evidence"]]


def test_citations_are_checked_without_claiming_semantic_support(client):
    original = client.post("/api/check", json=request()).json()
    response = client.post("/api/evidence/jev", json={"query": "一个未被验证的陈述", "citations": references(original)})
    result = response.json()
    assert response.status_code == 200
    assert result["citation_check"]["status"] == "passed"
    assert len(result["citation_check"]["references"]) == 6
    assert result["status"] == "unavailable"
    assert result["code"] == "not_configured"
    assert result["request_count"] == 0
    assert not any("jev_probability" in item for item in result["candidates"])
    assert result["question_version"] == CITATION_QUESTION_VERSION
    assert result["snapshot_hash"] == original["snapshot_hash"]
    assert len(result["citation_input_hash"]) == 64
    saved = client.get("/api/runs/" + original["run_id"] + "/export").json()
    assert saved["run"]["result"] == original
    assert len(client.get("/api/runs").json()) == 1
    assert "decision" not in result


@pytest.mark.parametrize("field,value,code", [
    ("quote", "伪造的来源文字", "quote_mismatch"),
    ("sha256", "0" * 64, "hash_mismatch"),
    ("locator", "L999999", "locator_missing"),
    ("source_id", "doc_not_published", "source_not_in_snapshot"),
])
def test_invalid_citation_prevents_model_request(client, monkeypatch, field, value, code):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    report = client.post("/api/check", json=request()).json()
    citations = references(report)
    citations[-1][field] = value
    result = client.app.state.workspace.rerank_evidence(
        "陈述", citations=citations, allow_live=True, synthetic_claim=True
    )
    assert result["status"] == "unavailable"
    assert result["code"] == "citation_integrity_failed"
    assert result["citation_check"]["references"][-1]["code"] == code
    assert result["request_count"] == 0


def test_citation_raw_file_hash_is_recomputed(client):
    report = client.post("/api/check", json=request()).json()
    citation = references(report)[0]
    with client.app.state.workspace.connect(write=True) as connection:
        connection.execute("UPDATE documents SET raw=? WHERE id=?", (b"tampered", citation["source_id"]))
    result = client.post("/api/evidence/jev", json={"query": "陈述", "citations": [citation]}).json()
    assert result["citation_check"]["references"][0]["code"] == "hash_mismatch"
    assert result["request_count"] == 0


def test_duplicate_or_truncated_citations_are_not_silently_scored(client):
    report = client.post("/api/check", json=request()).json()
    citation = references(report)[0]
    duplicated = client.post("/api/evidence/jev", json={"query": "陈述", "citations": [citation, citation]}).json()
    assert duplicated["citation_check"]["references"][1]["code"] == "duplicate_reference"
    limited = client.post("/api/evidence/jev", json={"query": "陈述", "limit": 1, "citations": references(report)})
    assert limited.status_code == 422


@pytest.mark.parametrize("extra", [{"allow_live": True}, {"synthetic_claim": True}, {"citations": []}])
def test_api_cannot_inject_online_or_synthetic_claim_permission(client, extra):
    report = client.post("/api/check", json=request()).json()
    response = client.post("/api/evidence/jev", json={"query": "陈述", "citations": references(report), **extra})
    assert response.status_code == 422


def test_api_citations_stay_offline_with_a_configured_key(client, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    report = client.post("/api/check", json=request()).json()
    result = client.post("/api/evidence/jev", json={"query": "陈述", "citations": references(report)}).json()
    assert result["citation_check"]["status"] == "passed"
    assert result["code"] == "live_not_authorized"
    assert result["request_count"] == 0


def test_uploaded_synthetic_permission_stays_opt_in_after_restart(client):
    imported = source(client)
    assert imported["external_model_allowed"] is False
    reopened = Workspace(ROOT, client.app.state.workspace.database)
    assert reopened.document(imported["id"])["external_model_allowed"] is False


def test_legacy_auto_grant_is_restored_from_import_audit(client):
    imported = source(client)
    workspace = client.app.state.workspace
    with workspace.connect(write=True) as connection:
        connection.execute("UPDATE documents SET external_model_allowed=1 WHERE id=?", (imported["id"],))
    reopened = Workspace(ROOT, workspace.database)
    assert reopened.document(imported["id"])["external_model_allowed"] is False
    events = client.get("/api/audit").json()
    assert any(item["event"] == "source_permission_restored" for item in events)


def test_explicit_synthetic_permission_is_preserved(client):
    workspace = client.app.state.workspace
    imported = workspace.import_document("opt-in.txt", "text/plain", b"demo", [{"locator": "L1", "text": "demo"}], "synthetic", True)
    reopened = Workspace(ROOT, workspace.database)
    assert reopened.document(imported["id"])["external_model_allowed"] is True


class CitationClient:
    bad_value = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def system_one(self, state, questions, model):
        assert len(questions) == 6
        assert set(questions) == {f"{prefix}_{index}" for prefix in ("support", "contradiction") for index in range(3)}
        scores = {"support_0": 0.94, "support_1": 0.2, "support_2": 0.92,
                  "contradiction_0": 0.03, "contradiction_1": 0.91, "contradiction_2": 0.9}
        if self.bad_value is not None:
            scores["contradiction_0"] = self.bad_value
        return SimpleNamespace(model=model, usage=SimpleNamespace(model_dump=lambda mode: {"input_tokens": 100, "output_tokens": 6}),
                               answers={key: SimpleNamespace(type="noul", noul=value) for key, value in scores.items()})


def semantic_candidates():
    return [{"source_id": f"doc-{index}", "locator": "L1", "text": "合成片段", "sha256": digest(str(index).encode()),
             "kind": "synthetic", "external_model_allowed": True} for index in range(3)]


def test_citation_signals_prioritize_review_without_deciding(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    judge = JevReranker(client_factory=CitationClient)
    result = judge.rerank("合成陈述", semantic_candidates(), purpose="citation_review", synthetic_claim=True, allow_live=True)
    assert result["status"] == "ready"
    assert result["review_required"] is True
    assert [item["jev_review_hint"] for item in result["candidates"]] == ["conflicting_signals", "possible_contradiction", "support_signal"]
    assert [item["jev_review_priority"] for item in result["candidates"]] == ["high", "high", "normal"]
    assert result["usage"]["output_tokens"] == 6
    assert result["resolved_model"] == "jev-1.13.0"
    assert "confidence" not in json.dumps(result)
    assert "action" not in result and "decision" not in result
    repeated = judge.rerank("合成陈述", semantic_candidates(), purpose="citation_review", synthetic_claim=True, allow_live=True)
    assert repeated["input_hash"] == result["input_hash"]
    changed = semantic_candidates()
    changed[0]["sha256"] = "0" * 64
    different = judge.rerank("合成陈述", changed, purpose="citation_review", synthetic_claim=True, allow_live=True)
    assert different["input_hash"] != result["input_hash"]


@pytest.mark.parametrize("value", [True, -0.1, 1.1, float("nan")])
def test_bad_contradiction_probability_preserves_unscored_candidates(monkeypatch, value):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(CitationClient, "bad_value", value)
    result = JevReranker(client_factory=CitationClient).rerank(
        "合成陈述", semantic_candidates(), purpose="citation_review", synthetic_claim=True, allow_live=True
    )
    assert result["code"] == "provider_error"
    assert result["candidates"] == semantic_candidates()


def test_arbitrary_live_claims_are_not_authorized_by_an_api_key(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    result = JevReranker(client_factory=CitationClient).rerank(
        "任意陈述", semantic_candidates(), purpose="citation_review", allow_live=True
    )
    assert result["code"] == "claim_not_authorized"
    assert result["request_count"] == 0

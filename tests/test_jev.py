from types import SimpleNamespace

import pytest

from ontolens.jev import JevReranker
from scripts.verify_jev import load_local_env


class FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def system_one(self, state, questions, model, **kwargs):
        assert model == "jev-1.13.0"
        assert len(questions) == 3
        scores = [0.12, 0.91, 0.44]
        answers = {
            question_id: SimpleNamespace(type="noul", noul=scores[index])
            for index, question_id in enumerate(questions)
        }
        return SimpleNamespace(
            model="jev-1.13.0",
            answers=answers,
            usage=SimpleNamespace(model_dump=lambda mode: {"input_tokens": 123, "output_tokens": 7}),
        )


class FailingClient(FakeClient):
    def system_one(self, *args, **kwargs):
        raise RuntimeError("simulated endpoint error")


def candidates():
    return [
        {"id": "doc-a", "source_id": "doc-a", "title": "A", "locator": "L1", "text": "alpha", "kind": "synthetic", "external_model_allowed": True},
        {"id": "doc-b", "source_id": "doc-b", "title": "B", "locator": "L2", "text": "beta", "kind": "synthetic", "external_model_allowed": True},
        {"id": "doc-c", "source_id": "doc-c", "title": "C", "locator": "L3", "text": "gamma", "kind": "synthetic", "external_model_allowed": True},
    ]


def test_jev_batches_candidates_and_sorts_by_noul(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setenv("TYPESAFE_MODEL", "jev-1.13.0")
    result = JevReranker(client_factory=FakeClient).rerank("which source supports this?", candidates(), 3, allow_live=True)
    assert result["status"] == "ready"
    assert result["fallback"] is False
    assert result["request_count"] == 1
    assert result["resolved_model"] == "jev-1.13.0"
    assert result["usage"] == {"input_tokens": 123, "output_tokens": 7}
    assert [item["source_id"] for item in result["candidates"]] == ["doc-b", "doc-c", "doc-a"]
    assert all("jev_confidence" not in item for item in result["candidates"])
    assert [item["jev_review_priority"] for item in result["candidates"]] == ["high", "normal", "normal"]


def test_jev_rejects_candidates_without_external_model_permission(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    result = JevReranker(client_factory=FakeClient).rerank(
        "query", [{**candidates()[0], "kind": "private", "external_model_allowed": False}], 1, allow_live=True
    )
    assert result["status"] == "unavailable"
    assert result["code"] == "source_not_allowed"


def test_jev_is_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    result = JevReranker().rerank("query", candidates(), 3)
    assert result["status"] == "unavailable"
    assert result["code"] == "not_configured"


def test_jev_invalid_review_threshold_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("TYPESAFE_JEV_REVIEW_THRESHOLD", "not-a-number")
    assert JevReranker().configuration()["review_threshold"] == 0.75


def test_jev_provider_error_keeps_unmodified_candidates(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    result = JevReranker(client_factory=FailingClient).rerank("query", candidates(), 3, allow_live=True)
    assert result["status"] == "error"
    assert result["code"] == "provider_error"
    assert result["fallback"] is True
    assert result["candidates"] == candidates()


def test_jev_configured_key_does_not_authorize_network(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    def forbidden_client(**kwargs):
        pytest.fail("The default entry point must not create a network client")
    result = JevReranker(client_factory=forbidden_client).rerank("query", candidates())
    assert result["code"] == "live_not_authorized"
    assert result["request_count"] == 0
    assert result["status"] == "unavailable"


@pytest.mark.parametrize("changes", [
    {"kind": "private", "external_model_allowed": True},
    {"external_model_allowed": "true"},
    {"external_model_allowed": 1},
])
def test_jev_rejects_forged_external_permission(monkeypatch, changes):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    def forbidden_client(**kwargs):
        pytest.fail("Unauthorized source must not reach TypeSafe")
    result = JevReranker(client_factory=forbidden_client).rerank(
        "query", [{**candidates()[0], **changes}], allow_live=True
    )
    assert result["code"] == "source_not_allowed"
    assert result["request_count"] == 0


def test_verify_jev_loads_local_env_without_overriding_process_values(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOLENS_LOAD_ENV", "true")
    env_file = tmp_path / ".env"
    env_file.write_text("TYPESAFE_API_KEY=local-key\nTYPESAFE_MODEL=local-model\n", encoding="utf-8")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("TYPESAFE_MODEL", "process-model")
    load_local_env(env_file)
    assert __import__("os").environ["TYPESAFE_API_KEY"] == "local-key"
    assert __import__("os").environ["TYPESAFE_MODEL"] == "process-model"

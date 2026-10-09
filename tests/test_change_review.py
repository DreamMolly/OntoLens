from types import SimpleNamespace

import pytest

from peiwu.jev import CHANGE_QUESTION_VERSION, JevReranker


class ChangeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def system_one(self, state, questions, model):
        assert set(questions) == {"support_0", "support_1"}
        answers = {
            "support_0": SimpleNamespace(type="noul", noul=0.91),
            "support_1": SimpleNamespace(type="noul", noul=0.22),
        }
        return SimpleNamespace(
            model=model,
            answers=answers,
            usage=SimpleNamespace(model_dump=lambda mode: {"input_tokens": 80, "output_tokens": 2}),
        )


def candidates():
    return [
        {"id": "change-a", "source_id": "change-a", "title": "变更 A", "locator": "L1",
         "text": "stu01 ACID 有效期发生变化", "sha256": "a" * 64, "kind": "synthetic",
         "external_model_allowed": True},
        {"id": "change-b", "source_id": "change-b", "title": "变更 B", "locator": "L2",
         "text": "cab_general 说明未变化", "sha256": "b" * 64, "kind": "synthetic",
         "external_model_allowed": True},
    ]


def test_change_review_only_prioritizes_human_review(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    result = JevReranker(client_factory=ChangeClient).rerank(
        "合成授权变更：哪些历史申请应优先人工复核？", candidates(),
        purpose="change_review", synthetic_claim=True, allow_live=True,
    )
    assert result["status"] == "ready"
    assert result["question_version"] == CHANGE_QUESTION_VERSION
    assert result["review_required"] is True
    assert result["candidates"][0]["jev_review_hint"] == "impact_signal"
    assert result["candidates"][0]["jev_impact_probability"] == 0.91
    assert all("action" not in item and "decision" not in item for item in result["candidates"])
    assert "decision" not in result


def test_change_review_requires_fixed_synthetic_claim_for_live(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    result = JevReranker(client_factory=ChangeClient).rerank(
        "任意变更", candidates(), purpose="change_review", allow_live=True,
    )
    assert result["code"] == "claim_not_authorized"
    assert result["request_count"] == 0


def test_change_review_is_safe_without_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    result = JevReranker().rerank("变更", candidates(), purpose="change_review")
    assert result["status"] == "unavailable"
    assert result["code"] == "not_configured"

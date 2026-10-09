from types import SimpleNamespace

from peiwu.jev import RELATION_QUESTION_VERSION, JevReranker


class RelationClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def system_one(self, state, questions, model):
        assert set(questions) == {"support_0", "support_1"}
        return SimpleNamespace(
            model=model,
            answers={
                "support_0": SimpleNamespace(type="noul", noul=0.93),
                "support_1": SimpleNamespace(type="noul", noul=0.18),
            },
            usage=SimpleNamespace(model_dump=lambda mode: {"input_tokens": 90, "output_tokens": 2}),
        )


def candidates():
    return [
        {"id": "relation-a", "source_id": "relation-a", "title": "授权记录", "locator": "L1",
         "text": "stu01 授权 ACID", "sha256": "a" * 64, "kind": "synthetic",
         "external_model_allowed": True, "relation_subject": "stu01",
         "relation_type": "authorized_for", "relation_object": "ACID"},
        {"id": "relation-b", "source_id": "relation-b", "title": "其他记录", "locator": "L2",
         "text": "cab_general 未变化", "sha256": "b" * 64, "kind": "synthetic",
         "external_model_allowed": True, "relation_subject": "stu01",
         "relation_type": "authorized_for", "relation_object": "ACID"},
    ]


def test_relation_review_stays_proposed_and_only_returns_support_signal(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    result = JevReranker(client_factory=RelationClient).rerank(
        "合成来源是否支持 proposed 关系：stu01 authorized_for ACID？", candidates(),
        purpose="relation_review", synthetic_claim=True, allow_live=True,
    )
    assert result["status"] == "ready"
    assert result["question_version"] == RELATION_QUESTION_VERSION
    assert result["review_required"] is True
    assert result["candidates"][0]["jev_relation_hint"] == "relation_support"
    assert result["candidates"][0]["jev_relation_probability"] == 0.93
    assert "approved" not in result
    assert "decision" not in result
    assert all(item.get("status") != "approved" for item in result["candidates"])


def test_relation_review_requires_synthetic_claim(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    result = JevReranker(client_factory=RelationClient).rerank(
        "任意关系", candidates(), purpose="relation_review", allow_live=True,
    )
    assert result["code"] == "claim_not_authorized"
    assert result["request_count"] == 0


def test_relation_review_without_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    result = JevReranker().rerank("关系", candidates(), purpose="relation_review")
    assert result["status"] == "unavailable"
    assert result["code"] == "not_configured"

import pytest

from ontolens.model_explain import build_request, extract_text, normalize_protocol


@pytest.mark.parametrize("protocol,path", [
    ("chat_completions", "/chat/completions"),
    ("responses", "/responses"),
    ("messages", "/messages"),
])
def test_model_protocol_builders_keep_explanation_separate(protocol, path):
    url, headers, body = build_request(protocol, "https://model.example/v1", "demo-model", "secret",
                                       "system", "user")
    assert url == "https://model.example/v1" + path
    assert body["model"] == "demo-model"
    assert "decision_check" not in str(body)
    if protocol == "messages":
        assert headers["x-api-key"] == "secret"
        assert body["messages"][0]["role"] == "user"
    elif protocol == "responses":
        assert headers["Authorization"] == "Bearer secret"
        assert body["input"][0]["role"] == "system"
    else:
        assert headers["Authorization"] == "Bearer secret"
        assert body["messages"][0]["role"] == "system"


@pytest.mark.parametrize("protocol,payload,expected", [
    ("chat_completions", {"choices": [{"message": {"content": "chat"}}]}, "chat"),
    ("responses", {"output_text": "response"}, "response"),
    ("responses", {"output": [{"content": [{"type": "output_text", "text": "response-block"}]}]}, "response-block"),
    ("messages", {"content": [{"type": "text", "text": "message"}]}, "message"),
])
def test_model_protocol_response_extractors(protocol, payload, expected):
    assert extract_text(protocol, payload) == expected


def test_model_protocol_rejects_unknown_value():
    assert normalize_protocol("response") == "responses"
    assert normalize_protocol("message") == "messages"
    with pytest.raises(ValueError):
        normalize_protocol("unknown")

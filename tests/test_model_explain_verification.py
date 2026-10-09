import argparse

import pytest

from scripts.verify_model_explain import configuration, local_url, synthetic_request


def test_model_explain_preflight_is_honest_without_configuration(monkeypatch):
    for name in ("PEIWU_MODEL_BASE_URL", "PEIWU_MODEL_NAME", "PEIWU_MODEL_API_KEY", "PEIWU_MODEL_PROTOCOL"):
        monkeypatch.delenv(name, raising=False)
    result = configuration()
    assert result["configured"] is False
    assert result["protocol"] == "chat_completions"
    assert result["live_request_sent"] is False


def test_model_explain_request_is_fixed_synthetic():
    request = synthetic_request()
    assert request["request_id"] == "MODEL-EXPLAIN-01"
    assert request["requester_id"] == "stu01"


@pytest.mark.parametrize("value", ["https://example.com", "http://localhost/api", "http://user:pass@localhost"])
def test_model_explain_url_rejects_nonlocal(value):
    with pytest.raises(argparse.ArgumentTypeError):
        local_url(value)

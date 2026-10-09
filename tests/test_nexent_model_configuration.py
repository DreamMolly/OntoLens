import argparse

import pytest

from scripts.configure_nexent_model import model_matches, model_payload, normalized_url, redacted_configuration
from scripts.verify_nexent import local_url


def test_model_configuration_requires_all_local_secret_inputs(monkeypatch):
    for name in ("ONTOLENS_MODEL_NAME", "ONTOLENS_MODEL_BASE_URL", "ONTOLENS_MODEL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="required"):
        model_payload()


def test_model_configuration_report_never_contains_secret_or_endpoint(monkeypatch):
    monkeypatch.setenv("ONTOLENS_MODEL_NAME", "synthetic-model")
    monkeypatch.setenv("ONTOLENS_MODEL_BASE_URL", "https://private.invalid/v1")
    monkeypatch.setenv("ONTOLENS_MODEL_API_KEY", "secret-value")
    payload = model_payload()
    report = redacted_configuration(payload)
    assert report["api_key_present"] is True
    assert report["base_url_present"] is True
    assert "secret-value" not in str(report)
    assert "private.invalid" not in str(report)


@pytest.mark.parametrize("url", ["https://user:secret@example.com/v1", "https://example.com/v1?token=secret",
                                 "https://example.com/v1#secret"])
def test_model_configuration_rejects_credentials_in_base_url(monkeypatch, url):
    monkeypatch.setenv("ONTOLENS_MODEL_NAME", "synthetic-model")
    monkeypatch.setenv("ONTOLENS_MODEL_BASE_URL", url)
    monkeypatch.setenv("ONTOLENS_MODEL_API_KEY", "secret-value")
    with pytest.raises(ValueError, match="must not contain"):
        model_payload()


def test_existing_model_must_match_name_provider_type_and_endpoint(monkeypatch):
    monkeypatch.setenv("ONTOLENS_MODEL_NAME", "synthetic-model")
    monkeypatch.setenv("ONTOLENS_MODEL_BASE_URL", "https://expected.invalid/v1/")
    monkeypatch.setenv("ONTOLENS_MODEL_API_KEY", "secret-value")
    expected = model_payload()
    actual = {key: expected[key] for key in ("display_name", "model_name", "model_factory", "model_type", "base_url")}
    actual["base_url"] = "https://expected.invalid/v1"
    assert model_matches(actual, expected)
    actual["base_url"] = "https://other.invalid/v1"
    assert not model_matches(actual, expected)


@pytest.mark.parametrize(("left", "right"), [
    ("http://localhost:8000/v1/", "http://host.docker.internal:8000/v1"),
    ("http://127.0.0.1:8000/v1", "http://host.docker.internal:8000/v1/"),
])
def test_model_endpoint_normalization_matches_nexent_container_rewrite(left, right):
    assert normalized_url(left) == normalized_url(right)


@pytest.mark.parametrize("value", ["https://example.com", "http://localhost/api", "http://user:pass@localhost"])
def test_model_configuration_refuses_nonlocal_nexent_url(value):
    with pytest.raises(argparse.ArgumentTypeError):
        local_url(value)

"""Keep every test independent of local model, account and workspace settings."""
import os

import pytest


@pytest.fixture(autouse=True)
def isolate_project_configuration(monkeypatch):
    for name in list(os.environ):
        if name.startswith(("ONTOLENS_", "PEIWU_", "TYPESAFE_", "MODEL_", "NEXENT_", "OPENAI_", "ANTHROPIC_")):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ONTOLENS_LOAD_ENV", "false")

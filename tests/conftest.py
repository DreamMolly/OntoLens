"""Keep every test independent of local model, account and workspace settings."""
import os
import secrets
import socket

import pytest


@pytest.fixture(autouse=True)
def isolate_project_configuration(monkeypatch):
    for name in list(os.environ):
        if name.startswith(("ONTOLENS_", "TYPESAFE_", "MODEL_", "NEXENT_", "OPENAI_", "ANTHROPIC_")):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ONTOLENS_LOAD_ENV", "false")


@pytest.fixture
def browser_listener():
    # Chromium blocks legacy service ports, including 10080.
    for _ in range(128):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            try:
                listener.bind(("127.0.0.1", 12000 + secrets.randbelow(48000)))
            except OSError:
                continue
            listener.listen(128)
            yield listener
            return
    raise RuntimeError("Unable to allocate a browser-safe loopback port")

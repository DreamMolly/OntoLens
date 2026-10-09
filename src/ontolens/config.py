"""Configuration loading for the OntoLens application.

The application has one configuration namespace. Process values take precedence
over values read from the project dotenv file, including an explicitly empty
process value.
"""
from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path


CONFIG_PREFIXES = ("ONTOLENS_", "TYPESAFE_")


def env_value(name: str, default=None, *, environment: Mapping[str, str] | None = None):
    settings = os.environ if environment is None else environment
    return settings.get("ONTOLENS_" + name, default)


def read_environment(path: Path) -> dict[str, str]:
    if env_value("LOAD_ENV", "true").lower() in {"0", "false", "no"} or not path.is_file():
        return {}
    result = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            name = name.strip()
            if name.startswith(CONFIG_PREFIXES):
                result[name] = value.strip().strip("\"'")
    return result


def load_environment(path: Path) -> None:
    present = set(os.environ)
    for name, value in read_environment(path).items():
        if name not in present:
            os.environ[name] = value

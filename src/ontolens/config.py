"""Configuration aliases for the OntoLens namespace migration.

An explicitly set ONTOLENS value, including an empty string, takes precedence
over PEIWU. Loading a dotenv file never overrides process configuration under
either alias; unset legacy configurations therefore keep working unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path


CONFIG_PREFIXES = ("ONTOLENS_", "PEIWU_", "TYPESAFE_", "NEXENT_")


def env_value(name: str, default=None, *, environment: Mapping[str, str] | None = None,
              aliases: tuple[str, ...] = ()):
    settings = os.environ if environment is None else environment
    for key in ("ONTOLENS_" + name, "PEIWU_" + name, *aliases):
        if key in settings:
            return settings[key]
    return default


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
        if name.startswith(("ONTOLENS_", "PEIWU_")):
            suffix = name.split("_", 1)[1]
            if "ONTOLENS_" + suffix in present or "PEIWU_" + suffix in present:
                continue
        elif name in present:
            continue
        os.environ[name] = value

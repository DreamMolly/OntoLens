from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        for name, content in sorted(entries.items()):
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, content)
    return output.getvalue()


def build_package(package: Path) -> bytes:
    agent_bytes = (package / "agent.json").read_bytes()
    config = json.loads(agent_bytes)
    root_key = str(config["agent_id"])
    if root_key not in config["agent_info"]:
        raise ValueError("agent_info must be indexed by the string form of agent_id")
    skill_names = set()
    for key, agent in config["agent_info"].items():
        if key != str(agent["agent_id"]) or not agent["name"].isidentifier():
            raise ValueError("Invalid Nexent agent identifier")
        if any(str(child) not in config["agent_info"] for child in agent["managed_agents"]):
            raise ValueError("Missing managed agent")
        skill_names.update(agent.get("skill_names") or [])
    entries = {"agent.json": agent_bytes}
    for name in sorted(skill_names):
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise ValueError("Invalid bundled skill name")
        skill_file = package / "skills" / name / "SKILL.md"
        if skill_file.is_symlink() or not skill_file.resolve().is_relative_to(package.resolve()):
            raise ValueError("Skill source must stay inside the package")
        entries[f"skills/{name}.zip"] = zip_bytes({"SKILL.md": skill_file.read_bytes()})
    return zip_bytes(entries)


def save_package(destination: Path, payload: bytes, backup_dir: Path) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    if destination.exists():
        previous = destination.read_bytes()
        if previous == payload:
            return digest
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / (hashlib.sha256(previous).hexdigest() + ".zip")
        if not backup.exists():
            with backup.open("xb") as output:
                output.write(previous)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/peiwu-nexent-agent.zip"))
    args = parser.parse_args()
    destination = (ROOT / args.output).resolve()
    if not destination.is_relative_to(ROOT) or destination.suffix.lower() != ".zip":
        parser.error("Output must be a ZIP inside the project")
    payload = build_package(ROOT / "nexent")
    digest = save_package(destination, payload, ROOT / ".runtime" / "package-backups")
    print(json.dumps({"output": str(destination), "sha256": digest, "bytes": len(payload)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

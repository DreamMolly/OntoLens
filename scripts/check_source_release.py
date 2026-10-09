"""Offline source allowlist and secret screening; never reads local .env files."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
import subprocess
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}\b"),
    re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
)
PRIVATE_SUFFIXES = {".pem", ".key", ".pfx", ".p12", ".db", ".sqlite", ".sqlite3"}
ARCHIVE_SUFFIXES = {".zip", ".7z", ".rar", ".tar", ".gz", ".tgz"}
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".git", ".venv", "node_modules"}


def is_link(path: Path) -> bool:
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def safe_path(root: Path, name: str) -> Path:
    normalized = name.replace("\\", "/")
    relative = PurePosixPath(normalized)
    if relative.is_absolute() or ".." in relative.parts or ":" in normalized or "\n" in name or "\r" in name:
        raise ValueError("Unsafe relative source path")
    path = root.joinpath(*relative.parts)
    for parent in [path, *path.parents]:
        if parent == root:
            break
        if (parent.exists() and is_link(parent)) or parent.is_symlink():
            raise ValueError("Symlinks and junctions are forbidden in source releases")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Source path escapes project")
    return path


def snapshot_validation(root: Path) -> None:
    report_path = safe_path(root, "artifacts/local-validation-report.json")
    original_report = report_path.read_bytes()
    report = json.loads(original_report.decode("utf-8"))
    checks = report.get("checks", [])
    required = {"pytest", "browser", "mcp", "assets", "jev", "pip", "javascript"}
    if report.get("passed") is not True or len(checks) != 7 or {c.get("name") for c in checks} != required:
        raise ValueError("Snapshot requires a successful seven-stage validation")
    run_name = PurePosixPath(report["run_dir"].replace("\\", "/")).name
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_name):
        raise ValueError("Invalid validation run directory")
    destination = "artifacts/source-validation/" + run_name
    copies = []
    for check in checks:
        original = safe_path(root, check["log"])
        if check.get("exit_code") != 0 or not check.get("command"):
            raise ValueError("Snapshot contains a failed validation stage")
        payload = original.read_bytes()
        if hashlib.sha256(payload).hexdigest() != check.get("log_sha256"):
            raise ValueError("Validation log hash mismatch")
        target = safe_path(root, destination + "/" + check["name"] + ".log")
        if target.exists() and target.read_bytes() != payload:
            raise ValueError("Refusing to overwrite a different validation log snapshot")
        copies.append((check, target, payload))
    # Check all input hashes and destinations before any write.
    for check, target, payload in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with target.open("xb") as stream:
                stream.write(payload)
        check["log"] = target.relative_to(root).as_posix()
    report["run_dir"] = destination
    backup = safe_path(root, ".runtime/source-release-backups/" + hashlib.sha256(original_report).hexdigest() + ".json")
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        with backup.open("xb") as stream:
            stream.write(original_report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(root: Path, policy: dict) -> list[str]:
    names = set()
    for name in policy["root_files"] + policy["evidence_files"]:
        if safe_path(root, name).is_file():
            names.add(name)
    for specification in policy["trees"]:
        base = safe_path(root, specification["path"])
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            relative = path.relative_to(root)
            if SKIP_PARTS.intersection(relative.parts) or any(".pre-" in part or ".backup" in part for part in relative.parts):
                continue
            name = relative.as_posix()
            if is_link(path):
                raise ValueError("Symlink or junction in included source tree: " + name)
            if path.is_file():
                if path.suffix.lower() in ARCHIVE_SUFFIXES:
                    raise ValueError("Accidental archive in source tree: " + name)
                if path.suffix.lower() in specification["suffixes"] or path.name in specification.get("names", []):
                    names.add(name)
    validation = safe_path(root, "artifacts/local-validation-report.json")
    if validation.exists():
        report = json.loads(validation.read_text(encoding="utf-8"))
        for row in report.get("checks", []):
            name = row.get("log", "").replace("\\", "/")
            if not name.startswith("artifacts/source-validation/") or not name.endswith(".log"):
                raise ValueError("Validation logs are local-only; run --snapshot-validation after final validation")
            path = safe_path(root, name)
            if hashlib.sha256(path.read_bytes()).hexdigest() != row.get("log_sha256"):
                raise ValueError("Source-validation log hash mismatch")
            names.add(name)
    missing = set(policy["required_files"]) - names
    if missing:
        raise ValueError("Required source files missing: " + ", ".join(sorted(missing)))
    return sorted(names)


def scan_bytes(payload: bytes, name: str) -> None:
    if any(pattern.search(payload) for pattern in SECRET_PATTERNS):
        raise ValueError("Potential credential detected; inspect locally: " + name)


def placeholder(value: str) -> bool:
    value = value.strip().strip("\"'")
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    return not value or value.upper().startswith(("REPLACE_", "YOUR_")) or value.startswith(("${", "<"))


def screen_configuration(payload: bytes, name: str) -> None:
    private_keys = {"api_key", "apikey", "access_token", "refresh_token", "secret_key", "private_key", "password", "authorization"}
    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower().replace("-", "_") in private_keys and isinstance(child, str) and not placeholder(child):
                    raise ValueError("Non-placeholder credential field; inspect locally: " + name)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    if name.endswith(".json") and name.startswith(("artifacts/", "nexent/")):
        visit(json.loads(payload.decode("utf-8")))
    if name.endswith(".env.example"):
        for line in payload.decode("utf-8").splitlines():
            match = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)", line)
            if match and re.search(r"(?:API_KEY|TOKEN|PASSWORD|SECRET)$", match[1]) and not placeholder(match[2]):
                raise ValueError("Non-placeholder credential in environment template: " + name)


def screen(root: Path, name: str, allowed_archives: set[str]) -> dict:
    path = safe_path(root, name)
    lowered = path.name.lower()
    if (re.search(r"(?:credentials?|secrets?|id_rsa|id_ed25519)", lowered)
            or path.suffix.lower() in PRIVATE_SUFFIXES
            or (lowered.startswith(".env") and lowered != ".env.example")
            or (lowered.endswith(".env") and not lowered.endswith(".env.example"))):
        raise ValueError("Sensitive filename is forbidden: " + name)
    if path.suffix.lower() in ARCHIVE_SUFFIXES and name not in allowed_archives:
        raise ValueError("Archive is not explicitly allowlisted: " + name)
    payload = path.read_bytes()
    scan_bytes(payload, name)
    screen_configuration(payload, name)
    if path.suffix.lower() in {".docx", ".pptx"}:
        with ZipFile(io.BytesIO(payload)) as archive:
            for member in archive.infolist():
                if ".." in PurePosixPath(member.filename).parts or member.filename.startswith("/"):
                    raise ValueError("Unsafe Office archive entry: " + name)
                if member.filename.endswith((".xml", ".rels", ".txt")):
                    scan_bytes(archive.read(member), name)
    if name == "artifacts/peiwu-nexent-agent.zip":
        config_bytes = (root / "nexent/agent.json").read_bytes()
        config = json.loads(config_bytes)
        skills = {skill for agent in config["agent_info"].values() for skill in agent.get("skill_names", [])}
        with ZipFile(io.BytesIO(payload)) as archive:
            if set(archive.namelist()) != {"agent.json", *(f"skills/{skill}.zip" for skill in skills)} or len(archive.namelist()) != 1 + len(skills):
                raise ValueError("Unexpected entry in allowlisted Nexent ZIP")
            if archive.read("agent.json") != config_bytes:
                raise ValueError("Nexent archive differs from source template")
            for skill in skills:
                if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill):
                    raise ValueError("Unsafe skill name in Nexent ZIP")
                with ZipFile(io.BytesIO(archive.read(f"skills/{skill}.zip"))) as nested:
                    if nested.namelist() != ["SKILL.md"] or nested.read("SKILL.md") != (root / "nexent/skills" / skill / "SKILL.md").read_bytes():
                        raise ValueError("Nexent bundled Skill differs from source")
    return {"path": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-validation", action="store_true", help="Copy exact stage logs and update only their report paths")
    parser.add_argument("--check-staged", action="store_true", help="Reject Git staged paths outside the checked source allowlist")
    parser.add_argument("--paths", action="store_true", help="Print checked relative paths, one per line")
    parser.add_argument("--manifest", type=Path, default=Path(".runtime/source-release-manifest.json"))
    args = parser.parse_args()
    try:
        policy = json.loads((ROOT / "scripts/source-release-policy.json").read_text(encoding="utf-8"))
        if args.snapshot_validation:
            snapshot_validation(ROOT)
        names = collect(ROOT, policy)
        rows = [screen(ROOT, name, set(policy["allowed_archives"])) for name in names]
        if args.check_staged:
            result = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"], cwd=ROOT, check=True, capture_output=True)
            staged = set(result.stdout.decode("utf-8").rstrip("\0").split("\0")) - {""}
            forbidden = staged - set(names)
            if forbidden:
                raise ValueError("Staged files outside allowlist: " + ", ".join(sorted(forbidden)))
            result = subprocess.run(["git", "diff", "--name-only", "-z"], cwd=ROOT, check=True, capture_output=True)
            changed = set(result.stdout.decode("utf-8").rstrip("\0").split("\0")) - {""}
            if staged.intersection(changed):
                raise ValueError("Staged content differs from screened working files; stage current files again")
        output = safe_path(ROOT, args.manifest.as_posix())
        if not output.relative_to(ROOT).as_posix().startswith(".runtime/"):
            raise ValueError("Manifest output must stay in .runtime")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"format": "peiwu-source-release-1", "scope": "Offline packaging screen; does not prove source authenticity or absence of all secrets", "files": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("\n".join(names) if args.paths else json.dumps({"passed": True, "files": len(rows), "bytes": sum(row["bytes"] for row in rows), "manifest": output.relative_to(ROOT).as_posix()}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

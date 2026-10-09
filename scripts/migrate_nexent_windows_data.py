from __future__ import annotations

import argparse
import hashlib
import json
import ntpath
import os
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".runtime" / "nexent-desktop-data"
BACKUP = ROOT / ".runtime" / "nexent-backups" / "20260924-112816-ec410ebb" / "manifest.json"
REPORT = ROOT / "artifacts" / "nexent-data-migration-report.json"
JOURNAL = ROOT / ".runtime" / "nexent-data-migration-state.json"
OLD_ROOT = "/mnt/f/Projects/2026ICT/.runtime/nexent-data"
COPY_HELPER_IMAGE = "docker.m.daocloud.io/postgres:15-alpine"
PROJECT_SERVICES = (
    "nexent-web", "nexent-northbound", "nexent-runtime", "nexent-mcp", "nexent-config",
    "nexent-data-process", "nexent-minio", "nexent-redis", "nexent-postgresql", "nexent-elasticsearch",
)
COPIES = (
    ("nexent-postgresql", "/var/lib/postgresql/data", "postgresql/data"),
    ("nexent-elasticsearch", "/usr/share/elasticsearch/data", "elasticsearch"),
    ("nexent-redis", "/data", "redis"),
    ("nexent-minio", "/data", "minio/data"),
    ("nexent-web", "/mnt/nexent-data/project-config", "project-config"),
    ("nexent-config", "/mnt/nexent-data/skills", "skills"),
    ("nexent-config", "/mnt/nexent-data/memory-provider-plugins", "memory-provider-plugins"),
    ("nexent-config", "/mnt/nexent-data/logs", "logs"),
    ("nexent-config", "/opt/ssh-keys", "openssh-server/ssh-keys"),
)
MOUNT_CONSUMERS = (
    ("nexent-postgresql", "/var/lib/postgresql/data", "postgresql/data"),
    ("nexent-elasticsearch", "/usr/share/elasticsearch/data", "elasticsearch"),
    ("nexent-redis", "/data", "redis"),
    ("nexent-minio", "/data", "minio/data"),
    ("nexent-web", "/mnt/nexent-data/project-config", "project-config"),
    ("nexent-config", "/mnt/nexent-data/skills", "skills"),
    ("nexent-runtime", "/mnt/nexent-data/skills", "skills"),
    ("nexent-mcp", "/mnt/nexent-data/skills", "skills"),
    ("nexent-northbound", "/mnt/nexent-data/skills", "skills"),
    ("nexent-config", "/mnt/nexent-data/memory-provider-plugins", "memory-provider-plugins"),
    ("nexent-runtime", "/mnt/nexent-data/memory-provider-plugins", "memory-provider-plugins"),
    ("nexent-config", "/mnt/nexent-data/logs", "logs"),
    ("nexent-runtime", "/mnt/nexent-data/logs", "logs"),
    ("nexent-mcp", "/mnt/nexent-data/logs", "logs"),
    ("nexent-northbound", "/mnt/nexent-data/logs", "logs"),
    ("nexent-data-process", "/mnt/nexent-data/logs", "logs"),
    ("nexent-config", "/opt/ssh-keys", "openssh-server/ssh-keys"),
    ("nexent-runtime", "/opt/ssh-keys", "openssh-server/ssh-keys"),
    ("nexent-mcp", "/opt/ssh-keys", "openssh-server/ssh-keys"),
    ("nexent-northbound", "/opt/ssh-keys", "openssh-server/ssh-keys"),
    ("nexent-config", "/opt/sync_user_supabase2pg.py", "scripts/sync_user_supabase2pg.py"),
)


def run(command: list[str], *, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True,
                          timeout=300, check=True)


def tree_record(path: Path) -> dict:
    entries = list(path.rglob("*"))
    symlinks = sorted(item.relative_to(path).as_posix() for item in entries if item.is_symlink())
    directories = sorted(item.relative_to(path).as_posix() for item in entries
                         if item.is_dir() and not item.is_symlink())
    files = sorted(item for item in entries if item.is_file() and not item.is_symlink())
    digest = hashlib.sha256()
    total = 0
    for item in files:
        relative = item.relative_to(path).as_posix()
        content_digest = hashlib.sha256(item.read_bytes()).hexdigest()
        size = item.stat().st_size
        digest.update(relative.encode("utf-8") + b"\0" + str(size).encode("ascii") + b"\0")
        digest.update(content_digest.encode("ascii") + b"\n")
        total += size
    structure = hashlib.sha256()
    for relative in directories:
        structure.update(b"D\0" + relative.encode("utf-8") + b"\n")
    for relative in symlinks:
        structure.update(b"L\0" + relative.encode("utf-8") + b"\n")
    return {"files": len(files), "bytes": total, "manifest_sha256": digest.hexdigest(),
            "directories": len(directories), "symlinks": len(symlinks),
            "structure_sha256": structure.hexdigest()}


def source_record(container: str, source: str) -> dict:
    quoted = shlex.quote(source)
    script = (f"cd {quoted} && find . -type f -print | LC_ALL=C sort | "
              "while IFS= read -r path; do hash=$(sha256sum \"$path\" | awk '{print $1}'); "
              "size=$(wc -c < \"$path\" | tr -d ' '); "
              "printf '%s\\t%s\\t%s\\n' \"$hash\" \"$size\" \"${path#./}\"; done")
    output = run(["docker", "run", "--rm", "--volumes-from", container, "--entrypoint", "sh",
                  COPY_HELPER_IMAGE, "-c", script]).stdout
    structure_script = (f"cd {quoted} && "
                        "find . -type d -print | LC_ALL=C sort | while IFS= read -r path; "
                        "do [ \"$path\" = . ] || printf 'D\\t%s\\n' \"${path#./}\"; done; "
                        "find . -type l -print | LC_ALL=C sort | while IFS= read -r path; "
                        "do printf 'L\\t%s\\n' \"${path#./}\"; done")
    structure_output = run(["docker", "run", "--rm", "--volumes-from", container, "--entrypoint", "sh",
                            COPY_HELPER_IMAGE, "-c", structure_script]).stdout
    digest = hashlib.sha256()
    count = 0
    total = 0
    for line in output.splitlines():
        content_hash, size_text, relative = line.split("\t", 2)
        size = int(size_text)
        digest.update(relative.encode("utf-8") + b"\0" + str(size).encode("ascii") + b"\0")
        digest.update(content_hash.encode("ascii") + b"\n")
        count += 1
        total += size
    directories = []
    symlinks = []
    structure = hashlib.sha256()
    for line in structure_output.splitlines():
        kind, relative = line.split("\t", 1)
        (directories if kind == "D" else symlinks).append(relative)
        structure.update(kind.encode("ascii") + b"\0" + relative.encode("utf-8") + b"\n")
    return {"files": count, "bytes": total, "manifest_sha256": digest.hexdigest(),
            "directories": len(directories), "symlinks": len(symlinks),
            "structure_sha256": structure.hexdigest()}


def inspect_mounts() -> dict[str, dict]:
    names = run(["docker", "ps", "-a", "--filter", "label=com.docker.compose.project=nexent",
                 "--format", "{{.Names}}"]).stdout.split()
    if not names:
        return {}
    result = run(["docker", "inspect", *names])
    containers = json.loads(result.stdout)
    return {item["Name"].lstrip("/"): item for item in containers}


def windows_path(value: str) -> str:
    return ntpath.normcase(ntpath.normpath(value.replace("/", "\\")))


def validate_compose_targets() -> None:
    environment = dict(os.environ)
    environment.update({"ROOT_DIR": TARGET.as_posix(),
                        "NEXENT_USER_DIR": (ROOT / ".runtime" / "nexent-home").as_posix()})
    compose = ["docker", "compose", "--project-name", "nexent", "--env-file",
               "third_party/nexent/deploy/env/.env", "--env-file", "nexent/windows.paths.env.example",
               "-f", "third_party/nexent/deploy/docker/compose/docker-compose.prod.yml",
               "-f", "nexent/windows.override.yaml", "config", "--format", "json"]
    config = json.loads(run(compose, environment=environment).stdout)
    service_by_container = {service.get("container_name", name): service
                            for name, service in config["services"].items()}
    for container, source, relative in MOUNT_CONSUMERS:
        expected = windows_path(str(TARGET / relative))
        volumes = service_by_container.get(container, {}).get("volumes", [])
        matching = [item for item in volumes if item.get("target") == source]
        if (len(matching) != 1 or matching[0].get("type") != "bind"
                or windows_path(matching[0].get("source", "")) != expected):
            raise ValueError(f"Compose target does not resolve to the migration directory: {container}:{source}")


def preflight() -> dict:
    target = TARGET.resolve()
    runtime = (ROOT / ".runtime").resolve()
    if not target.is_relative_to(runtime) or target == runtime:
        raise ValueError("Migration target must be a dedicated directory inside .runtime")
    if TARGET.exists():
        raise ValueError("Migration target already exists; refusing to merge or overwrite data")
    if not BACKUP.is_file():
        raise ValueError("The recorded PostgreSQL/Skill backup manifest is missing")
    if JOURNAL.is_file():
        journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
        if journal.get("state") not in {"copied", "recovered_after_failure"}:
            raise ValueError("An interrupted migration journal exists; run with --recover before retrying")
    containers = inspect_mounts()
    for container, source, relative in MOUNT_CONSUMERS:
        if container not in containers:
            continue
        inspected = containers.get(container) or {}
        labels = inspected.get("Config", {}).get("Labels") or {}
        if labels.get("com.docker.compose.project") != "nexent":
            raise ValueError(f"Container is not owned by the Nexent Compose project: {container}")
        matching = [mount for mount in inspected.get("Mounts", []) if mount.get("Destination") == source]
        expected_source = OLD_ROOT + "/" + relative.replace("\\", "/")
        if (len(matching) != 1 or matching[0].get("Type") != "bind"
                or matching[0].get("Source") != expected_source):
            raise ValueError(f"Expected source mount is missing: {container}:{source}")
    validate_compose_targets()
    return {"target": str(target), "backup_manifest": str(BACKUP.relative_to(ROOT)),
            "copy_count": len(COPIES), "compose_preflight": True}


def apply_migration(report: dict) -> None:
    listing = run(["docker", "ps", "-a", "--filter", "label=com.docker.compose.project=nexent",
                   "--format", "{{.Names}}"]).stdout.split()
    present = [name for name in PROJECT_SERVICES if name in listing]
    running = run(["docker", "ps", "--filter", "label=com.docker.compose.project=nexent",
                   "--format", "{{.Names}}"]).stdout.split()
    copied = []
    stopped = []
    try:
        JOURNAL.write_text(json.dumps({"state": "stopping", "target": str(TARGET),
                                       "original_running": running, "stopped": []}, indent=2), encoding="utf-8")
        for name in running:
            run(["docker", "stop", "--timeout", "30", name])
            stopped.append(name)
            JOURNAL.write_text(json.dumps({"state": "stopping", "target": str(TARGET),
                                           "original_running": running, "stopped": stopped}, indent=2), encoding="utf-8")
        source_records = {(container, source): source_record(container, source)
                          for container, source, _ in COPIES}
        if any(record["symlinks"] for record in source_records.values()):
            raise ValueError("Source data contains symlinks; use a service-native backup instead of filesystem copy")
        TARGET.mkdir(parents=True)
        for container, source, relative in COPIES:
            destination = TARGET / relative
            destination.mkdir(parents=True)
            run(["docker", "cp", f"{container}:{source}/.", str(destination)])
            target_record = tree_record(destination)
            if target_record != source_records[(container, source)]:
                raise ValueError(f"Source/target manifest mismatch: {container}:{source}")
            copied.append({"container": container, "source": source, "destination": relative,
                           "source_record": source_records[(container, source)],
                           "target_record": target_record})
        script_source = ROOT / "third_party" / "nexent" / "deploy" / "docker" / "assets" / "scripts" / "sync_user_supabase2pg.py"
        script_target = TARGET / "scripts" / "sync_user_supabase2pg.py"
        script_target.parent.mkdir(parents=True)
        shutil.copy2(script_source, script_target)
        copied.append({"source": str(script_source.relative_to(ROOT)),
                       "destination": str(script_target.relative_to(TARGET)),
                       "files": 1, "bytes": script_target.stat().st_size,
                       "sha256": hashlib.sha256(script_target.read_bytes()).hexdigest()})
        if not (TARGET / "postgresql" / "data" / "PG_VERSION").is_file():
            raise ValueError("Copied PostgreSQL data is missing PG_VERSION")
        report.update({"status": "source_target_manifests_verified", "stopped_containers": stopped,
                       "existing_containers": present, "copies": copied,
                       "target_tree": tree_record(TARGET)})
        JOURNAL.write_text(json.dumps({"state": "copied", "target": str(TARGET),
                                       "original_running": running, "stopped": stopped}, indent=2), encoding="utf-8")
    except BaseException as error:
        report.update({"status": "copy_failed", "stopped_containers": stopped,
                       "partial_target_exists": TARGET.exists(), "copy_error_type": type(error).__name__})
        recovery_errors = []
        for name in running:
            try:
                run(["docker", "start", name])
            except Exception as recovery_error:
                recovery_errors.append({"container": name, "error_type": type(recovery_error).__name__})
        if recovery_errors:
            report["recovery_errors"] = recovery_errors
            journal_state = "recovery_failed"
        else:
            journal_state = "recovered_after_failure"
        JOURNAL.write_text(json.dumps({"state": journal_state, "target": str(TARGET),
                                       "original_running": running, "stopped": stopped,
                                       "recovery_errors": recovery_errors}, indent=2), encoding="utf-8")
        raise


def recover_interrupted() -> dict:
    if not JOURNAL.is_file():
        raise ValueError("No migration journal exists")
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    names = journal.get("original_running")
    if (not isinstance(names, list) or not names
            or any(name not in PROJECT_SERVICES for name in names)):
        raise ValueError("Migration journal has an invalid container list")
    for name in names:
        run(["docker", "start", name])
    inspected = inspect_mounts()
    not_running = [name for name in names if inspected.get(name, {}).get("State", {}).get("Status") != "running"]
    if not_running:
        raise ValueError("Some recovered containers are not running: " + ", ".join(not_running))
    journal["state"] = "recovered_after_interruption"
    JOURNAL.write_text(json.dumps(journal, indent=2), encoding="utf-8")
    return {"status": journal["state"], "containers": names, "partial_target_exists": TARGET.exists()}


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="Stop Nexent containers and copy their bind-mounted data")
    action.add_argument("--recover", action="store_true", help="Restart containers from an interrupted migration journal")
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()
    output = args.output.resolve()
    artifacts = (ROOT / "artifacts").resolve()
    if (output.parent != artifacts or output.suffix.lower() != ".json"
            or not output.name.startswith("nexent-data-migration-")):
        parser.error("Report must be a nexent-data-migration-*.json file directly inside artifacts")
    report = {"status": "preflight_failed", "time": datetime.now(timezone.utc).isoformat(),
              "scope": "Cold copy from the existing Nexent binds to a new Windows F: project directory; no source deletion"}
    exit_code = 1
    try:
        if args.recover:
            report.update(recover_interrupted())
        else:
            report["preflight"] = preflight()
            report["status"] = "preflight_passed"
            if args.apply:
                apply_migration(report)
        exit_code = 0
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "error": report.get("error"),
                      "report": str(output)}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import ntpath
import subprocess
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .start_demo import elasticsearch_data_root, normalize_windows_path, StartupError
else:
    from start_demo import elasticsearch_data_root, normalize_windows_path, StartupError


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"nexent-elasticsearch", "nexent-postgresql", "nexent-redis", "nexent-minio",
            "nexent-config", "nexent-runtime", "nexent-mcp", "nexent-northbound", "nexent-web",
            "nexent-data-process"}
REQUIRED_HEALTH = {"nexent-elasticsearch", "nexent-redis", "nexent-postgresql", "nexent-data-process"}
REQUIRED_PROJECT_BINDS = {
    "nexent-elasticsearch": {"/usr/share/elasticsearch/data"},
    "nexent-postgresql": {"/var/lib/postgresql/data", "/docker-entrypoint-initdb.d/init.sql"},
    "nexent-redis": {"/data"},
    "nexent-minio": {"/data"},
    "nexent-web": {"/mnt/nexent-data/project-config"},
    "nexent-config": {"/mnt/nexent", "/opt/nexent/sql", "/mnt/nexent-data/skills",
                      "/mnt/nexent-data/memory-provider-plugins", "/mnt/nexent-data/logs",
                      "/opt/ssh-keys", "/opt/sync_user_supabase2pg.py"},
    "nexent-runtime": {"/mnt/nexent", "/opt/nexent/sql", "/mnt/nexent-data/skills",
                       "/mnt/nexent-data/memory-provider-plugins", "/mnt/nexent-data/logs", "/opt/ssh-keys"},
    "nexent-mcp": {"/mnt/nexent", "/opt/nexent/sql", "/mnt/nexent-data/skills",
                   "/mnt/nexent-data/logs", "/opt/ssh-keys"},
    "nexent-northbound": {"/mnt/nexent", "/opt/nexent/sql", "/mnt/nexent-data/skills",
                          "/mnt/nexent-data/logs", "/opt/ssh-keys"},
    "nexent-data-process": {"/mnt/nexent", "/opt/nexent/sql", "/mnt/nexent-data/logs"},
}


def is_project_windows_bind(source: str, root: str) -> bool:
    source = source.replace("\\", "/")
    for prefix in ("/run/desktop/mnt/host/", "/host_mnt/"):
        if source.startswith(prefix):
            relative = source[len(prefix):]
            if len(relative) > 2 and relative[1] == "/" and relative[0].isalpha():
                source = relative[0] + ":/" + relative[2:]
            break
    source = ntpath.normcase(ntpath.normpath(source))
    root = ntpath.normcase(ntpath.normpath(root))
    if not ntpath.splitdrive(source)[0] or not ntpath.isabs(source):
        return False
    try:
        return ntpath.commonpath([source, root]) == root
    except ValueError:
        return False


def audit_containers(containers: list[dict], root: str) -> dict:
    issues = []
    inventory = []
    names = {container["Name"].lstrip("/") for container in containers}
    for name in sorted(EXPECTED - names):
        issues.append({"code": "missing_service", "container": name})
    for container in containers:
        name = container["Name"].lstrip("/")
        state = container["State"]
        health = state.get("Health", {}).get("Status")
        restart_count = container.get("RestartCount", 0)
        if (state["Status"] != "running" or health in {"unhealthy", "starting"}
                or (name in REQUIRED_HEALTH and health != "healthy") or restart_count > 0):
            issues.append({"code": "service_not_ready", "container": name, "state": state["Status"],
                           "health": health, "restart_count": restart_count})
        mounts = []
        project_bind_destinations = set()
        for mount in container["Mounts"]:
            source = mount["Source"]
            mount_result = {"source": source, "destination": mount["Destination"], "type": mount["Type"]}
            if mount["Type"] == "volume":
                mount_result["classification"] = "existing_docker_volume_do_not_move"
            elif source == "/var/run/docker.sock":
                mount_result["classification"] = "upstream_docker_socket"
            elif mount["Type"] == "bind":
                safe = is_project_windows_bind(source, root)
                relocated = False
                if not safe and name == "nexent-elasticsearch" and mount["Destination"] == "/usr/share/elasticsearch/data":
                    try:
                        approved = elasticsearch_data_root(Path(root))
                        relocated = normalize_windows_path(source) == normalize_windows_path(str(approved))
                    except StartupError:
                        relocated = False
                    safe = relocated
                mount_result["classification"] = "project_windows_bind" if safe else "wrong_host_path"
                if relocated:
                    mount_result["classification"] = "verified_project_relocation"
                if safe:
                    project_bind_destinations.add(mount["Destination"])
                if not safe:
                    issues.append({"code": "wrong_host_path", "container": name, **mount_result})
            mounts.append(mount_result)
        for destination in sorted(REQUIRED_PROJECT_BINDS.get(name, set()) - project_bind_destinations):
            issues.append({"code": "missing_project_bind", "container": name, "destination": destination})
        ports = container.get("HostConfig", {}).get("PortBindings") or {}
        for port, bindings in ports.items():
            for binding in bindings or []:
                if binding.get("HostIp", "") not in {"127.0.0.1", "::1"}:
                    issues.append({"code": "non_loopback_port", "container": name, "container_port": port,
                                   "host_ip": binding.get("HostIp"), "host_port": binding.get("HostPort")})
        inventory.append({"name": name, "image": container["Config"]["Image"], "image_id": container["Image"],
                          "mounts": mounts, "ports": ports})
    return {"ready": not issues, "issues": issues, "containers": inventory,
            "policy": "read-only audit; no restart, migration, deletion, credential display or model calls"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/nexent-deployment-audit.json")
    args = parser.parse_args()
    output = args.output.resolve()
    artifacts = (ROOT / "artifacts").resolve()
    if (output.parent != artifacts or output.suffix.lower() != ".json"
            or not output.name.startswith("nexent-deployment-audit")):
        parser.error("Report must be a nexent-deployment-audit*.json file directly inside artifacts")
    try:
        listing = subprocess.run(["docker", "ps", "-a", "--filter", "label=com.docker.compose.project=nexent",
                                  "--format", "{{.ID}}"], capture_output=True, text=True, timeout=20, check=True)
        identifiers = listing.stdout.split()
        containers = []
        if identifiers:
            result = subprocess.run(["docker", "inspect", *identifiers], capture_output=True, text=True,
                                    timeout=20, check=True)
            containers = json.loads(result.stdout)
        report = audit_containers(containers, str(ROOT))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, AttributeError) as error:
        report = {"ready": False, "issues": [{"code": "docker_inspection_failed",
                                              "error_type": type(error).__name__}], "containers": [],
                  "policy": "read-only audit; current Docker state unavailable; no previous success reused"}
    report["time"] = datetime.now(timezone.utc).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ready": report["ready"], "issue_codes": sorted({issue["code"] for issue in report["issues"]}),
                      "report": str(output)}, ensure_ascii=False))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

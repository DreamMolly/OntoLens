from __future__ import annotations

import argparse
import json
import ntpath
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
PROJECT_NAME = "nexent"
WORKSPACE_VOLUME = "nexent-agent-workspace"
DOCKER_SOCKET = "/var/run/docker.sock"
EXPECTED_TOOLS = {
    "asset_recognition", "evidence_lookup", "graph_query", "candidate_suggestions",
    "evidence_rerank_jev", "decision_check", "candidate_review",
}
SERVICE_CONTAINERS = {
    "nexent-elasticsearch": "nexent-elasticsearch",
    "nexent-postgresql": "nexent-postgresql",
    "redis": "nexent-redis",
    "nexent-minio": "nexent-minio",
    "nexent-config": "nexent-config",
    "nexent-runtime": "nexent-runtime",
    "nexent-mcp": "nexent-mcp",
    "nexent-northbound": "nexent-northbound",
    "nexent-web": "nexent-web",
    "nexent-data-process": "nexent-data-process",
}
INFRA_SERVICES = ("nexent-elasticsearch", "nexent-postgresql", "redis", "nexent-minio")
APPLICATION_SERVICES = tuple(name for name in SERVICE_CONTAINERS if name not in INFRA_SERVICES)
REQUIRED_HEALTH = {
    "nexent-elasticsearch", "nexent-postgresql", "nexent-redis", "nexent-data-process",
}
COMPLETE_MIGRATION_STATUSES = {
    "copied_container_state_with_limits", "copied_and_verified", "source_target_manifests_verified",
}


class StartupError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True)
class MountSpec:
    kind: str
    source: str
    read_only: bool = False


def _posix(path: Path) -> str:
    return path.resolve().as_posix()


def elasticsearch_data_root(root: Path) -> Path:
    """Honor only the verified, project-specific relocation; never arbitrary bind paths."""
    original = root / ".runtime/nexent-desktop-data/elasticsearch"
    receipt = root / ".runtime/nexent-es-relocation.json"
    if not receipt.is_file():
        return original
    try:
        record = json.loads(receipt.read_text(encoding="utf-8"))
        target = Path("D:/NexentData/2026ICT/elasticsearch")
        if (record.get("status") != "copied_and_verified"
                or record.get("source") != _posix(original)
                or record.get("target") != target.as_posix()
                or not record.get("files") or not target.is_dir()):
            raise ValueError("invalid relocation")
        return target
    except (OSError, ValueError, TypeError) as error:
        raise StartupError("es_relocation_invalid", "Elasticsearch relocation receipt is invalid") from error


def expected_mounts(root: Path) -> dict[str, dict[str, MountSpec]]:
    data = root / ".runtime" / "nexent-desktop-data"
    home = root / ".runtime" / "nexent-home"
    sql = root / "third_party" / "nexent" / "deploy" / "sql"
    specs = {
        "nexent-elasticsearch": {
            "/usr/share/elasticsearch/data": MountSpec("bind", _posix(elasticsearch_data_root(root))),
        },
        "nexent-postgresql": {
            "/var/lib/postgresql/data": MountSpec("bind", _posix(data / "postgresql" / "data")),
            "/docker-entrypoint-initdb.d/init.sql": MountSpec("bind", _posix(sql / "init.sql"), True),
        },
        "redis": {"/data": MountSpec("bind", _posix(data / "redis"))},
        "nexent-minio": {"/data": MountSpec("bind", _posix(data / "minio" / "data"))},
        "nexent-web": {
            "/mnt/nexent-data/project-config": MountSpec("bind", _posix(data / "project-config")),
        },
        "nexent-data-process": {
            "/mnt/nexent": MountSpec("bind", _posix(home)),
            "/opt/nexent/sql": MountSpec("bind", _posix(sql), True),
            "/mnt/nexent-data/logs": MountSpec("bind", _posix(data / "logs")),
        },
        "nexent-config": {
            "/mnt/nexent": MountSpec("bind", _posix(home)),
            "/opt/nexent/sql": MountSpec("bind", _posix(sql), True),
            "/mnt/nexent-data/skills": MountSpec("bind", _posix(data / "skills")),
            "/mnt/nexent-data/memory-provider-plugins": MountSpec(
                "bind", _posix(data / "memory-provider-plugins")
            ),
            "/mnt/nexent-data/logs": MountSpec("bind", _posix(data / "logs")),
            "/opt/ssh-keys": MountSpec("bind", _posix(data / "openssh-server" / "ssh-keys"), True),
            "/opt/sync_user_supabase2pg.py": MountSpec(
                "bind", _posix(data / "scripts" / "sync_user_supabase2pg.py"), True
            ),
            DOCKER_SOCKET: MountSpec("bind", DOCKER_SOCKET, True),
        },
        "nexent-runtime": {
            "/mnt/nexent": MountSpec("bind", _posix(home)),
            "/mnt/nexent/workdir": MountSpec("volume", WORKSPACE_VOLUME),
            "/opt/nexent/sql": MountSpec("bind", _posix(sql), True),
            "/mnt/nexent-data/skills": MountSpec("bind", _posix(data / "skills")),
            "/mnt/nexent-data/memory-provider-plugins": MountSpec(
                "bind", _posix(data / "memory-provider-plugins")
            ),
            "/mnt/nexent-data/logs": MountSpec("bind", _posix(data / "logs")),
            "/opt/ssh-keys": MountSpec("bind", _posix(data / "openssh-server" / "ssh-keys"), True),
            DOCKER_SOCKET: MountSpec("bind", DOCKER_SOCKET, True),
        },
        "nexent-mcp": {
            "/mnt/nexent": MountSpec("bind", _posix(home)),
            "/opt/nexent/sql": MountSpec("bind", _posix(sql), True),
            "/mnt/nexent-data/skills": MountSpec("bind", _posix(data / "skills")),
            "/mnt/nexent-data/logs": MountSpec("bind", _posix(data / "logs")),
            "/opt/ssh-keys": MountSpec("bind", _posix(data / "openssh-server" / "ssh-keys"), True),
        },
        "nexent-northbound": {
            "/mnt/nexent": MountSpec("bind", _posix(home)),
            "/opt/nexent/sql": MountSpec("bind", _posix(sql), True),
            "/mnt/nexent-data/skills": MountSpec("bind", _posix(data / "skills")),
            "/mnt/nexent-data/logs": MountSpec("bind", _posix(data / "logs")),
            "/opt/ssh-keys": MountSpec("bind", _posix(data / "openssh-server" / "ssh-keys"), True),
            DOCKER_SOCKET: MountSpec("bind", DOCKER_SOCKET, True),
        },
    }
    return specs


def normalize_windows_path(value: str) -> str:
    value = value.replace("\\", "/")
    for prefix in ("/run/desktop/mnt/host/", "/host_mnt/"):
        if value.lower().startswith(prefix):
            tail = value[len(prefix):]
            if len(tail) > 2 and tail[0].isalpha() and tail[1] == "/":
                value = f"{tail[0]}:/{tail[2:]}"
            break
    return ntpath.normcase(ntpath.normpath(value))


def _load_json(path: Path, code: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StartupError(code, f"Required state is unreadable: {path.name}") from error
    if not isinstance(value, dict):
        raise StartupError(code, f"Required state has an invalid shape: {path.name}")
    return value


def _dotenv_paths(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise StartupError("invalid_windows_paths", "Windows path environment file is malformed")
        key, value = stripped.split("=", 1)
        if key in values:
            raise StartupError("invalid_windows_paths", "Windows path environment file has duplicate keys")
        values[key] = value.strip().strip('"').strip("'")
    return values


def validate_local_state(root: Path) -> tuple[dict, str]:
    runtime = root / ".runtime"
    data = runtime / "nexent-desktop-data"
    home = runtime / "nexent-home"
    token_path = runtime / "peiwu-mcp-token.txt"
    database = runtime / "workbench.sqlite3"
    pg_version = data / "postgresql" / "data" / "PG_VERSION"
    migration_path = root / "artifacts" / "nexent-data-migration-report.json"
    readiness_path = root / "artifacts" / "nexent-model-readiness.json"
    integration_path = root / "artifacts" / "nexent-integration-report.json"
    required = [data, home, token_path, database, pg_version, migration_path,
                readiness_path, integration_path,
                root / ".venv" / "Scripts" / "python.exe", root / "start-workbench.ps1",
                root / "third_party" / "nexent" / "deploy" / "env" / ".env",
                root / "third_party" / "nexent" / "deploy" / "docker" / "compose" / "docker-compose.prod.yml",
                root / "nexent" / "windows.paths.env.example", root / "nexent" / "windows.override.yaml"]
    missing = [item.name for item in required if not item.exists()]
    if missing:
        raise StartupError("local_state_incomplete", "Existing migrated deployment is incomplete")

    try:
        token = token_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as error:
        raise StartupError("mcp_token_unreadable", "Stored MCP token is unreadable") from error
    if not re.fullmatch(r"[A-Za-z0-9._~-]{32,256}", token):
        raise StartupError("mcp_token_invalid", "Stored MCP token is missing or malformed")
    if database.read_bytes()[:16] != b"SQLite format 3\x00":
        raise StartupError("workbench_database_invalid", "Existing workbench SQLite database is invalid")
    version = pg_version.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", version):
        raise StartupError("postgres_state_invalid", "Existing PostgreSQL state is invalid")

    migration = _load_json(migration_path, "migration_state_invalid")
    target = (migration.get("preflight") or {}).get("target", "")
    recovery = migration.get("post_copy_recovery") or {}
    restored = recovery.get("restored") or {}
    recovered = (recovery.get("deployment_audit_ready") is True
                 and recovery.get("model_recreated_and_bound") is True
                 and restored.get("mcp_records", 0) >= 1
                 and restored.get("visible_agents", 0) >= 1
                 and restored.get("skills", 0) >= 3
                 and str(recovery.get("post_migration_platform_verification", "")).startswith("platform_tools_"))
    if (migration.get("status") not in COMPLETE_MIGRATION_STATUSES
            or normalize_windows_path(target) != normalize_windows_path(_posix(data)) or not recovered):
        raise StartupError("migration_state_incomplete", "Migration and recovery state is not ready for startup")

    readiness = _load_json(readiness_path, "model_readiness_invalid")
    integration = _load_json(integration_path, "integration_state_invalid")
    agent_id = readiness.get("agent_id")
    model_ids = readiness.get("model_ids")
    integration_agent = integration.get("agent") or {}
    integration_mcp = integration.get("mcp") or {}
    mcp_id = integration_mcp.get("id")
    if (not isinstance(agent_id, int) or not isinstance(model_ids, list) or not model_ids
            or any(not isinstance(value, int) for value in model_ids)
            or readiness.get("agent_name") != "peiwu_compliance_review"
            or readiness.get("agent_available") is not True
            or readiness.get("deployment_audit_ready") is not True
            or integration.get("status") not in {
                "platform_tools_passed_model_pending", "platform_tools_and_synthetic_model_run_passed"
            }
            or integration_agent.get("agent_id") != agent_id
            or integration_agent.get("model_ids") != model_ids
            or not isinstance(mcp_id, int) or integration_mcp.get("health") != "healthy"
            or set(integration_mcp.get("tools") or []) != EXPECTED_TOOLS):
        raise StartupError("platform_identity_state_invalid", "Existing Agent and MCP identity evidence is inconsistent")

    path_env = _dotenv_paths(root / "nexent" / "windows.paths.env.example")
    expected_env = {"ROOT_DIR": _posix(data), "NEXENT_USER_DIR": _posix(home), "HOME": _posix(home)}
    if set(path_env) != set(expected_env) or any(
            normalize_windows_path(path_env[key]) != normalize_windows_path(value)
            for key, value in expected_env.items()):
        raise StartupError("invalid_windows_paths", "Windows path environment does not match the migrated deployment")

    file_targets = {"/docker-entrypoint-initdb.d/init.sql", "/opt/sync_user_supabase2pg.py"}
    for service_specs in expected_mounts(root).values():
        for target_path, spec in service_specs.items():
            if spec.kind != "bind" or spec.source == DOCKER_SOCKET:
                continue
            source = Path(spec.source)
            valid = source.is_file() if target_path in file_targets else source.is_dir()
            if not valid:
                raise StartupError("bind_source_missing", "A required migrated bind source is missing")
    return ({"postgres_version": version, "workbench_database": "present",
             "mcp_token": "present", "migration_status": migration["status"],
             "recovery_state": "verified", "agent_id": agent_id,
             "model_ids": model_ids, "mcp_id": mcp_id}, token)


def _canonical_volume(source: str, config: dict) -> str:
    definition = (config.get("volumes") or {}).get(source) or {}
    return str(definition.get("name") or source)


def validate_compose_config(config: dict, root: Path) -> dict:
    services = config.get("services")
    if not isinstance(services, dict):
        raise StartupError("compose_config_invalid", "Compose configuration has no service map")
    active = {name: value for name, value in services.items() if not value.get("profiles")}
    if set(active) != set(SERVICE_CONTAINERS):
        raise StartupError("compose_service_set_mismatch", "Compose active service set is not the approved Nexent deployment")
    profiled = set(services) - set(active)
    if not profiled.issubset({"nexent-openssh-server"}):
        raise StartupError("compose_service_set_mismatch", "Compose contains an unexpected profiled service")

    specs = expected_mounts(root)
    images: set[str] = set()
    for service_name, container_name in SERVICE_CONTAINERS.items():
        service = active[service_name]
        if service.get("container_name") != container_name:
            raise StartupError("compose_container_name_mismatch", f"Unexpected container name for {service_name}")
        image = service.get("image")
        if not isinstance(image, str) or not image:
            raise StartupError("compose_image_missing", f"Compose image is missing for {service_name}")
        images.add(image)
        actual_by_target: dict[str, dict] = {}
        for mount in service.get("volumes") or []:
            target = mount.get("target")
            if not isinstance(target, str) or target in actual_by_target:
                raise StartupError("compose_mount_invalid", f"Invalid mount target for {service_name}")
            actual_by_target[target] = mount
        if set(actual_by_target) != set(specs[service_name]):
            raise StartupError("compose_mount_set_mismatch", f"Unexpected mount set for {service_name}")
        for target, expected in specs[service_name].items():
            actual = actual_by_target[target]
            if actual.get("type") != expected.kind or bool(actual.get("read_only", False)) != expected.read_only:
                raise StartupError("compose_mount_mismatch", f"Mount type or mode differs for {service_name}:{target}")
            source = str(actual.get("source", ""))
            if expected.kind == "volume":
                matches = _canonical_volume(source, config) == expected.source
            elif expected.source == DOCKER_SOCKET:
                matches = source == DOCKER_SOCKET
            else:
                matches = normalize_windows_path(source) == normalize_windows_path(expected.source)
            if not matches:
                raise StartupError("compose_mount_mismatch", f"Mount source differs for {service_name}:{target}")

        ports = service.get("ports") or []
        expected_port = {"nexent-web": (3000, 13000), "nexent-northbound": (5013, 15013)}.get(service_name)
        if expected_port is None:
            if ports:
                raise StartupError("compose_port_mismatch", f"Unexpected published port for {service_name}")
        elif len(ports) != 1:
            raise StartupError("compose_port_mismatch", f"Required loopback port is missing for {service_name}")
        else:
            port = ports[0]
            target_port, published_port = expected_port
            if (port.get("host_ip") != "127.0.0.1" or int(port.get("target", -1)) != target_port
                    or str(port.get("published")) != str(published_port)
                    or port.get("protocol", "tcp") != "tcp"):
                raise StartupError("compose_port_mismatch", f"Published port differs for {service_name}")
    return {"services": sorted(active), "images": sorted(images), "mounts": specs,
            "data_root": _posix(root / ".runtime" / "nexent-desktop-data"),
            "nexent_home": _posix(root / ".runtime" / "nexent-home")}


def _existing_mount_source(mount: dict) -> str:
    return str(mount.get("Name") or mount.get("Source") or "")


def validate_existing_mounts(service: str, mounts: list[dict], plan: dict) -> None:
    expected = plan["mounts"][service]
    actual = {item.get("Destination"): item for item in mounts}
    if None in actual or len(actual) != len(mounts) or set(actual) != set(expected):
        raise StartupError("existing_mount_set_mismatch", f"Existing mount set differs for {service}")
    for target, spec in expected.items():
        mount = actual[target]
        if mount.get("Type") != spec.kind or bool(mount.get("RW", True)) == spec.read_only:
            raise StartupError("existing_mount_mismatch", f"Existing mount type or mode differs for {service}:{target}")
        source = _existing_mount_source(mount)
        if spec.kind == "volume":
            matches = source == spec.source
        elif spec.source == DOCKER_SOCKET:
            matches = source == DOCKER_SOCKET
        else:
            matches = normalize_windows_path(source) == normalize_windows_path(spec.source)
        if not matches:
            raise StartupError("existing_mount_mismatch", f"Existing mount source differs for {service}:{target}")


class Host:
    def run(self, args: list[str], **kwargs):
        return subprocess.run(args, **kwargs)

    def popen(self, args: list[str], **kwargs):
        return subprocess.Popen(args, **kwargs)

    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def monotonic(self) -> float:
        return time.monotonic()

    def port_open(self, hostname: str, port: int) -> bool:
        try:
            with socket.create_connection((hostname, port), timeout=1):
                return True
        except OSError:
            return False

    def get_json(self, url: str, timeout: float) -> dict:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def post_json(self, url: str, payload: dict, headers: dict[str, str], timeout: float) -> dict:
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                         headers={"Content-Type": "application/json", **headers}, method="POST")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))


def _hidden_process_options() -> dict:
    if os.name != "nt":
        return {"start_new_session": True}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {"startupinfo": startupinfo,
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}


NODE_MCP_PROBE = r"""
const http = require('node:http');
let token = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => token += chunk);
process.stdin.on('end', async () => {
  function post(payload, protocol) {
    return new Promise((resolve, reject) => {
      const body = JSON.stringify(payload);
      const headers = {'Content-Type':'application/json','Accept':'application/json, text/event-stream',
        'Authorization':'Bearer ' + token.trim(),'Content-Length':Buffer.byteLength(body)};
      if (protocol) headers['MCP-Protocol-Version'] = protocol;
      const request = http.request({hostname:'host.docker.internal',port:8765,path:'/mcp/',method:'POST',headers}, response => {
        const chunks=[]; response.on('data', chunk => chunks.push(chunk));
        response.on('end', () => {
          if (response.statusCode !== 200) return reject(new Error('HTTP ' + response.statusCode));
          try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); } catch (error) { reject(error); }
        });
      });
      request.on('error', reject); request.setTimeout(10000, () => request.destroy(new Error('timeout')));
      request.end(body);
    });
  }
  try {
    const initialized = await post({jsonrpc:'2.0',id:1,method:'initialize',params:{
      protocolVersion:'2025-03-26',capabilities:{},clientInfo:{name:'peiwu-startup',version:'1'}}});
    const protocol = initialized.result.protocolVersion;
    const listed = await post({jsonrpc:'2.0',id:2,method:'tools/list'}, protocol);
    process.stdout.write(JSON.stringify({protocol,tools:listed.result.tools.map(tool => tool.name).sort()}));
  } catch (error) { process.stderr.write('MCP probe failed\n'); process.exitCode=1; }
});
""".strip()


class DemoStartup:
    def __init__(self, root: Path = ROOT, host: Host | None = None, *, docker_cli: str | None = None,
                 environ: dict[str, str] | None = None, progress: Callable[[str], None] | None = None):
        self.root = root.resolve()
        self.host = host or Host()
        self.docker_cli = docker_cli
        self.environ = dict(os.environ if environ is None else environ)
        self.progress = progress or (lambda message: print(f"[demo-startup] {message}", flush=True))

    def _run(self, args: list[str], *, code: str, timeout: int = 60,
             env: dict[str, str] | None = None, input_text: str | None = None):
        try:
            result = self.host.run(args, capture_output=True, text=True, timeout=timeout,
                                   env=env, input=input_text)
        except (OSError, subprocess.SubprocessError) as error:
            raise StartupError(code, f"Command failed during {code}") from error
        if result.returncode != 0:
            raise StartupError(code, f"Command failed during {code}")
        return result

    def _find_docker(self) -> str:
        if self.docker_cli:
            return self.docker_cli
        found = self.host.which("docker")
        candidates = [Path(found)] if found else []
        program_files = self.environ.get("ProgramFiles")
        local_app = self.environ.get("LOCALAPPDATA")
        if program_files:
            candidates.append(Path(program_files) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe")
        if local_app:
            candidates.append(Path(local_app) / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe")
        for candidate in candidates:
            if candidate.is_file():
                self.docker_cli = str(candidate)
                return self.docker_cli
        raise StartupError("docker_cli_missing", "Installed Docker CLI was not found")

    def _docker_available(self, env: dict[str, str]) -> bool:
        try:
            result = self.host.run([self._find_docker(), "version", "--format", "{{.Server.Version}}"],
                                   capture_output=True, text=True, timeout=10, env=env)
            return result.returncode == 0 and bool(result.stdout.strip())
        except (OSError, subprocess.SubprocessError, StartupError):
            return False

    def _find_desktop(self) -> Path | None:
        candidates: list[Path] = []
        local_app = self.environ.get("LOCALAPPDATA")
        program_files = self.environ.get("ProgramFiles")
        if local_app:
            candidates.append(Path(local_app) / "Programs" / "DockerDesktop" / "Docker Desktop.exe")
        if program_files:
            candidates.append(Path(program_files) / "Docker" / "Docker" / "Docker Desktop.exe")
        docker = Path(self._find_docker())
        if docker.is_absolute():
            for parent in list(docker.parents)[:4]:
                candidates.append(parent / "Docker Desktop.exe")
        return next((path for path in candidates if path.is_file()), None)

    def _ensure_docker(self, apply: bool, env: dict[str, str]) -> bool:
        if self._docker_available(env):
            return False
        if not apply:
            raise StartupError("docker_unavailable", "Docker is unavailable; preflight did not start it")
        desktop = self._find_desktop()
        if desktop is None:
            raise StartupError("docker_desktop_missing", "Installed Docker Desktop executable was not found")
        self.progress("starting Docker Desktop")
        try:
            self.host.popen([str(desktop)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, cwd=str(self.root), **_hidden_process_options())
        except OSError as error:
            raise StartupError("docker_desktop_start_failed", "Docker Desktop could not be started") from error
        deadline = self.host.monotonic() + 120
        last_progress = self.host.monotonic()
        while self.host.monotonic() < deadline:
            if self._docker_available(env):
                return True
            now = self.host.monotonic()
            if now - last_progress >= 20:
                self.progress("waiting for Docker Desktop")
                last_progress = now
            self.host.sleep(2)
        raise StartupError("docker_start_timeout", "Docker Desktop did not become ready in time")

    def _compose_env(self) -> dict[str, str]:
        env = dict(self.environ)
        env["ROOT_DIR"] = _posix(self.root / ".runtime" / "nexent-desktop-data")
        env["NEXENT_USER_DIR"] = _posix(self.root / ".runtime" / "nexent-home")
        env["PEIWU_NEXENT_ES_DATA"] = _posix(elasticsearch_data_root(self.root))
        env.pop("COMPOSE_PROFILES", None)
        return env

    def _compose_base(self) -> list[str]:
        return [self._find_docker(), "compose", "--project-name", PROJECT_NAME,
                "--env-file", str(self.root / "third_party/nexent/deploy/env/.env"),
                "--env-file", str(self.root / "nexent/windows.paths.env.example"),
                "-f", str(self.root / "third_party/nexent/deploy/docker/compose/docker-compose.prod.yml"),
                "-f", str(self.root / "nexent/windows.override.yaml")]

    def _compose_plan(self, env: dict[str, str]) -> tuple[dict, dict]:
        result = self._run(self._compose_base() + ["config", "--format", "json"],
                           code="compose_config_failed", timeout=45, env=env)
        try:
            config = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError) as error:
            raise StartupError("compose_config_invalid", "Compose returned invalid configuration JSON") from error
        return config, validate_compose_config(config, self.root)

    def _validate_local_docker_resources(self, config: dict, plan: dict, env: dict[str, str]) -> None:
        self._run([self._find_docker(), "image", "inspect", *plan["images"]],
                  code="local_image_missing", timeout=45, env=env)
        result = self._run([self._find_docker(), "volume", "inspect", WORKSPACE_VOLUME],
                           code="workspace_volume_missing", timeout=20, env=env)
        try:
            volumes = json.loads(result.stdout)
            volume = volumes[0]
        except (json.JSONDecodeError, IndexError, KeyError, TypeError) as error:
            raise StartupError("workspace_volume_invalid", "Runtime workspace volume is invalid") from error
        labels = volume.get("Labels") or {}
        if volume.get("Name") != WORKSPACE_VOLUME or labels.get("com.docker.compose.project") not in {None, PROJECT_NAME}:
            raise StartupError("workspace_volume_foreign", "Runtime workspace volume belongs to another deployment")
        runtime_mount = next(item for item in config["services"]["nexent-runtime"].get("volumes", [])
                             if item.get("target") == "/mnt/nexent/workdir")
        if _canonical_volume(str(runtime_mount.get("source", "")), config) != WORKSPACE_VOLUME:
            raise StartupError("workspace_volume_foreign", "Compose runtime workspace volume is not approved")

    def _containers(self, plan: dict, env: dict[str, str]) -> dict[str, dict]:
        fmt = '{{.ID}}\t{{.Names}}\t{{.Label "com.docker.compose.project"}}\t{{.Label "com.docker.compose.service"}}'
        result = self._run([self._find_docker(), "ps", "-a", "--format", fmt],
                           code="container_listing_failed", timeout=20, env=env)
        rows = []
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) != 4:
                raise StartupError("container_listing_invalid", "Docker container listing is malformed")
            rows.append(tuple(parts))
        expected_by_container = {container: service for service, container in SERVICE_CONTAINERS.items()}
        for _, name, project, _ in rows:
            if name in expected_by_container and project != PROJECT_NAME:
                raise StartupError("foreign_container_name", f"Container name is owned by another project: {name}")
            if project == PROJECT_NAME and name not in expected_by_container:
                raise StartupError("unexpected_project_container", f"Unexpected container in Nexent project: {name}")
        project_rows = [row for row in rows if row[2] == PROJECT_NAME]
        if not project_rows:
            return {}
        inspected = self._run([self._find_docker(), "inspect", *[row[0] for row in project_rows]],
                              code="container_inspection_failed", timeout=30, env=env)
        try:
            values = json.loads(inspected.stdout)
        except (json.JSONDecodeError, TypeError) as error:
            raise StartupError("container_inspection_invalid", "Docker inspect returned invalid JSON") from error
        inventory: dict[str, dict] = {}
        for item in values:
            name = str(item.get("Name", "")).lstrip("/")
            service = expected_by_container.get(name)
            labels = (item.get("Config") or {}).get("Labels") or {}
            if (service is None or labels.get("com.docker.compose.project") != PROJECT_NAME
                    or labels.get("com.docker.compose.service") != service):
                raise StartupError("container_ownership_mismatch", "Existing container ownership does not match Compose")
            validate_existing_mounts(service, item.get("Mounts") or [], plan)
            state = item.get("State") or {}
            inventory[name] = {"id": item.get("Id") or item.get("ID"), "status": state.get("Status"),
                               "health": (state.get("Health") or {}).get("Status"),
                               "restart_count": item.get("RestartCount", 0)}
        return inventory

    def _probe_workbench(self) -> dict | None:
        if not self.host.port_open("127.0.0.1", 8765):
            return None
        try:
            payload = self.host.get_json("http://127.0.0.1:8765/api/status", 3)
        except (OSError, ValueError, KeyError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise StartupError("workbench_port_conflict", "Port 8765 is occupied by an unrecognized service") from error
        if (not isinstance(payload, dict) or payload.get("mode") != "synthetic_demo"
                or not isinstance(payload.get("active_id"), str) or not payload["active_id"]):
            raise StartupError("workbench_identity_mismatch", "Port 8765 is not the expected workbench")
        return {"state": "running", "mode": "synthetic_demo", "active_id": payload["active_id"]}

    def _host_mcp_probe(self, token: str) -> dict:
        headers = {"Accept": "application/json, text/event-stream", "Authorization": "Bearer " + token}
        try:
            initialized = self.host.post_json("http://127.0.0.1:8765/mcp/", {
                "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                    "protocolVersion": "2025-03-26", "capabilities": {},
                    "clientInfo": {"name": "peiwu-startup", "version": "1"},
                }}, headers, 10)
            protocol = initialized["result"]["protocolVersion"]
            listed = self.host.post_json("http://127.0.0.1:8765/mcp/", {
                "jsonrpc": "2.0", "id": 2, "method": "tools/list",
            }, {**headers, "MCP-Protocol-Version": protocol}, 10)
            tools = {item["name"] for item in listed["result"]["tools"]}
        except (OSError, KeyError, TypeError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise StartupError("workbench_mcp_auth_failed", "Stored token does not authenticate the running workbench") from error
        if tools != EXPECTED_TOOLS:
            raise StartupError("workbench_mcp_identity_mismatch", "Running workbench exposes an unexpected MCP tool set")
        return {"authenticated": True, "protocol": protocol, "tools": sorted(tools)}

    def _compose_up(self, services: tuple[str, ...], env: dict[str, str], label: str) -> None:
        self.progress(f"starting {label}")
        self._run(self._compose_base() + ["up", "-d", "--pull", "never", "--no-deps", *services],
                  code=f"compose_{label}_failed", timeout=180, env=env)

    def _wait_ready(self, plan: dict, env: dict[str, str], required_services: tuple[str, ...],
                    timeout: int, label: str) -> dict[str, dict]:
        required_names = {SERVICE_CONTAINERS[name] for name in required_services}
        deadline = self.host.monotonic() + timeout
        last_progress = self.host.monotonic()
        while True:
            inventory = self._containers(plan, env)
            pending = []
            for name in sorted(required_names):
                state = inventory.get(name)
                if state is None or state["status"] != "running":
                    pending.append(name)
                elif name in REQUIRED_HEALTH and state["health"] != "healthy":
                    pending.append(name)
                elif state["health"] in {"starting", "unhealthy"}:
                    pending.append(name)
            if not pending:
                self.progress(f"{label} ready")
                return inventory
            now = self.host.monotonic()
            if now >= deadline:
                raise StartupError("service_ready_timeout", f"{label} did not become ready in time")
            if now - last_progress >= 20:
                self.progress(f"waiting for {label}: {', '.join(pending)}")
                last_progress = now
            self.host.sleep(2)

    def _start_workbench(self, token: str, existing: dict | None) -> tuple[dict, dict]:
        if existing is not None:
            self.progress("reusing workbench")
            return existing, {"action": "reused"}
        powershell = self.host.which("pwsh") or self.host.which("powershell")
        if not powershell:
            raise StartupError("powershell_missing", "PowerShell executable was not found")
        log_dir = self.root / ".runtime" / "demo-startup"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "workbench.log"
        child_env = dict(self.environ)
        child_env["PEIWU_MCP_TOKEN"] = token
        args = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(self.root / "start-workbench.ps1"),
                "-BindHost", "0.0.0.0", "-Port", "8765"]
        self.progress("starting workbench")
        try:
            with log_path.open("ab") as log:
                process = self.host.popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                          cwd=str(self.root), env=child_env, **_hidden_process_options())
        except OSError as error:
            raise StartupError("workbench_start_failed", "Workbench process could not be started") from error
        deadline = self.host.monotonic() + 45
        while self.host.monotonic() < deadline:
            if process.poll() is not None:
                raise StartupError("workbench_exited", "Workbench exited before becoming ready")
            status = self._probe_workbench()
            if status is not None:
                self.progress("workbench ready")
                return status, {"action": "started", "pid": process.pid,
                                "log": str(log_path.relative_to(self.root))}
            self.host.sleep(1)
        raise StartupError("workbench_ready_timeout", "Workbench did not become ready in time")

    def _container_mcp_probe(self, token: str, env: dict[str, str]) -> dict:
        self.progress("verifying container-to-workbench MCP")
        result = self._run([self._find_docker(), "exec", "-i", "nexent-web", "node", "-e", NODE_MCP_PROBE],
                           code="container_mcp_probe_failed", timeout=30, env=env, input_text=token)
        try:
            payload = json.loads(result.stdout)
            tools = set(payload["tools"])
            protocol = payload["protocol"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise StartupError("container_mcp_probe_invalid", "Container MCP probe returned invalid JSON") from error
        if tools != EXPECTED_TOOLS or not isinstance(protocol, str) or not protocol:
            raise StartupError("container_mcp_identity_mismatch", "Container reached an unexpected MCP service")
        return {"reachable_from_container": True, "protocol": protocol, "tools": sorted(tools)}

    def _nexent_api_once(self, expected: dict) -> dict | None:
        try:
            agents = self.host.get_json("http://127.0.0.1:13000/api/agent/list", 8)
            mcp_list = self.host.get_json("http://127.0.0.1:13000/api/mcp/list", 8)
        except (OSError, ValueError, KeyError, urllib.error.URLError, json.JSONDecodeError):
            return None
        if not isinstance(agents, list) or not isinstance(mcp_list, dict):
            return None
        matching_agents = [item for item in agents if item.get("name") == "peiwu_compliance_review"]
        matching_mcp = [item for item in mcp_list.get("remote_mcp_server_list", [])
                        if item.get("remote_mcp_server_name") == "peiwu-local"]
        if not matching_agents or not matching_mcp:
            return None
        if len(matching_agents) != 1 or len(matching_mcp) != 1:
            raise StartupError("nexent_identity_mismatch", "Nexent contains duplicate Peiwu Agent or MCP records")
        agent = matching_agents[0]
        mcp = matching_mcp[0]
        if (agent.get("agent_id") != expected["agent_id"]
                or agent.get("model_ids") != expected["model_ids"]
                or mcp.get("mcp_id") != expected["mcp_id"]):
            raise StartupError("nexent_identity_mismatch", "Nexent Agent or MCP identity differs from restored state")
        if agent.get("is_available") is not True or mcp.get("enabled") is not True:
            return None
        try:
            health = self.host.get_json(
                f"http://127.0.0.1:13000/api/mcp/healthcheck?mcp_id={expected['mcp_id']}", 15
            )
        except (OSError, ValueError, KeyError, urllib.error.URLError, json.JSONDecodeError):
            return None
        if (health.get("data") or {}).get("health_status") != "healthy":
            return None
        return {"agent": {"id": expected["agent_id"], "model_ids": expected["model_ids"],
                          "available": True},
                "mcp": {"id": expected["mcp_id"], "health": "healthy"}}

    def _wait_nexent_api(self, expected: dict, timeout: int = 120) -> dict:
        self.progress("verifying Nexent Agent and MCP readiness")
        deadline = self.host.monotonic() + timeout
        last_progress = self.host.monotonic()
        while True:
            result = self._nexent_api_once(expected)
            if result is not None:
                self.progress("Nexent API ready")
                return result
            now = self.host.monotonic()
            if now >= deadline:
                raise StartupError("nexent_api_ready_timeout", "Nexent Agent and MCP API did not become ready in time")
            if now - last_progress >= 20:
                self.progress("waiting for Nexent Agent and MCP API")
                last_progress = now
            self.host.sleep(2)

    def execute(self, apply: bool = False) -> dict:
        self.progress("checking existing local state")
        local_state, token = validate_local_state(self.root)
        workbench_before = self._probe_workbench()
        host_mcp = self._host_mcp_probe(token) if workbench_before is not None else None
        env = self._compose_env()
        home_before = self.environ.get("HOME")
        if env.get("HOME") != home_before:
            raise StartupError("home_environment_changed", "Startup must not change HOME")
        docker_started = self._ensure_docker(apply, env)
        self.progress("validating Compose configuration")
        config, plan = self._compose_plan(env)
        self._validate_local_docker_resources(config, plan, env)
        before = self._containers(plan, env)
        early_container_mcp = None
        if (apply and workbench_before is not None
                and before.get("nexent-web", {}).get("status") == "running"):
            early_container_mcp = self._container_mcp_probe(token, env)
        report = {"mode": "apply" if apply else "preflight", "ready": True,
                  "local_state": local_state,
                  "compose": {"services": plan["services"], "data_root": plan["data_root"],
                              "elasticsearch_data_root": _posix(elasticsearch_data_root(self.root)),
                              "nexent_home": plan["nexent_home"],
                              "ports": {"nexent-web": "127.0.0.1:13000->3000",
                                        "nexent-northbound": "127.0.0.1:15013->5013"}},
                  "docker": {"available": True, "desktop_started": docker_started},
                  "workbench": workbench_before or {"state": "stopped"},
                  "containers": {"before": before}}
        if host_mcp is not None:
            report["workbench"]["mcp_authenticated"] = True
        if not apply:
            report["status"] = "preflight_ready"
            report["policy"] = "read-only preflight; no Docker or workbench mutation"
            return report

        self._compose_up(INFRA_SERVICES, env, "infrastructure")
        self._wait_ready(plan, env, INFRA_SERVICES, 180, "infrastructure")
        self._compose_up(APPLICATION_SERVICES, env, "application")
        after = self._wait_ready(plan, env, tuple(SERVICE_CONTAINERS), 300, "application")
        status, workbench_action = self._start_workbench(token, workbench_before)
        if (early_container_mcp is not None and before.get("nexent-web", {}).get("id")
                == after.get("nexent-web", {}).get("id")):
            mcp = early_container_mcp
        else:
            mcp = self._container_mcp_probe(token, env)
        nexent_api = self._wait_nexent_api(local_state)
        before_ids = {name: value["id"] for name, value in before.items()}
        after_ids = {name: value["id"] for name, value in after.items()}
        report["containers"].update({
            "after": after,
            "reused": sorted(name for name in after_ids if before_ids.get(name) == after_ids[name]),
            "recreated": sorted(name for name in after_ids if name in before_ids and before_ids[name] != after_ids[name]),
            "created": sorted(name for name in after_ids if name not in before_ids),
        })
        report["workbench"] = {**status, **workbench_action}
        report["mcp"] = mcp
        report["nexent_api"] = nexent_api
        report["status"] = "ready"
        report["policy"] = "existing local deployment only; no pull, build, migration, token change or model call"
        return report


def write_report(report: dict, root: Path = ROOT) -> Path:
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    mode = report.get("mode", "failed")
    candidate = artifacts / f"demo-startup-{stamp}-{mode}.json"
    sequence = 0
    while True:
        path = candidate if sequence == 0 else artifacts / f"demo-startup-{stamp}-{mode}-{sequence}.json"
        try:
            with path.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
            return path
        except FileExistsError:
            sequence += 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight or start the existing migrated Peiwu demo")
    parser.add_argument("--apply", action="store_true", help="Start the existing Docker services and workbench")
    args = parser.parse_args(argv)
    mode = "apply" if args.apply else "preflight"
    manager = DemoStartup()
    try:
        report = manager.execute(args.apply)
        exit_code = 0
    except StartupError as error:
        report = {"mode": mode, "status": "failed", "ready": False,
                  "issues": [{"code": error.code, "message": error.safe_message}],
                  "policy": "failed closed; credentials and command output omitted"}
        exit_code = 1
    except Exception as error:
        report = {"mode": mode, "status": "failed", "ready": False,
                  "issues": [{"code": "unexpected_error", "error_type": type(error).__name__}],
                  "policy": "failed closed; credentials and command output omitted"}
        exit_code = 1
    report["time"] = datetime.now(timezone.utc).isoformat()
    path = write_report(report)
    print(json.dumps({"status": report["status"], "ready": report["ready"],
                      "issue_codes": [item["code"] for item in report.get("issues", [])],
                      "report": str(path)}, ensure_ascii=False), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

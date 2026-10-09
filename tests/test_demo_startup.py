import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import start_demo


TOKEN = "a" * 64


def test_elasticsearch_relocation_rejects_unverified_or_arbitrary_target(tmp_path):
    original = tmp_path / ".runtime/nexent-desktop-data/elasticsearch"
    assert start_demo.elasticsearch_data_root(tmp_path) == original
    receipt = tmp_path / ".runtime/nexent-es-relocation.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps({"status": "copied_and_verified", "source": original.as_posix(),
                                   "target": "C:/unrelated", "files": [{"path": "one"}]}))
    with pytest.raises(start_demo.StartupError, match="relocation receipt"):
        start_demo.elasticsearch_data_root(tmp_path)


def prepare_root(root: Path) -> None:
    files = [
        root / ".venv/Scripts/python.exe",
        root / "start-workbench.ps1",
        root / "third_party/nexent/deploy/env/.env",
        root / "third_party/nexent/deploy/docker/compose/docker-compose.prod.yml",
        root / "nexent/windows.override.yaml",
    ]
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder", encoding="utf-8")
    data = root / ".runtime/nexent-desktop-data"
    home = root / ".runtime/nexent-home"
    home.mkdir(parents=True)
    for service_specs in start_demo.expected_mounts(root).values():
        for target, spec in service_specs.items():
            if spec.kind != "bind" or spec.source == start_demo.DOCKER_SOCKET:
                continue
            path = Path(spec.source)
            if target in {"/docker-entrypoint-initdb.d/init.sql", "/opt/sync_user_supabase2pg.py"}:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("existing", encoding="utf-8")
            else:
                path.mkdir(parents=True, exist_ok=True)
    (data / "postgresql/data/PG_VERSION").write_text("15\n", encoding="ascii")
    (root / ".runtime/ontolens-mcp-token.txt").write_text(TOKEN, encoding="utf-8")
    (root / ".runtime/workbench.sqlite3").write_bytes(b"SQLite format 3\x00" + b"\x00" * 64)
    paths = root / "nexent/windows.paths.env.example"
    paths.write_text(
        f"ROOT_DIR={data.resolve().as_posix()}\n"
        f"NEXENT_USER_DIR={home.resolve().as_posix()}\n"
        f"HOME={home.resolve().as_posix()}\n",
        encoding="utf-8",
    )
    report = {
        "status": "copied_container_state_with_limits",
        "preflight": {"target": str(data.resolve())},
        "post_copy_recovery": {
            "deployment_audit_ready": True,
            "model_recreated_and_bound": True,
            "restored": {"mcp_records": 1, "visible_agents": 1, "skills": 3},
            "post_migration_platform_verification": "platform_tools_and_synthetic_model_run_passed",
        },
    }
    artifact = root / "artifacts/nexent-data-migration-report.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps(report), encoding="utf-8")
    (root / "artifacts/nexent-model-readiness.json").write_text(json.dumps({
        "agent_id": 1, "agent_name": "ontolens_compliance_review", "model_ids": [1],
        "agent_available": True, "deployment_audit_ready": True,
    }), encoding="utf-8")
    (root / "artifacts/nexent-integration-report.json").write_text(json.dumps({
        "status": "platform_tools_and_synthetic_model_run_passed",
        "agent": {"agent_id": 1, "model_ids": [1]},
        "mcp": {"id": 1, "health": "healthy", "tools": sorted(start_demo.EXPECTED_TOOLS)},
    }), encoding="utf-8")


def compose_config(root: Path) -> dict:
    services = {}
    for service, container in start_demo.SERVICE_CONTAINERS.items():
        volumes = []
        for target, spec in start_demo.expected_mounts(root)[service].items():
            source = "nexent_agent_workspace" if spec.kind == "volume" else spec.source
            volumes.append({"type": spec.kind, "source": source, "target": target,
                            "read_only": spec.read_only})
        item = {"container_name": container, "image": f"example/{service}:fixed", "volumes": volumes}
        if service == "nexent-web":
            item["ports"] = [{"host_ip": "127.0.0.1", "target": 3000,
                              "published": "13000", "protocol": "tcp"}]
        if service == "nexent-northbound":
            item["ports"] = [{"host_ip": "127.0.0.1", "target": 5013,
                              "published": "15013", "protocol": "tcp"}]
        services[service] = item
    services["nexent-openssh-server"] = {
        "container_name": "nexent-openssh-server", "image": "example/ssh:fixed", "profiles": ["terminal"]
    }
    return {"services": services,
            "volumes": {"nexent_agent_workspace": {"name": start_demo.WORKSPACE_VOLUME}}}


def inspected_containers(root: Path, *, old_path: bool = False) -> list[dict]:
    values = []
    for service, container in start_demo.SERVICE_CONTAINERS.items():
        mounts = []
        for target, spec in start_demo.expected_mounts(root)[service].items():
            source = spec.source
            if old_path and target == "/usr/share/elasticsearch/data":
                source = "/mnt/f/Projects/2026ICT/.runtime/nexent-data/elasticsearch"
            mount = {"Type": spec.kind, "Source": source, "Destination": target,
                     "RW": not spec.read_only}
            if spec.kind == "volume":
                mount["Name"] = spec.source
                mount["Source"] = "/var/lib/docker/volumes/nexent-agent-workspace/_data"
            mounts.append(mount)
        health = "healthy" if container in start_demo.REQUIRED_HEALTH else None
        values.append({"Id": f"id-{container}", "Name": "/" + container,
                       "Config": {"Labels": {"com.docker.compose.project": "nexent",
                                              "com.docker.compose.service": service}},
                       "State": {"Status": "running", **({"Health": {"Status": health}} if health else {})},
                       "RestartCount": 0, "Mounts": mounts})
    return values


class FakeProcess:
    def __init__(self, pid=4242):
        self.pid = pid

    def poll(self):
        return None


class FakeHost:
    def __init__(self, root: Path, *, workbench_running=False, docker_ready=True,
                 containers=None, foreign_row=None):
        self.root = root
        self.config = compose_config(root)
        self.container_values = containers if containers is not None else inspected_containers(root)
        self.workbench_running = workbench_running
        self.docker_ready = docker_ready
        self.foreign_row = foreign_row
        self.commands = []
        self.popen_calls = []
        self.clock = 0.0

    def run(self, args, **kwargs):
        self.commands.append((list(args), kwargs))
        if len(args) > 1 and args[1] == "version":
            return SimpleNamespace(returncode=0 if self.docker_ready else 1,
                                   stdout="29.8.0\n" if self.docker_ready else "", stderr="")
        if "compose" in args and "config" in args:
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.config), stderr="")
        if len(args) > 2 and args[1:3] == ["image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout="[]", stderr="")
        if len(args) > 2 and args[1:3] == ["volume", "inspect"]:
            payload = [{"Name": start_demo.WORKSPACE_VOLUME,
                        "Labels": {"com.docker.compose.project": "nexent"}}]
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
        if len(args) > 2 and args[1:3] == ["ps", "-a"]:
            rows = [f"{item['Id']}\t{item['Name'].lstrip('/')}\tnexent\t"
                    f"{item['Config']['Labels']['com.docker.compose.service']}"
                    for item in self.container_values]
            if self.foreign_row:
                rows.append(self.foreign_row)
            return SimpleNamespace(returncode=0, stdout="\n".join(rows), stderr="")
        if len(args) > 1 and args[1] == "inspect":
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.container_values), stderr="")
        if "compose" in args and "up" in args:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(args) > 1 and args[1] == "exec":
            payload = {"protocol": "2025-03-26", "tools": sorted(start_demo.EXPECTED_TOOLS)}
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
        raise AssertionError(f"Unexpected command: {args}")

    def popen(self, args, **kwargs):
        self.popen_calls.append((list(args), kwargs))
        if str(args[0]).endswith("Docker Desktop.exe"):
            self.docker_ready = True
        else:
            self.workbench_running = True
        return FakeProcess()

    def which(self, name):
        return "pwsh.exe" if name == "pwsh" else None

    def sleep(self, seconds):
        self.clock += seconds

    def monotonic(self):
        return self.clock

    def port_open(self, hostname, port):
        return self.workbench_running

    def get_json(self, url, timeout):
        if url.endswith("/api/status"):
            return {"mode": "synthetic_demo", "active_id": "demo-initial"}
        if url.endswith("/api/agent/list"):
            return [{"agent_id": 1, "name": "ontolens_compliance_review", "model_ids": [1],
                     "is_available": True}]
        if url.endswith("/api/mcp/list"):
            return {"remote_mcp_server_list": [{"mcp_id": 1, "remote_mcp_server_name": "ontolens-local",
                                                "enabled": True}]}
        if "/api/mcp/healthcheck?" in url:
            return {"data": {"health_status": "healthy"}}
        raise AssertionError(f"Unexpected URL: {url}")

    def post_json(self, url, payload, headers, timeout):
        if payload["method"] == "initialize":
            return {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26"}}
        if payload["method"] == "tools/list":
            return {"jsonrpc": "2.0", "id": 2,
                    "result": {"tools": [{"name": name} for name in sorted(start_demo.EXPECTED_TOOLS)]}}
        raise AssertionError(payload)


def test_compose_rejects_old_mnt_f_and_non_loopback_paths(tmp_path):
    prepare_root(tmp_path)
    config = compose_config(tmp_path)
    es = config["services"]["nexent-elasticsearch"]["volumes"][0]
    es["source"] = "/mnt/f/Projects/2026ICT/.runtime/nexent-data/elasticsearch"
    with pytest.raises(start_demo.StartupError, match="Mount source differs"):
        start_demo.validate_compose_config(config, tmp_path)


def test_compose_protects_runtime_workspace_volume_and_docker_socket(tmp_path):
    prepare_root(tmp_path)
    config = compose_config(tmp_path)
    runtime = config["services"]["nexent-runtime"]
    workspace = next(item for item in runtime["volumes"] if item["target"] == "/mnt/nexent/workdir")
    workspace["source"] = "foreign_shared_volume"
    with pytest.raises(start_demo.StartupError, match="Mount source differs"):
        start_demo.validate_compose_config(config, tmp_path)
    config = compose_config(tmp_path)
    socket_mount = next(item for item in config["services"]["nexent-config"]["volumes"]
                        if item["target"] == start_demo.DOCKER_SOCKET)
    socket_mount["source"] = "//./pipe/docker_engine"
    with pytest.raises(start_demo.StartupError, match="Mount source differs"):
        start_demo.validate_compose_config(config, tmp_path)


def test_northbound_keeps_container_5013_but_publishes_loopback_15013(tmp_path):
    prepare_root(tmp_path)
    config = compose_config(tmp_path)
    start_demo.validate_compose_config(config, tmp_path)
    config["services"]["nexent-northbound"]["ports"][0]["published"] = "5013"
    with pytest.raises(start_demo.StartupError, match="Published port differs"):
        start_demo.validate_compose_config(config, tmp_path)


def test_existing_container_mount_change_is_refused_instead_of_recreated(tmp_path):
    prepare_root(tmp_path)
    plan = start_demo.validate_compose_config(compose_config(tmp_path), tmp_path)
    es = inspected_containers(tmp_path, old_path=True)[0]
    with pytest.raises(start_demo.StartupError, match="Existing mount source differs"):
        start_demo.validate_existing_mounts("nexent-elasticsearch", es["Mounts"], plan)


def test_preflight_is_read_only_and_overrides_stale_paths_without_changing_home(tmp_path):
    prepare_root(tmp_path)
    host = FakeHost(tmp_path)
    caller = {"HOME": "C:/Users/example", "ROOT_DIR": "/mnt/f/stale", "NEXENT_USER_DIR": "/mnt/f/stale-home"}
    report = start_demo.DemoStartup(tmp_path, host, docker_cli="docker.exe", environ=caller,
                                    progress=lambda _: None).execute(False)
    assert report["status"] == "preflight_ready"
    assert report["workbench"] == {"state": "stopped"}
    assert not host.popen_calls
    assert all("up" not in args and "exec" not in args for args, _ in host.commands)
    config_env = next(kwargs["env"] for args, kwargs in host.commands if "config" in args)
    assert config_env["ROOT_DIR"].endswith("/.runtime/nexent-desktop-data")
    assert config_env["NEXENT_USER_DIR"].endswith("/.runtime/nexent-home")
    assert config_env["HOME"] == caller["HOME"]
    assert TOKEN not in json.dumps(report)


def test_apply_reuses_containers_and_workbench_and_keeps_token_off_argv(tmp_path):
    prepare_root(tmp_path)
    host = FakeHost(tmp_path, workbench_running=True)
    report = start_demo.DemoStartup(tmp_path, host, docker_cli="docker.exe", environ={"HOME": "C:/Users/example"},
                                    progress=lambda _: None).execute(True)
    assert report["status"] == "ready"
    assert report["nexent_api"] == {"agent": {"id": 1, "model_ids": [1], "available": True},
                                     "mcp": {"id": 1, "health": "healthy"}}
    assert report["workbench"]["action"] == "reused"
    assert not host.popen_calls
    assert set(report["containers"]["reused"]) == set(start_demo.SERVICE_CONTAINERS.values())
    assert report["containers"]["created"] == []
    assert report["containers"]["recreated"] == []
    up_commands = [args for args, _ in host.commands if "compose" in args and "up" in args]
    assert len(up_commands) == 2
    assert all("--pull" in args and "never" in args and "--no-deps" in args for args in up_commands)
    assert all(TOKEN not in " ".join(args) for args, _ in host.commands)
    exec_kwargs = next(kwargs for args, kwargs in host.commands if len(args) > 1 and args[1] == "exec")
    assert exec_kwargs["input"] == TOKEN
    assert TOKEN not in json.dumps(report)


def test_apply_starts_workbench_once_with_token_in_child_environment(tmp_path):
    prepare_root(tmp_path)
    host = FakeHost(tmp_path, workbench_running=False)
    report = start_demo.DemoStartup(tmp_path, host, docker_cli="docker.exe", environ={"HOME": "C:/Users/example"},
                                    progress=lambda _: None).execute(True)
    assert report["workbench"]["action"] == "started"
    assert len(host.popen_calls) == 1
    args, kwargs = host.popen_calls[0]
    assert "start-workbench.ps1" in " ".join(args)
    assert args[1:4] == ["-NoProfile", "-ExecutionPolicy", "Bypass"]
    assert TOKEN not in " ".join(args)
    assert kwargs["env"]["ONTOLENS_MCP_TOKEN"] == TOKEN
    assert kwargs["env"]["HOME"] == "C:/Users/example"


def test_wrong_service_on_workbench_port_fails_before_any_mutation(tmp_path):
    prepare_root(tmp_path)
    host = FakeHost(tmp_path, workbench_running=True)
    host.get_json = lambda url, timeout: {"mode": "other", "active_id": "wrong"}
    manager = start_demo.DemoStartup(tmp_path, host, docker_cli="docker.exe", progress=lambda _: None)
    with pytest.raises(start_demo.StartupError) as error:
        manager.execute(True)
    assert error.value.code == "workbench_identity_mismatch"
    assert host.commands == []
    assert host.popen_calls == []


def test_wrong_existing_workbench_token_fails_before_compose_up(tmp_path):
    prepare_root(tmp_path)
    host = FakeHost(tmp_path, workbench_running=True)

    def reject_token(url, payload, headers, timeout):
        raise OSError("unauthorized")

    host.post_json = reject_token
    manager = start_demo.DemoStartup(tmp_path, host, docker_cli="docker.exe", progress=lambda _: None)
    with pytest.raises(start_demo.StartupError) as error:
        manager.execute(True)
    assert error.value.code == "workbench_mcp_auth_failed"
    assert host.commands == []
    assert host.popen_calls == []


def test_nexent_api_model_binding_mismatch_never_reports_ready(tmp_path):
    prepare_root(tmp_path)
    host = FakeHost(tmp_path, workbench_running=False)
    regular_get = host.get_json

    def mismatched_agent(url, timeout):
        if url.endswith("/api/agent/list"):
            return [{"agent_id": 1, "name": "ontolens_compliance_review", "model_ids": [2],
                     "is_available": True}]
        return regular_get(url, timeout)

    host.get_json = mismatched_agent
    manager = start_demo.DemoStartup(tmp_path, host, docker_cli="docker.exe", progress=lambda _: None)
    with pytest.raises(start_demo.StartupError) as error:
        manager.execute(True)
    assert error.value.code == "nexent_identity_mismatch"
    assert any("up" in args for args, _ in host.commands)


def test_foreign_same_name_container_is_refused(tmp_path):
    prepare_root(tmp_path)
    foreign = "foreign-id\tnexent-web\tother-project\tnexent-web"
    host = FakeHost(tmp_path, foreign_row=foreign)
    manager = start_demo.DemoStartup(tmp_path, host, docker_cli="docker.exe", progress=lambda _: None)
    with pytest.raises(start_demo.StartupError) as error:
        manager.execute(False)
    assert error.value.code == "foreign_container_name"
    assert all("up" not in args for args, _ in host.commands)


def test_docker_unavailable_preflight_does_not_start_desktop(tmp_path):
    prepare_root(tmp_path)
    host = FakeHost(tmp_path, docker_ready=False)
    manager = start_demo.DemoStartup(tmp_path, host, docker_cli="docker.exe", progress=lambda _: None)
    with pytest.raises(start_demo.StartupError) as error:
        manager.execute(False)
    assert error.value.code == "docker_unavailable"
    assert host.popen_calls == []


def test_apply_starts_only_an_existing_docker_desktop_install(tmp_path):
    prepare_root(tmp_path)
    desktop = tmp_path / "Programs/DockerDesktop/Docker Desktop.exe"
    desktop.parent.mkdir(parents=True)
    desktop.write_bytes(b"installed")
    host = FakeHost(tmp_path, docker_ready=False, workbench_running=True)
    report = start_demo.DemoStartup(
        tmp_path, host, docker_cli="docker.exe",
        environ={"LOCALAPPDATA": str(tmp_path), "HOME": "C:/Users/example"}, progress=lambda _: None,
    ).execute(True)
    assert report["docker"]["desktop_started"] is True
    desktop_calls = [args for args, _ in host.popen_calls if str(args[0]).endswith("Docker Desktop.exe")]
    assert desktop_calls == [[str(desktop)]]


def test_reports_are_unique_and_do_not_overwrite(tmp_path):
    first = start_demo.write_report({"mode": "preflight", "ready": True}, tmp_path)
    second = start_demo.write_report({"mode": "preflight", "ready": False}, tmp_path)
    assert first != second
    assert json.loads(first.read_text(encoding="utf-8"))["ready"] is True
    assert json.loads(second.read_text(encoding="utf-8"))["ready"] is False

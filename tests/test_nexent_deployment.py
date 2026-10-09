import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import audit_nexent_deployment

from scripts.audit_nexent_deployment import EXPECTED, audit_containers, is_project_windows_bind


ROOT = "F:/Projects/2026ICT"


def test_relocated_es_exception_is_exact_and_does_not_allow_other_services(monkeypatch):
    monkeypatch.setattr(audit_nexent_deployment, "elasticsearch_data_root",
                        lambda root: Path("D:/NexentData/2026ICT/elasticsearch"))
    def audit(name, source, destination):
        container = {"Name": "/" + name, "Image": "sha256:test", "Config": {"Image": "fixed:image"},
                     "State": {"Status": "running", "Health": {"Status": "healthy"}},
                     "Mounts": [{"Type": "bind", "Source": source, "Destination": destination}]}
        return audit_containers([container], ROOT)["containers"][0]["mounts"][0]["classification"]
    assert audit("nexent-elasticsearch", "D:/NexentData/2026ICT/elasticsearch", "/usr/share/elasticsearch/data") == "verified_project_relocation"
    assert audit("nexent-elasticsearch", "D:/NexentData/other", "/usr/share/elasticsearch/data") == "wrong_host_path"
    assert audit("nexent-postgresql", "D:/NexentData/2026ICT/elasticsearch", "/var/lib/postgresql/data") == "wrong_host_path"


@pytest.mark.parametrize("path", ["F:/Projects/2026ICT/.runtime/nexent-data",
                                  "F:\\Projects\\2026ICT\\.runtime\\data",
                                  "/run/desktop/mnt/host/f/Projects/2026ICT/.runtime/data",
                                  "/host_mnt/f/Projects/2026ICT/.runtime/data"])
def test_windows_project_binds_are_recognized(path):
    assert is_project_windows_bind(path, ROOT)


@pytest.mark.parametrize("path", ["/mnt/f/Projects/2026ICT/.runtime/data",
                                  "C:/Projects/2026ICT/.runtime/data",
                                  "F:/Projects/2026ICT-other/data",
                                  "F:/Projects/2026ICT/../../outside",
                                  "/var/lib/docker/volumes/example/_data"])
def test_other_or_linux_internal_paths_are_not_mistaken_for_f_drive(path):
    assert not is_project_windows_bind(path, ROOT)


def test_deployment_audit_reports_missing_services_health_and_public_ports_without_secrets():
    container = {"Name": "/nexent-web", "Image": "sha256:test",
                 "Config": {"Image": "nexent-web:fixed", "Env": ["TOKEN=do-not-report"]},
                 "State": {"Status": "running", "Health": {"Status": "unhealthy"}},
                 "Mounts": [{"Type": "bind", "Source": "/mnt/f/Projects/2026ICT/.runtime/data", "Destination": "/data"}],
                 "HostConfig": {"PortBindings": {"3000/tcp": [{"HostIp": "", "HostPort": "3000"}]}}}
    report = audit_containers([container], ROOT)
    assert report["ready"] is False
    assert {issue["code"] for issue in report["issues"]} == {
        "missing_service", "service_not_ready", "wrong_host_path", "non_loopback_port", "missing_project_bind"}
    assert "do-not-report" not in str(report)


def test_healthy_required_project_binds_do_not_require_moving_runtime_workspace_volume():
    containers = [{"Name": "/" + name, "Image": "sha256:test", "Config": {"Image": "fixed:image"},
                   "State": {"Status": "running",
                             **({"Health": {"Status": "healthy"}} if name in audit_nexent_deployment.REQUIRED_HEALTH else {})},
                   "RestartCount": 0,
                   "Mounts": [{"Type": "bind", "Source": ROOT + "/.runtime/data/" + str(index),
                               "Destination": destination}
                              for index, destination in enumerate(audit_nexent_deployment.REQUIRED_PROJECT_BINDS[name])]
                             + [{"Type": "volume", "Source": "/var/lib/docker/volumes/existing/_data",
                               "Destination": "/workspace"}],
                   "HostConfig": {"PortBindings": {"3000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "3000"}]}}}
                  for name in EXPECTED]
    report = audit_containers(containers, ROOT)
    assert report["ready"] is True
    assert any(mount["classification"] == "existing_docker_volume_do_not_move"
               for mount in report["containers"][0]["mounts"])


def test_deployment_audit_rejects_missing_or_volume_backed_persistent_mounts():
    containers = [{"Name": "/" + name, "Image": "sha256:test", "Config": {"Image": "fixed:image"},
                   "State": {"Status": "running",
                             **({"Health": {"Status": "healthy"}} if name in audit_nexent_deployment.REQUIRED_HEALTH else {})},
                   "RestartCount": 0,
                   "Mounts": [], "HostConfig": {"PortBindings": {}}} for name in EXPECTED]
    report = audit_containers(containers, ROOT)
    assert report["ready"] is False
    assert "missing_project_bind" in {issue["code"] for issue in report["issues"]}
    containers[0]["Mounts"] = [{"Type": "volume", "Source": "opaque-volume",
                                 "Destination": next(iter(audit_nexent_deployment.REQUIRED_PROJECT_BINDS[containers[0]["Name"].lstrip("/")]))}]
    assert audit_containers(containers, ROOT)["ready"] is False


@pytest.mark.parametrize("name", sorted(audit_nexent_deployment.REQUIRED_HEALTH))
def test_deployment_audit_rejects_required_health_or_restart_history(name):
    container = {"Name": "/" + name, "Image": "sha256:test", "Config": {"Image": "fixed:image"},
                 "State": {"Status": "running"}, "RestartCount": 1,
                 "Mounts": [{"Type": "bind", "Source": ROOT + "/.runtime/es", "Destination": destination}
                            for destination in audit_nexent_deployment.REQUIRED_PROJECT_BINDS[name]],
                 "HostConfig": {"PortBindings": {}}}
    report = audit_containers([container], ROOT)
    assert any(issue["code"] == "service_not_ready" for issue in report["issues"])


@pytest.mark.parametrize("error", [FileNotFoundError("docker not installed"),
                                  subprocess.CalledProcessError(1, "docker", stderr="SECRET=not-for-report"),
                                  subprocess.TimeoutExpired("docker", 20)])
def test_unavailable_docker_replaces_stale_success_with_redacted_failure(tmp_path, monkeypatch, error):
    report = tmp_path / "artifacts" / "nexent-deployment-audit-test.json"
    report.parent.mkdir()
    report.write_text(json.dumps({"ready": True}), encoding="utf-8")
    monkeypatch.setattr(audit_nexent_deployment, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["audit", "--output", str(report)])

    def unavailable(*args, **kwargs):
        raise error

    monkeypatch.setattr(audit_nexent_deployment.subprocess, "run", unavailable)
    assert audit_nexent_deployment.main() == 1
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["ready"] is False
    assert result["issues"][0]["code"] == "docker_inspection_failed"
    assert "SECRET" not in report.read_text(encoding="utf-8")

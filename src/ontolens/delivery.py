from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

import yaml


REQUIRED_CHECKS = {"pytest", "browser", "mcp", "assets", "jev", "pip", "javascript"}
WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DRAWING_NAMESPACE = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
SLIDE_NAMESPACE = "{http://schemas.openxmlformats.org/presentationml/2006/main}"


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_file(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Evidence must be an existing file inside the project")
    return path


def source_manifest(root: Path) -> dict[str, str]:
    patterns = ("src/ontolens/**/*.py", "src/ontolens/static/*", "scripts/*.py", "tests/*.py",
                "data/**/*", "pyproject.toml", "requirements.txt", "start-workbench.ps1", "start-demo.ps1",
                "setup-local.ps1", "setup-local.sh", "start-workbench.sh", "start-demo.sh",
                ".env.example", ".gitignore", ".gitattributes", "design.md", "design/02-foundations.md",
                "start-operational.ps1", "Dockerfile", ".dockerignore", "deploy/*.yaml",
                "scripts/source-release-policy.json", "nexent/upstream.json",
                "nexent/windows.override.yaml", "nexent/windows.paths.env.example")
    paths = {path for pattern in patterns for path in root.glob(pattern)
             if path.is_file() and "__pycache__" not in path.parts}
    return {path.relative_to(root).as_posix(): file_digest(local_file(root, str(path.relative_to(root))))
            for path in sorted(paths)}


def validation_count(root: Path, report: dict) -> int:
    rows = report.get("checks", [])
    if (report.get("passed") is not True or len(rows) != len(REQUIRED_CHECKS)
            or {row["name"] for row in rows} != REQUIRED_CHECKS):
        raise ValueError("All seven stage checks must be present and successful")
    if not report.get("input_manifest") or report["input_manifest"] != source_manifest(root):
        raise ValueError("Source files changed or have no fingerprint; rerun validate_local.py")
    count = None
    for row in rows:
        if type(row.get("exit_code")) is not int or row["exit_code"] != 0 or not row.get("command"):
            raise ValueError("A stage command failed or is missing")
        log = local_file(root, row["log"])
        if file_digest(log) != row.get("log_sha256"):
            raise ValueError("Stage log hash mismatch: " + row["name"])
        if row["name"] == "pytest":
            matches = re.findall(r"\b(\d+) passed\b", log.read_text(encoding="utf-8"))
            if len(matches) != 1 or int(matches[0]) < 1:
                raise ValueError("Missing or ambiguous pytest summary")
            count = int(matches[0])
    return count


def word_text(path: Path) -> str:
    with ZipFile(path) as archive:
        document = ElementTree.fromstring(archive.read("word/document.xml"))
    return "\n".join("".join(node.text or "" for node in paragraph.iter(WORD_NAMESPACE + "t"))
                     for paragraph in document.iter(WORD_NAMESPACE + "p"))


def slide_shapes(path: Path, number: int) -> dict[str, str]:
    with ZipFile(path) as archive:
        slide = ElementTree.fromstring(archive.read(f"ppt/slides/slide{number}.xml"))
    result = {}
    for shape in slide.iter(SLIDE_NAMESPACE + "sp"):
        identity = shape.find(".//" + SLIDE_NAMESPACE + "cNvPr")
        if identity is not None:
            result[identity.attrib["id"]] = "\n".join(node.text or "" for node in shape.iter(DRAWING_NAMESPACE + "t"))
    return result


def deck_text(path: Path) -> str:
    with ZipFile(path) as archive:
        slide_names = sorted(name for name in archive.namelist()
                             if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
        return "\n".join("\n".join(node.text or "" for node in
                                      ElementTree.fromstring(archive.read(name)).iter(DRAWING_NAMESPACE + "t"))
                           for name in slide_names)


def material_counts(root: Path, expected: int) -> dict:
    document = word_text(local_file(root, "submission/ontolens-development-design-draft.docx"))
    deck = deck_text(local_file(root, "submission/ontolens-presentation-draft.pptx"))
    counts = re.findall(r"(?:阶段回归|全量回归)\s+(\d+) passed", document)
    deck_counts = re.findall(r"(?:阶段回归|全量回归)\s+(\d+) passed", deck)
    if counts != [str(expected)] or deck_counts != [str(expected)]:
        raise ValueError("Word/PPT pytest counts differ from the recorded stage run")
    command = ".venv/Scripts/python.exe -m pytest -q"
    if command not in document or command not in deck:
        raise ValueError("The pytest number must carry its reproduction command in both documents")
    if not all(term in text for text in (document, deck) for term in ("unavailable", "SHA256", "未验证")):
        raise ValueError("Citation integrity and unverified online-model boundaries must remain visible")
    return {"word_pytest_passed": expected, "ppt_pytest_passed": expected}


def package_matches(root: Path) -> str:
    package = local_file(root, "artifacts/ontolens-nexent-agent.zip")
    agent = local_file(root, "nexent/agent.json").read_bytes()
    config = json.loads(agent)
    skills = {name for info in config["agent_info"].values() for name in info.get("skill_names", [])}
    if any(not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) for name in skills):
        raise ValueError("Invalid skill name")
    with ZipFile(package) as archive:
        expected = {"agent.json", *(f"skills/{name}.zip" for name in skills)}
        if len(archive.namelist()) != len(expected) or set(archive.namelist()) != expected or archive.read("agent.json") != agent:
            raise ValueError("Agent ZIP does not match the source template")
        for name in sorted(skills):
            with ZipFile(io.BytesIO(archive.read(f"skills/{name}.zip"))) as skill:
                original = local_file(root, f"nexent/skills/{name}/SKILL.md").read_bytes()
                if skill.namelist() != ["SKILL.md"] or skill.read("SKILL.md") != original:
                    raise ValueError("Bundled Skill differs from its source")
    return file_digest(package)


def readiness_stage(status: object) -> str:
    mapping = {
        "pending_team_model_and_deployment_fixes": "model_pending",
        "model_bound_synthetic_run_verified_pending_real_data_and_deployment_fixes": "model_bound_deployment_pending",
        "model_bound_synthetic_run_verified_deployment_ready_pending_real_data": "deployment_ready",
    }
    if status not in mapping:
        raise ValueError("Unknown Nexent model-readiness status")
    return mapping[status]


def integration_checks(integration: dict, readiness: dict) -> dict:
    required = {"seven_tools", "four_decisions", "needs_review", "evidence_quotes_and_hashes",
                "repeat_decision", "no_model_request", "offline_citation_check"}
    checks = integration.get("checks") or {}
    accepted = {"platform_tools_passed_model_pending", "platform_tools_and_synthetic_model_run_passed"}
    if integration.get("status") not in accepted or integration.get("error"):
        raise ValueError("Nexent integration verification failed or has not completed; rerun verify_nexent.py")
    if any(checks.get(name) is not True for name in required):
        raise ValueError("Nexent integration report is missing successful platform checks")
    agent = integration.get("agent") or {}
    if not isinstance(agent, dict):
        raise ValueError("Nexent integration Agent record is invalid")
    model_ids = readiness.get("model_ids")
    agent_id = readiness.get("agent_id")
    if (type(agent_id) is not int or agent_id < 1 or agent.get("agent_id") != agent_id
            or agent.get("model_ids") != model_ids):
        raise ValueError("Nexent integration and model-readiness bindings differ")
    models = integration.get("models")
    if (not isinstance(models, list) or any(not isinstance(item, dict) for item in models)
            or len(models) != readiness.get("models_visible")):
        raise ValueError("Nexent integration and model-readiness model inventories differ")
    bound = bool(model_ids)
    if bound:
        if (not isinstance(model_ids, list) or any(type(item) is not int or item < 1 for item in model_ids)
                or len(set(model_ids)) != len(model_ids)):
            raise ValueError("Nexent model binding IDs are invalid")
        run = integration.get("agent_run") or {}
        if (integration["status"] != "platform_tools_and_synthetic_model_run_passed"
                or checks.get("agent_model_orchestration") is not True
                or checks.get("agent_run_synthetic") is not True
                or agent.get("is_available") is not True
                or run.get("agent_id") != agent.get("agent_id")
                or run.get("model_id") not in model_ids
                or run.get("model_id") not in {item.get("model_id") for item in models}
                or run.get("mode") != "synthetic_demo" or run.get("final_status") != "ready"
                or not isinstance(run.get("artifact_sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", run["artifact_sha256"])
                or not isinstance(run.get("snapshot_hash"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", run["snapshot_hash"])
                or not isinstance(run.get("version_id"), str) or not run["version_id"]
                or type(run.get("evidence_count")) is not int or run["evidence_count"] < 1):
            raise ValueError("Nexent synthetic Agent run does not match the available model binding")
    elif (integration["status"] != "platform_tools_passed_model_pending"
          or checks.get("agent_model_orchestration") is not False
          or checks.get("agent_run_synthetic") is True or integration.get("agent_run")):
        raise ValueError("Nexent report claims model orchestration without a model binding")
    return {"passed": True, "status": integration["status"], "platform_checks": len(required),
            "synthetic_model_run_verified": bound}


def audit(root: Path) -> dict:
    report = {"passed": False, "scope": "Local delivery consistency only; not model performance or submission approval",
              "checks": {}, "goal_complete": False}
    try:
        validation_path = local_file(root, "artifacts/local-validation-report.json")
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        count = validation_count(root, validation)
        report["checks"]["validation"] = {"passed": True, "pytest_passed": count,
                                           "report_sha256": file_digest(validation_path), "run_dir": validation["run_dir"]}
        report["checks"]["materials"] = {"passed": True, **material_counts(root, count)}
        package_hash = package_matches(root)
        report["checks"]["package"] = {"passed": True, "sha256": package_hash}
        matrix_path = local_file(root, "submission/evidence-matrix.yaml")
        matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
        claims = {item["id"]: item for item in matrix["claims"]}
        if len(claims) != len(matrix["claims"]):
            raise ValueError("Duplicate evidence-matrix claim ID")
        integration = json.loads(local_file(root, "artifacts/nexent-integration-report.json").read_text(encoding="utf-8"))
        source_commit = integration.get("source_commit")
        if (integration.get("package_sha256") != package_hash
                or not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", source_commit)):
            raise ValueError("Nexent integration report describes another source package")
        readiness = json.loads(local_file(root, "artifacts/nexent-model-readiness.json").read_text(encoding="utf-8"))
        stage = readiness_stage(readiness.get("status"))
        pending_status = stage == "model_pending"
        bound_status = stage in {"model_bound_deployment_pending", "deployment_ready"}
        deployment_ready_status = stage == "deployment_ready"
        if pending_status:
            valid_model_state = readiness.get("model_ids") == [] and readiness.get("models_visible") == 0
        elif bound_status:
            model_ids = readiness.get("model_ids")
            valid_model_state = (isinstance(model_ids, list) and bool(model_ids)
                                 and all(type(item) is int and item > 0 for item in model_ids)
                                 and len(set(model_ids)) == len(model_ids)
                                 and readiness.get("models_visible") >= len(model_ids)
                                 and readiness.get("agent_available") is True)
        else:
            valid_model_state = False
        if (readiness.get("source_commit") != integration.get("source_commit")
                or readiness.get("mcp_tools_verified") != 7 or not valid_model_state):
            raise ValueError("Nexent model-readiness record is inconsistent or overclaims completion")
        agent_run_hash = None
        agent_run_path = None
        if bound_status:
            agent_run_path = local_file(root, readiness.get("agent_run_artifact", ""))
            agent_run_hash = file_digest(agent_run_path)
            integration_run = integration.get("agent_run") or {}
            if (readiness.get("agent_run_sha256") != agent_run_hash
                    or integration_run.get("artifact_sha256") != agent_run_hash
                    or Path(integration_run.get("source", "")).as_posix()
                    != agent_run_path.relative_to(root).as_posix()):
                raise ValueError("Nexent Agent-run evidence hash or path differs from the recorded artifact")
        report["checks"]["integration"] = integration_checks(integration, readiness)
        deployment_path = local_file(root, "artifacts/nexent-deployment-audit.json")
        deployment = json.loads(deployment_path.read_text(encoding="utf-8"))
        if (type(deployment.get("ready")) is not bool or not isinstance(deployment.get("issues"), list)
                or any(not isinstance(item, dict) or not isinstance(item.get("code"), str)
                       for item in deployment.get("issues", []))):
            raise ValueError("Nexent deployment audit has an invalid schema")
        if deployment_ready_status and (readiness.get("deployment_audit_ready") is not True
                                        or deployment["ready"] is not True or deployment["issues"]):
            raise ValueError("Deployment-ready model record differs from the current deployment audit")
        migration_path = None
        model_configuration_path = None
        if deployment_ready_status:
            migration_path = local_file(root, "artifacts/nexent-data-migration-report.json")
            migration = json.loads(migration_path.read_text(encoding="utf-8"))
            if migration.get("status") not in {"copied_container_state_with_limits", "source_target_manifests_verified"}:
                raise ValueError("Nexent migration report is missing or overclaims verification")
            model_configuration_path = local_file(root, "artifacts/nexent-model-configuration-report.json")
            model_configuration = json.loads(model_configuration_path.read_text(encoding="utf-8"))
            if (model_configuration.get("status") != "configured"
                    or model_configuration.get("connectivity") is not True
                    or model_configuration.get("model_id") not in readiness.get("model_ids", [])
                    or model_configuration.get("agent_id") != readiness.get("agent_id")):
                raise ValueError("Nexent model recovery report differs from model readiness")
        if not integration.get("checks", {}).get("agent_model_orchestration") and claims["C03"]["status"] == "DONE":
            raise ValueError("C03 overclaims complete model orchestration")
        if (claims["C06"]["status"] != "PARTIAL"
                or "--live" not in claims["C06"]["command"]
                or "artifacts/jev-live-verification.json" not in claims["C06"]["evidence"]):
            raise ValueError("C06 must point to the explicit live JEV verification and its artifact")
        if claims["C12"]["status"] != "PARTIAL":
            raise ValueError("C12 must distinguish implemented citation integrity from unverified semantic review")
        if claims.get("C13", {}).get("status") != "PARTIAL":
            raise ValueError("C13 must distinguish protocol contract tests from online model verification")
        if claims.get("C14", {}).get("status") != "PARTIAL":
            raise ValueError("C14 must distinguish change-review contract tests from real-data validation")
        if claims.get("C15", {}).get("status") != "PARTIAL":
            raise ValueError("C15 must distinguish relation-review contract tests from domain validation")
        if claims.get("C16", {}).get("status") != "PARTIAL":
            raise ValueError("C16 must distinguish replay contracts from online model verification")
        if claims.get("C17", {}).get("status") != "PARTIAL":
            raise ValueError("C17 must distinguish local model preflight from Nexent Agent execution")
        if claims.get("C10", {}).get("status") != "PARTIAL":
            raise ValueError("C10 must keep deployment audit scope and residual risk explicit")
        if claims.get("C18", {}).get("status") != "DONE":
            raise ValueError("C18 must preserve the fail-closed delivery-audit regression")
        if claims.get("C19", {}).get("status") != "PARTIAL":
            raise ValueError("C19 must distinguish same-host recovery from independent cold start")
        report["checks"]["matrix"] = {"passed": True, "C03": claims["C03"]["status"],
                                        "C06": claims["C06"]["status"], "C12": claims["C12"]["status"],
                                        "C13": claims["C13"]["status"], "C14": claims["C14"]["status"],
                                        "C15": claims["C15"]["status"], "C16": claims["C16"]["status"],
                                        "C17": claims["C17"]["status"], "C18": claims["C18"]["status"],
                                        "C19": claims["C19"]["status"]}
        report["checks"]["deployment"] = {"passed": True, "ready": deployment["ready"],
                                            "issue_codes": sorted({item.get("code") for item in deployment["issues"]}),
                                            "report_sha256": file_digest(deployment_path)}
        report["checks"]["model_readiness"] = {"passed": True, "status": readiness["status"],
                                                       "model_ids": readiness["model_ids"],
                                                       "models_visible": readiness["models_visible"],
                                                       "agent_run_sha256": agent_run_hash}
        evidence_files = [
            "submission/ontolens-development-design-draft.docx", "submission/ontolens-presentation-draft.pptx",
            "submission/evidence-matrix.yaml", "artifacts/nexent-integration-report.json",
            "artifacts/nexent-deployment-audit.json", "artifacts/nexent-model-readiness.json",
        ]
        if agent_run_path is not None:
            evidence_files.append(readiness["agent_run_artifact"])
        if migration_path is not None:
            evidence_files.extend(["artifacts/nexent-data-migration-report.json",
                                   "artifacts/nexent-model-configuration-report.json"])
        report["files"] = {name: file_digest(local_file(root, name)) for name in evidence_files}
        report["passed"] = True
    except (OSError, ValueError, KeyError, TypeError, AttributeError,
            BadZipFile, ElementTree.ParseError, yaml.YAMLError) as error:
        report["error"] = str(error)
    return report

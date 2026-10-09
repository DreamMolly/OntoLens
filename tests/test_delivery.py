from pathlib import Path
from zipfile import ZipFile

import pytest

from peiwu.delivery import (
    deck_text,
    file_digest,
    integration_checks,
    local_file,
    material_counts,
    package_matches,
    readiness_stage,
    slide_shapes,
    source_manifest,
    word_text,
)


ROOT = Path(__file__).resolve().parents[1]


def test_source_manifest_is_deterministic_and_covers_new_delivery_code():
    first = source_manifest(ROOT)
    second = source_manifest(ROOT)
    assert first == second
    assert "src/peiwu/delivery.py" in first
    assert "scripts/audit_deliverables.py" in first
    assert first["src/peiwu/delivery.py"] == file_digest(ROOT / "src/peiwu/delivery.py")
    assert first["start-demo.ps1"] == file_digest(ROOT / "start-demo.ps1")
    assert "nexent/windows.override.yaml" in first
    assert "nexent/windows.paths.env.example" in first


def test_local_file_rejects_paths_outside_project():
    with pytest.raises(ValueError):
        local_file(ROOT, "../outside.txt")


def test_existing_material_readers_find_boundaries_and_count_shape():
    document = word_text(ROOT / "submission/peiwu-development-design-draft.docx")
    slides = deck_text(ROOT / "submission/peiwu-presentation-draft.pptx")
    assert "source_id、locator、quote 和 SHA256" in document
    assert "unavailable" in document
    assert "MCP" in slides and "unavailable" in slides


@pytest.mark.parametrize("deck_count,accepted", [(27, True), (26, False)])
def test_material_counts_survive_slide_and_object_reordering(tmp_path, deck_count, accepted):
    folder = tmp_path / "submission"
    folder.mkdir()
    prefix = ".venv/Scripts/python.exe -m pytest -q; unavailable; SHA256; 未验证; 阶段回归 "
    with ZipFile(folder / "peiwu-development-design-draft.docx", "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>' + prefix + '27 passed</w:t></w:r></w:p></w:body></w:document>')
    with ZipFile(folder / "peiwu-presentation-draft.pptx", "w") as archive:
        archive.writestr("ppt/slides/slide2.xml", '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="99" name="regression"/></p:nvSpPr><p:txBody><a:p><a:r><a:t>' + prefix + str(deck_count) + ' passed</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')
    if accepted:
        assert material_counts(tmp_path, 27) == {"word_pytest_passed": 27, "ppt_pytest_passed": 27}
    else:
        with pytest.raises(ValueError, match="counts differ"):
            material_counts(tmp_path, 27)


def test_nexent_package_matches_source_template():
    package_hash = package_matches(ROOT)
    assert len(package_hash) == 64
    assert package_hash == file_digest(ROOT / "artifacts/peiwu-nexent-agent.zip")


@pytest.mark.parametrize(("status", "stage"), [
    ("pending_team_model_and_deployment_fixes", "model_pending"),
    ("model_bound_synthetic_run_verified_pending_real_data_and_deployment_fixes",
     "model_bound_deployment_pending"),
    ("model_bound_synthetic_run_verified_deployment_ready_pending_real_data", "deployment_ready"),
])
def test_readiness_stage_distinguishes_model_and_deployment_gates(status, stage):
    assert readiness_stage(status) == stage


def test_readiness_stage_rejects_unknown_status():
    with pytest.raises(ValueError, match="Unknown"):
        readiness_stage("made_up")


@pytest.fixture
def bound_platform_reports():
    checks = {name: True for name in (
        "seven_tools", "four_decisions", "needs_review", "evidence_quotes_and_hashes",
        "repeat_decision", "no_model_request", "offline_citation_check",
        "agent_model_orchestration", "agent_run_synthetic")}
    integration = {
        "status": "platform_tools_and_synthetic_model_run_passed", "checks": checks,
        "agent": {"agent_id": 1, "model_ids": [1], "is_available": True},
        "models": [{"model_id": 1}],
        "agent_run": {"agent_id": 1, "model_id": 1, "mode": "synthetic_demo", "final_status": "ready",
                      "artifact_sha256": "a" * 64, "snapshot_hash": "b" * 64,
                      "version_id": "demo-initial", "evidence_count": 6},
    }
    readiness = {"agent_id": 1, "model_ids": [1], "models_visible": 1}
    return integration, readiness


def test_delivery_accepts_verified_platform_without_claiming_deployment_ready(bound_platform_reports):
    result = integration_checks(*bound_platform_reports)
    assert result["passed"] is True
    assert result["synthetic_model_run_verified"] is True
    assert "deployment_verified" not in result


def test_delivery_rejects_interrupted_docker_report_even_with_matching_metadata(bound_platform_reports):
    integration, readiness = bound_platform_reports
    integration.update(status="failed", error="Docker API is unavailable")
    with pytest.raises(ValueError, match="failed or has not completed"):
        integration_checks(integration, readiness)


@pytest.mark.parametrize("check", ["seven_tools", "four_decisions", "needs_review",
                                  "evidence_quotes_and_hashes", "repeat_decision",
                                  "no_model_request", "offline_citation_check"])
def test_delivery_rejects_missing_platform_check(bound_platform_reports, check):
    integration, readiness = bound_platform_reports
    integration["checks"].pop(check)
    with pytest.raises(ValueError, match="missing successful platform checks"):
        integration_checks(integration, readiness)


@pytest.mark.parametrize("field,value", [("agent_id", 2), ("model_ids", [2]), ("models_visible", 0)])
def test_delivery_rejects_stale_model_readiness(bound_platform_reports, field, value):
    integration, readiness = bound_platform_reports
    readiness[field] = value
    with pytest.raises(ValueError, match="differ"):
        integration_checks(integration, readiness)


def test_delivery_rejects_malformed_model_inventory(bound_platform_reports):
    integration, readiness = bound_platform_reports
    integration["models"] = ["not-a-model-record"]
    with pytest.raises(ValueError, match="inventories differ"):
        integration_checks(integration, readiness)


@pytest.mark.parametrize("field,value", [("agent_id", 2), ("model_id", 2),
                                        ("mode", "real_data"), ("final_status", "error")])
def test_delivery_rejects_agent_run_for_another_binding_or_scope(bound_platform_reports, field, value):
    integration, readiness = bound_platform_reports
    integration["agent_run"][field] = value
    with pytest.raises(ValueError, match="does not match"):
        integration_checks(integration, readiness)


def test_delivery_rejects_missing_agent_identity_even_when_all_reports_omit_it(bound_platform_reports):
    integration, readiness = bound_platform_reports
    integration["agent"].pop("agent_id")
    integration["agent_run"].pop("agent_id")
    readiness.pop("agent_id")
    with pytest.raises(ValueError, match="bindings differ"):
        integration_checks(integration, readiness)


def test_delivery_keeps_unbound_platform_explicitly_model_pending(bound_platform_reports):
    integration, readiness = bound_platform_reports
    integration["status"] = "platform_tools_passed_model_pending"
    integration["agent"]["model_ids"] = []
    integration["models"] = []
    integration.pop("agent_run")
    integration["checks"].update(agent_model_orchestration=False, agent_run_synthetic=False)
    readiness.update(model_ids=[], models_visible=0)
    assert integration_checks(integration, readiness)["synthetic_model_run_verified"] is False
    integration["checks"]["agent_model_orchestration"] = True
    with pytest.raises(ValueError, match="without a model binding"):
        integration_checks(integration, readiness)


def test_delivery_accepts_consistent_nondefault_model_id(bound_platform_reports):
    integration, readiness = bound_platform_reports
    integration["agent"]["model_ids"] = [2]
    integration["models"] = [{"model_id": 2}]
    integration["agent_run"]["model_id"] = 2
    readiness["model_ids"] = [2]
    assert integration_checks(integration, readiness)["synthetic_model_run_verified"] is True


def test_integration_helper_only_validates_agent_run_digest_shape(bound_platform_reports):
    integration, readiness = bound_platform_reports
    integration["agent_run"]["artifact_sha256"] = "0" * 64
    # The helper validates shape; audit() separately binds this digest to the local evidence file.
    assert integration_checks(integration, readiness)["synthetic_model_run_verified"] is True

from __future__ import annotations

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import shutil
from threading import Barrier

import pytest
import yaml
from pydantic import ValidationError

import ontolens.counterfactual as counterfactual
from ontolens.contracts import CheckRequest
from ontolens.counterfactual import build_counterfactual_report


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path):
    for name in ("data/catalog.yaml", "data/rules/v2.yaml", "data/evaluation/counterfactuals.yaml"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return tmp_path


def edit_fixture(project, mutate):
    path = project / "data/evaluation/counterfactuals.yaml"
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(spec)
    path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")


def test_counterfactual_report_is_reproducible_and_scoped(project):
    first = build_counterfactual_report(root=project)
    second = build_counterfactual_report(root=project)

    assert first == second
    assert first["scope"]["mode"] == "synthetic_demo"
    assert "industry accuracy" in first["scope"]["claim_boundary"]
    assert first["summary"] == {
        "total": 21,
        "passed": 21,
        "failed": 0,
        "all_pass": True,
        "by_category": {
            "cabinet": {"total": 1, "passed": 1, "failed": 0},
            "inventory": {"total": 2, "passed": 2, "failed": 0},
            "quantity_boundary": {"total": 2, "passed": 2, "failed": 0},
            "today_unreturned_class": {"total": 1, "passed": 1, "failed": 0},
            "unknown_entity": {"total": 3, "passed": 3, "failed": 0},
            "unit": {"total": 1, "passed": 1, "failed": 0},
            "authorization_validity": {"total": 6, "passed": 6, "failed": 0},
            "lot_status": {"total": 2, "passed": 2, "failed": 0},
            "invariance": {"total": 3, "passed": 3, "failed": 0},
        },
    }
    assert first["inputs"]["fixture"]["path"] == "data/evaluation/counterfactuals.yaml"
    assert all(len(item["input_hash"]) == 64 for item in first["cases"])
    assert all(item["checks"]["mutation_isolated"] for item in first["cases"])


def test_counterfactual_covers_review_boundaries_and_decision_changes(project):
    report = build_counterfactual_report(root=project)
    by_id = {item["id"]: item for item in report["cases"]}

    unit = by_id["CF-UNIT-001"]
    assert unit["variant"]["outcome"] == {
        "status": "needs_review", "unit": None, "decision": None, "review_reason_code": "UNIT_MISMATCH"
    }
    assert unit["checks"]["decision_changed"] is True
    assert unit["checks"]["status_changed"] is True

    stock = by_id["CF-INVENTORY-001"]
    assert stock["variant"]["outcome"]["decision"] == {
        "action": "LIMIT", "approved_quantity": 20.0, "reason_code": "STOCK_SHORT", "rule_version": "v2"
    }
    assert stock["checks"]["status_changed"] is False

    unreturned = by_id["CF-UNRETURNED-001"]
    assert unreturned["variant"]["outcome"]["decision"]["reason_code"] == "SESSION_INCOMPATIBLE"
    unknown = by_id["CF-UNKNOWN-REQUESTER-001"]
    assert unknown["variant"]["outcome"]["status"] == "needs_review"
    assert unknown["variant"]["outcome"]["decision"] is None

    cap = by_id["CF-QUANTITY-CAP-001"]
    assert cap["variant"]["outcome"]["decision"]["reason_code"] == "ISSUE_CAP"
    invalid = by_id["CF-INVALID-QUANTITY-001"]
    assert invalid["variant"]["outcome"]["decision"]["reason_code"] == "INVALID_QUANTITY"
    assert invalid["evaluation_layer"] == "internal_calculation"
    with pytest.raises(ValidationError, match="greater than 0"):
        CheckRequest.model_validate(invalid["variant"]["request"])
    assert "not an HTTP response" in report["scope"]["http_boundary"]


def test_counterfactual_does_not_use_frozen_gold_cases(project):
    gold_hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "data/cases").glob("*.yaml")}
    assert gold_hashes
    # The isolated project deliberately has no data/cases directory.
    assert not (project / "data/cases").exists()
    report = build_counterfactual_report(root=project)
    fixture_path = project / report["inputs"]["fixture"]["path"]
    assert fixture_path.parent == project / "data" / "evaluation"
    assert fixture_path.name == "counterfactuals.yaml"
    assert "data/cases/" not in report["inputs"]["fixture"]["path"]
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in gold_hashes.items())


def test_authorization_inclusive_boundaries_and_setup_receipt(project):
    report = build_counterfactual_report(root=project)
    cases = {item["id"]: item for item in report["cases"]}
    for suffix, at in (("START-ON", "2026-09-25"), ("START-AFTER", "2026-09-26"),
                       ("END-BEFORE", "2026-09-29"), ("END-ON", "2026-09-30")):
        item = cases["CF-AUTH-" + suffix]
        assert item["variant"]["request"]["as_of"] == at
        assert item["variant"]["outcome"]["decision"]["action"] == "ALLOW"
        assert item["checks"]["decision_changed"] is False
        assert item["expected_relation"] == "invariant"
        assert item["checks"]["passed"] is True
    for suffix, code in (("START-BEFORE", "AUTHORIZATION_NOT_ACTIVE"), ("END-AFTER", "AUTHORIZATION_EXPIRED")):
        assert cases["CF-AUTH-" + suffix]["variant"]["outcome"] == {
            "status": "needs_review", "unit": None, "decision": None, "review_reason_code": code,
        }
    for item in (item for item in report["cases"] if item["category"] == "authorization_validity"):
        assert item["setup"] == [{
            "path": "validity.stu01", "value": {"from": "2026-09-25", "until": "2026-09-30"},
            "reason": "Synthetic bounded authorization for inclusive date-boundary checks; not source evidence.",
        }]
        assert item["observed_setup_paths"] == ["validity.stu01"]
        assert item["observed_changed_paths"] == ["request.as_of"]


def test_nonissuable_lots_and_irrelevant_changes(project):
    report = build_counterfactual_report(root=project)
    for item in report["cases"]:
        if item["category"] == "lot_status":
            assert item["variant"]["outcome"]["decision"] == {
                "action": "ISOLATE", "approved_quantity": None, "reason_code": "LOT_NOT_ISSUABLE", "rule_version": "v2",
            }
        if item["category"] == "invariance":
            assert item["base"]["outcome"] == item["variant"]["outcome"]
            assert item["checks"]["passed"] is True


def test_parallel_runs_preserve_old_database_and_use_unique_directories(project, monkeypatch):
    temp_root = project / "tmp"
    temp_root.mkdir()
    sentinel = temp_root / "counterfactual-evaluation.sqlite3"
    sentinel.write_bytes(b"pre-existing database sentinel")
    barrier = Barrier(2)
    databases = []
    original = counterfactual.Workspace

    def synchronized_workspace(root, database):
        databases.append(database)
        barrier.wait(timeout=15)
        return original(root, database)

    monkeypatch.setattr(counterfactual, "Workspace", synchronized_workspace)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(build_counterfactual_report, root=project) for _ in range(2)]
        first, second = [future.result(timeout=30) for future in futures]
    assert first == second
    assert first["summary"]["all_pass"] is True
    assert len({path.parent for path in databases}) == 2
    assert all(path.parent.parent == temp_root for path in databases)
    assert list(temp_root.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"pre-existing database sentinel"


@pytest.mark.parametrize("phase", ["construction", "evaluation"])
def test_exception_cleans_only_its_own_directory(project, monkeypatch, phase):
    temp_root = project / "tmp"
    temp_root.mkdir()
    sentinel = temp_root / "counterfactual-evaluation.sqlite3"
    sentinel.write_bytes(b"keep old database")
    sibling = temp_root / "counterfactual-evaluation-another-run"
    sibling.mkdir()
    (sibling / "active.sqlite3").write_bytes(b"keep concurrent run")
    original = counterfactual.Workspace

    if phase == "construction":
        def broken_workspace(root, database):
            database.write_bytes(b"partial database")
            raise RuntimeError("injected constructor failure")
        monkeypatch.setattr(counterfactual, "Workspace", broken_workspace)
    else:
        def broken_calculate(*args, **kwargs):
            raise RuntimeError("injected calculation failure")
        monkeypatch.setattr(original, "_calculate", broken_calculate)
    with pytest.raises(RuntimeError, match="injected"):
        build_counterfactual_report(root=project)
    assert set(temp_root.iterdir()) == {sentinel, sibling}
    assert sentinel.read_bytes() == b"keep old database"
    assert (sibling / "active.sqlite3").read_bytes() == b"keep concurrent run"


@pytest.mark.parametrize("side", ["base", "variant"])
def test_wrong_expectation_fails_report(project, side):
    def tamper(spec):
        spec["cases"][0]["expected"][side]["status"] = "incorrect_expected_status"
    edit_fixture(project, tamper)
    report = build_counterfactual_report(root=project)
    assert report["summary"]["all_pass"] is False
    assert report["summary"]["failed"] == 1
    assert report["cases"][0]["checks"]["expected_" + side] is False


def test_wrong_review_reason_fails_even_when_status_matches(project):
    def tamper(spec):
        case = next(c for c in spec["cases"] if c["id"] == "CF-AUTH-END-AFTER")
        case["expected"]["variant"]["review_reason_code"] = "AUTHORIZATION_NOT_ACTIVE"
    edit_fixture(project, tamper)
    report = build_counterfactual_report(root=project)
    assert report["summary"]["failed"] == 1
    assert report["summary"]["all_pass"] is False


def test_declared_invariance_cannot_hide_a_changed_outcome(project):
    edit_fixture(project, lambda spec: spec["cases"][0].update(expected_relation="invariant"))
    report = build_counterfactual_report(root=project)
    assert report["cases"][0]["checks"]["expected_variant"] is True
    assert report["cases"][0]["checks"]["relation_holds"] is False
    assert report["summary"]["all_pass"] is False


def test_setup_is_hashed_and_does_not_allow_new_mutation_keys(project):
    first = build_counterfactual_report(root=project)
    def change_reason(spec):
        next(c for c in spec["cases"] if c.get("setup"))["setup"][0]["reason"] += " Revised provenance note."
    edit_fixture(project, change_reason)
    second = build_counterfactual_report(root=project)
    before = next(c for c in first["cases"] if c["setup"])
    after = next(c for c in second["cases"] if c["setup"])
    assert before["input_hash"] != after["input_hash"]
    assert before["base"]["outcome"] == after["base"]["outcome"]
    state = {"validity": {}}
    with pytest.raises(ValueError, match="leaf does not exist"):
        counterfactual._set_path(state, "validity.stu01", {"from": "2026-09-25"})
    assert state == {"validity": {}}


@pytest.mark.parametrize("operation", [
    {"path": "validity.unknown", "value": {"from": "2026-09-25", "until": "2026-09-30"}, "reason": "test"},
    {"path": "validity.stu01", "value": {"from": "2026-09-30", "until": "2026-09-25"}, "reason": "test"},
    {"path": "validity.stu01", "value": {"from": "2026-09-25", "until": "2026-09-30"}},
])
def test_malformed_setup_fails_closed(project, operation):
    edit_fixture(project, lambda spec: spec["cases"][0].update(setup=[copy.deepcopy(operation)]))
    with pytest.raises(ValueError, match="setup"):
        build_counterfactual_report(root=project)

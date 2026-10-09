"""Synthetic test fixtures exercise actual private-source import contracts."""
import base64
import copy
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest
import yaml

from peiwu.export_verification import verify_evidence_export
from peiwu.ledger_import import GROUPS, canonical, parse_bundle
from peiwu.workspace import Workspace, WorkspaceError, digest, encode

ROOT = Path(__file__).resolve().parents[1]


def bundle(format="json"):
    # These are deliberately synthetic test records, not external validation.
    facts = {
        "people": {
            "operator_847": {"role": "teacher", "banned": False, "classes": ["FLAMMABLE"],
                             "authorization_basis": "TEST FIXTURE access record A-9", "valid_from": "2026-01-01", "valid_until": "2026-12-31"},
            "blocked_18": {"role": "teacher", "banned": True, "classes": ["FLAMMABLE"],
                           "authorization_basis": "TEST FIXTURE suspended access", "valid_from": "2026-01-01", "valid_until": "2026-12-31"}},
        "chemicals": {"material_842": {"hazard_class": "FLAMMABLE", "per_issue_limit": 40, "unit": "mL"}},
        "lots": {"batch_92": {"chemical_id": "material_842", "on_hand": 250, "status": "available"},
                 "damaged_61": {"chemical_id": "material_842", "on_hand": 30, "status": "damaged"}},
        "cabinets": {"storage_116": {"allowed_classes": ["FLAMMABLE"]}},
        "issues": {"operator_847": [], "blocked_18": []},
        "rules": {"version": "local-rule-47", "student_fraction": 0.5, "session_incompatibility": True,
                  "deny_students": False, "incompatible_pairs": [["FLAMMABLE", "OXIDIZER"]]},
    }
    files, sources = {}, {}
    for group in GROUPS:
        selected = format if group != "rules" else "yaml"
        media = {"json": "application/json", "yaml": "application/yaml", "csv": "text/csv"}[selected]
        name = group + "." + selected
        if selected == "json":
            raw = b"\xef\xbb\xbf" + json.dumps(facts[group], indent=2).replace("\n", "\r\n").encode()
        elif selected == "yaml":
            raw = ("# TEST FIXTURE original source\r\n" + yaml.safe_dump(facts[group], sort_keys=False)).encode()
        else:
            output = io.StringIO(newline="")
            rows = [{"id": key, **({"classes": row} if group == "issues" else row)} for key, row in facts[group].items()]
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow({key: json.dumps(value) if isinstance(value, (list, bool)) else value for key, value in row.items()})
            raw = output.getvalue().encode()
        files[name] = raw
        sources[group] = {"file": name, "media_type": media, "kind": "private", "sha256": digest(raw)}
    manifest = {"schema": "peiwu-ledger-bundle-1", "label": "TEST FIXTURE operator ledger",
                "authorization": {"local_operation_authorized": True, "operator": "test-operator", "basis": "TEST FIXTURE local authorization"},
                "metadata": {"authorized_by": "test-authority", "purpose": "automated contract test", "recorded_at": "2026-10-08"}, "sources": sources}
    return manifest, files, facts


def request(**changes):
    return {"request_id": "test-operational-1", "requester_id": "operator_847", "lot_id": "batch_92",
            "destination_cabinet_id": "storage_116", "quantity": 20, "unit": "mL", "as_of": "2026-10-08", **changes}


@pytest.fixture
def workspace(tmp_path):
    return Workspace(ROOT, tmp_path / "business.sqlite3", seed_demo=False)


def activate(workspace, format="json"):
    manifest, files, facts = bundle(format)
    candidate = workspace.import_ledger_bundle(manifest, files)
    report = workspace.preview(candidate["id"])
    assert report["structural_validation"]["accepted"], report
    assert report["structural_validation"]["invariants"]["checked_requests"] == 4
    assert workspace.active_id() == "operational-initial"
    version = workspace.publish(candidate["id"], workspace.active_id(), "Publish TEST FIXTURE")
    return manifest, files, facts, candidate, version


def test_empty_operational_has_no_seed_facts_and_exports(workspace):
    assert workspace.documents() == []
    assert all(not rows for rows in workspace.version()["snapshot"]["catalog"].values())
    result = workspace.check(request())
    assert result["status"] == "needs_review" and result["decision"] is None
    assert result["evidence"] == [] and result["mode"] == "imported_workspace"
    report = verify_evidence_export(workspace.export(result["run_id"]))
    assert report["passed"], report


@pytest.mark.parametrize("format", ["json", "yaml", "csv"])
def test_arbitrary_business_ids_original_bytes_actions_and_offline_replay(workspace, format):
    manifest, files, facts, candidate, version = activate(workspace, format)
    assert version["snapshot"]["catalog"]["people"] == facts["people"]
    assert "stu01" not in version["snapshot"]["catalog"]["people"]
    variants = [(request(), "ALLOW"), (request(quantity=80), "LIMIT"),
                (request(requester_id="blocked_18"), "DENY"), (request(lot_id="damaged_61"), "ISOLATE"),
                (request(as_of="2027-01-01"), None), (request(unit="g"), None), (request(requester_id="missing"), None)]
    for payload, action in variants:
        result = workspace.check(payload)
        assert result["mode"] == "imported_workspace"
        assert (result["decision"]["action"] if result["decision"] else None) == action
        exported = workspace.export(result["run_id"])
        report = verify_evidence_export(exported)
        assert report["passed"], report
        assert report["scope"]["decision_reexecuted"]
        source_map = {source["id"]: source for source in exported["sources"]}
        for group, binding in version["snapshot"]["import_bindings"].items():
            original = source_map[binding["original_source_id"]]
            raw = base64.b64decode(original["raw_base64"])
            assert raw == files[manifest["sources"][group]["file"]]
            text = raw.decode("utf-8-sig")
            for chunk in original["chunks"]:
                assert chunk["text"] in text
            if group != "rules":
                assert {chunk["locator"] for chunk in original["chunks"] if chunk["locator"].startswith("$.")} == {"$." + entity for entity in facts[group]}
        assert len(source_map) == 12 and all(not source["external_model_allowed"] for source in source_map.values())


def test_new_stock_snapshot_changes_only_new_runs_and_rollback(workspace):
    manifest, files, _, _, first = activate(workspace)
    original = workspace.check(request(quantity=30))
    original_export = workspace.export(original["run_id"])
    lots_file = manifest["sources"]["lots"]["file"]
    lots = json.loads(files[lots_file].decode("utf-8-sig"))
    lots["batch_92"]["on_hand"] = 7
    files[lots_file] = canonical(lots).encode()
    manifest["sources"]["lots"]["sha256"] = digest(files[lots_file])
    candidate = workspace.import_ledger_bundle(manifest, files)
    report = workspace.preview(candidate["id"])
    assert report["changes"][0]["after"]["decision"]["approved_quantity"] == 7
    second = workspace.publish(candidate["id"], first["id"], "Updated TEST FIXTURE stock")
    assert workspace.check(request(quantity=30))["decision"]["approved_quantity"] == 7
    assert workspace.export(original["run_id"]) == original_export
    workspace.rollback(first["id"], second["id"], "restore TEST FIXTURE")
    assert workspace.check(request(quantity=30))["decision"]["approved_quantity"] == 30


def test_publish_cas_rejects_stale_candidate(workspace):
    manifest, files, _ = bundle()
    a = workspace.import_ledger_bundle(manifest, files)
    b = workspace.import_ledger_bundle(manifest, files)
    workspace.publish(a["id"], "operational-initial", "TEST FIXTURE A")
    with pytest.raises(WorkspaceError) as error:
        workspace.publish(b["id"], "operational-initial", "TEST FIXTURE B")
    assert error.value.status == 409


@pytest.mark.parametrize("fault", ["hash", "unauthorized", "public_person", "external", "missing_file", "unknown_reference", "nan", "date", "unit", "issues"])
def test_invalid_bundle_is_atomic(workspace, fault):
    manifest, files, facts = bundle()
    if fault == "hash":
        files["people.json"] += b" "
    elif fault == "unauthorized":
        manifest["authorization"]["local_operation_authorized"] = False
    elif fault == "public_person":
        manifest["sources"]["people"]["kind"] = "public"
    elif fault == "external":
        manifest["sources"]["lots"]["external_model_allowed"] = True
    elif fault == "missing_file":
        files.pop("lots.json")
    else:
        group = {"unknown_reference": "lots", "nan": "lots", "date": "people", "unit": "chemicals", "issues": "issues"}[fault]
        if fault == "unknown_reference": facts[group]["batch_92"]["chemical_id"] = "unknown"
        if fault == "nan": facts[group]["batch_92"]["on_hand"] = float("nan")
        if fault == "date": facts[group]["operator_847"]["valid_until"] = "2025-01-01"
        if fault == "unit": facts[group]["material_842"]["unit"] = "unspecified"
        if fault == "issues": facts[group].pop("operator_847")
        files[group + ".json"] = json.dumps(facts[group]).encode()
        manifest["sources"][group]["sha256"] = digest(files[group + ".json"])
    with pytest.raises(WorkspaceError):
        workspace.import_ledger_bundle(manifest, files)
    assert workspace.documents() == [] and workspace.candidates() == []


def test_modified_original_blocks_publish(workspace):
    manifest, files, _ = bundle()
    candidate = workspace.import_ledger_bundle(manifest, files)
    original_id = candidate["snapshot"]["import_bindings"]["lots"]["original_source_id"]
    with workspace.connect(write=True) as connection:
        connection.execute("UPDATE documents SET raw=? WHERE id=?", (b"changed", original_id))
    assert not workspace.preview(candidate["id"])["structural_validation"]["accepted"]
    with pytest.raises(WorkspaceError):
        workspace.publish(candidate["id"], "operational-initial", "must fail")
    assert workspace.active_id() == "operational-initial"


def test_demo_patch_cannot_override_imported_business_authorization(workspace):
    activate(workspace)
    source = workspace.import_document("TEST-FIXTURE-demo.txt", "text/plain", b"demo", [{"locator": "L1", "text": "demo"}], "synthetic")
    with pytest.raises(WorkspaceError) as error:
        workspace.propose({"parent_id": workspace.active_id(), "requester_id": "operator_847", "classes": ["TOXIC"],
                           "source_id": source["id"], "locator": "L1", "valid_from": None, "valid_until": None})
    assert error.value.status == 409


def test_rehashed_tampered_snapshot_cannot_detach_facts_from_originals(workspace):
    activate(workspace)
    result = workspace.check(request())
    exported = workspace.export(result["run_id"])
    tampered = copy.deepcopy(exported)
    tampered["version"]["snapshot"]["catalog"]["lots"]["batch_92"]["on_hand"] = 900
    tampered["version"]["sha256"] = digest(encode(tampered["version"]["snapshot"]).encode())
    tampered["run"]["result"]["snapshot_hash"] = tampered["version"]["sha256"]
    report = verify_evidence_export(tampered)
    assert not report["passed"]
    assert any(issue["code"] == "imported_source_mapping_mismatch" for issue in report["issues"])


@pytest.mark.parametrize("media,raw", [("application/json", b'{"same": {}, "same": {}}'),
                                      ("application/yaml", b"same: {}\nsame: {}\n")])
def test_duplicate_original_ids_rejected(workspace, media, raw):
    manifest, files, _ = bundle()
    files["lots.json"] = raw
    manifest["sources"]["lots"].update(media_type=media, sha256=digest(raw))
    with pytest.raises(WorkspaceError, match="duplicate"):
        workspace.import_ledger_bundle(manifest, files)

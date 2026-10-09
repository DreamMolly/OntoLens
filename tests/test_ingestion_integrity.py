import hashlib
import json
from pathlib import Path

import pytest
import yaml

from ontolens.asset_evaluation import evaluate_asset_recognition
from ontolens.documents import parse_document
from ontolens.workspace import Workspace, WorkspaceError


ROOT = Path(__file__).resolve().parents[1]


def test_csv_accepts_a_field_within_the_document_text_limit():
    field = "x" * 140_000

    media, chunks = parse_document("inventory.csv", field.encode("utf-8"))

    assert media == "text/csv"
    assert len(chunks) == 1
    assert chunks[0]["locator"] == "R1"
    assert json.loads(chunks[0]["text"]) == [field]


@pytest.mark.parametrize("raw", [b'name,class\n"stu01,ACID', b'"stu01"x,ACID\n'])
def test_csv_rejects_malformed_quoted_records(raw):
    with pytest.raises(WorkspaceError, match="CSV 格式无效"):
        parse_document("inventory.csv", raw)


def test_csv_multiline_quotes_keep_record_locations_and_source_hash(tmp_path):
    raw = '\ufeffperson,note\r\nstu01,"授权 ACID\r\n待审核"\r\n'.encode("utf-8")
    media, chunks = parse_document("inventory.csv", raw)
    workspace = Workspace(ROOT, tmp_path / "ingestion.sqlite3")

    document = workspace.import_document("inventory.csv", media, raw, chunks, "synthetic")
    stored = workspace.document(document["id"], include_raw=True)

    assert stored["raw"] == raw
    assert stored["sha256"] == hashlib.sha256(raw).hexdigest()
    assert [chunk["locator"] for chunk in stored["chunks"]] == ["R1", "R2"]
    assert json.loads(stored["chunks"][1]["text"]) == ["stu01", "授权 ACID\r\n待审核"]
    assets = workspace.recognize_assets(document["id"])
    assert assets["relations"]
    for relation in assets["relations"]:
        assert relation["source_id"] == document["id"]
        assert relation["locator"] == "R2"
        assert relation["quote"] == stored["chunks"][1]["text"]
        assert relation["status"] == "proposed"
        assert relation["review_required"] is True
    assert workspace.active_id() == "demo-initial"


@pytest.mark.parametrize("error_kind", ["missing", "extra"])
def test_asset_aggregate_does_not_hide_errors_repeated_in_another_case(tmp_path, error_kind):
    full_text = "stu01 授权 ACID，生效: 2026-10-01，有效至: 2026-12-31"
    correct = {
        "id": "correct", "title": "correct.md", "text": full_text,
        "expected_entities": [["Person", "stu01"], ["HazardClass", "ACID"]],
        "expected_relations": [["authorized_for", "stu01", "ACID"]],
        "expected_schema_candidates": [["authorized_for", "valid_from", "valid_until"]],
    }
    erroneous = dict(correct, id="erroneous", title="erroneous.md")
    if error_kind == "missing":
        erroneous["text"] = "stu01"
    else:
        for key in ("expected_entities", "expected_relations", "expected_schema_candidates"):
            erroneous[key] = []
    fixture = tmp_path / "asset-cases.yaml"
    fixture.write_text(yaml.safe_dump({"cases": [correct, erroneous]}, allow_unicode=True), encoding="utf-8")

    report = evaluate_asset_recognition(ROOT, fixture)

    assert report["aggregation"] == "micro_per_case"
    for field in ("entities", "relations", "schema_candidates"):
        aggregate = report["aggregate"][field]
        for metric in ("predicted", "expected", "correct"):
            assert aggregate[metric] == sum(case[field][metric] for case in report["cases"])
        assert aggregate["f1"] < 1.0
    metric = "recall" if error_kind == "missing" else "precision"
    assert report["aggregate"]["relations"][metric] == 0.5
    assert report["aggregate"]["schema_candidates"][metric] == 0.5

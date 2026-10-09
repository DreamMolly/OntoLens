import base64
import hashlib
import json
from pathlib import Path

import pytest

from ontolens.documents import parse_document
from ontolens.workspace import Workspace, encode


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path):
    return Workspace(ROOT, tmp_path / "workspace-integrity.sqlite3")


def request(**changes):
    return {
        "request_id": "integrity-check", "requester_id": "stu01", "lot_id": "lot_eth",
        "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL",
        "as_of": "2026-09-28", **changes,
    }


def publish_authorization(workspace):
    # A UTF-8 BOM, blank lines and CRLF cannot be recovered from parsed chunks.
    raw = b"\xef\xbb\xbf" + "# 合成变更\r\n\r\nstu01 授权只保留 ACID。\r\n".encode()
    media, chunks = parse_document("authorization.md", raw)
    source = workspace.import_document("authorization.md", media, raw, chunks, "synthetic")
    parent_id = workspace.active_id()
    candidate = workspace.propose({
        "parent_id": parent_id, "requester_id": "stu01", "classes": ["ACID"],
        "source_id": source["id"], "locator": "L3", "note": "合成来源复现检查",
        "valid_from": None, "valid_until": None,
    })
    published = workspace.publish(candidate["id"], parent_id, "仅作合成演示")
    return source, raw, published


def test_export_contains_original_bytes_and_all_snapshot_sources(workspace):
    source, raw, published = publish_authorization(workspace)
    unrelated = workspace.import_document(
        "unrelated.txt", "text/plain", b"not referenced", [], "private"
    )
    result = workspace.check(request())
    assert result["decision"]["reason_code"] == "CLASS_NOT_AUTHORIZED"

    # The actual web export must remain JSON serializable, including binary sources.
    bundle = json.loads(json.dumps(workspace.export(result["run_id"])))
    sources = {item["id"]: item for item in bundle["sources"]}
    snapshot = bundle["version"]["snapshot"]
    expected_ids = set(snapshot["provenance"].values()) | {
        item["source_id"] for item in snapshot["person_evidence"].values()
    }
    assert set(sources) == expected_ids
    assert unrelated["id"] not in sources
    assert base64.b64decode(sources[source["id"]]["raw_base64"], validate=True) == raw
    for item in sources.values():
        assert item["raw_encoding"] == "base64"
        decoded = base64.b64decode(item["raw_base64"], validate=True)
        assert hashlib.sha256(decoded).hexdigest() == item["sha256"]
        assert "raw" not in item
    for edge in result["evidence"]:
        original = sources[edge["source_id"]]
        assert original["sha256"] == edge["sha256"]
        assert {"locator": edge["locator"], "text": edge["quote"]} in original["chunks"]
    assert bundle["version"]["id"] == published["id"]
    assert hashlib.sha256(encode(snapshot).encode()).hexdigest() == result["snapshot_hash"]


def test_old_replay_stays_bound_to_original_sources_after_publish_and_rollback(workspace):
    original = workspace.check(request())
    before = workspace.export(original["run_id"])
    source, _, published = publish_authorization(workspace)
    assert workspace.check(request())["decision"]["action"] == "DENY"
    assert workspace.export(original["run_id"]) == before
    assert source["id"] not in {item["id"] for item in before["sources"]}

    workspace.rollback("demo-initial", published["id"], "恢复合成初始版本")
    assert workspace.check(request())["decision"]["action"] == "ALLOW"
    assert workspace.export(original["run_id"]) == before
    assert before["run"]["result"] == original
    assert before["version"]["id"] == original["version_id"] == "demo-initial"


def import_text(workspace, text):
    raw = text.encode()
    media, chunks = parse_document("term-boundaries.txt", raw)
    return workspace.import_document("term-boundaries.txt", media, raw, chunks, "synthetic")


@pytest.mark.parametrize("text", [
    "stu01 classical acidification study.",
    "stu01 class ACIDIFICATION TOXICITY DATABASE GENERALIZED.",
    "stu01 class 2ACID ACID2 ACID_VALUE PRE_ACID.",
])
def test_hazard_aliases_do_not_match_inside_english_identifiers(workspace, text):
    source = import_text(workspace, text)
    assets = workspace.recognize_assets(source["id"])
    assert not any(entity["type"] == "HazardClass" for entity in assets["entities"])
    assert workspace.suggest_candidates(source["id"]) == []
    assert assets["relations"] == []
    assert workspace.active_id() == "demo-initial"


@pytest.mark.parametrize("trigger", ["classical", "unauthorized", "sub_class", "class2"])
def test_authorization_trigger_must_be_a_complete_english_word(workspace, trigger):
    source = import_text(workspace, f"stu01 {trigger} ACID.")
    assets = workspace.recognize_assets(source["id"])
    assert any(entity["id"] == "ACID" for entity in assets["entities"])
    assert workspace.suggest_candidates(source["id"]) == []
    assert assets["relations"] == []


@pytest.mark.parametrize("text,classes,change_mode,valid_from,valid_until", [
    ("stu01 classes acid, FLAMMABLE.", ["ACID", "FLAMMABLE"], "add", None, None),
    ("stu01 authorize ACID.", ["ACID"], "add", None, None),
    ("stu01 authorizes ACID.", ["ACID"], "add", None, None),
    ("stu01 authorized ACID only from: 2026-10-01 until: 2026-12-31.",
     ["ACID"], "replace", "2026-10-01", "2026-12-31"),
    ("stu01授权仅保留酸，生效：2026-10-01，有效至：2026-12-31。",
     ["ACID"], "replace", "2026-10-01", "2026-12-31"),
    ("stu01授权ACID类别。", ["ACID"], "add", None, None),
])
def test_complete_english_and_chinese_terms_preserve_proposed_candidates(
    workspace, text, classes, change_mode, valid_from, valid_until
):
    source = import_text(workspace, text)
    candidates = workspace.suggest_candidates(source["id"])
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["proposed_classes"] == classes
    assert candidate["change_mode"] == change_mode
    assert candidate["valid_from"] == valid_from
    assert candidate["valid_until"] == valid_until
    assert candidate["quote"] == text
    assert candidate["source_id"] == source["id"]
    assert candidate["review_required"] is True
    assert candidate["status"] == "proposed"
    assets = workspace.recognize_assets(source["id"])
    assert {entity["id"] for entity in assets["entities"] if entity["type"] == "HazardClass"} == set(classes)
    assert {relation["object"] for relation in assets["relations"]} == set(classes)
    assert workspace.active_id() == "demo-initial"


def test_embedded_english_modifiers_do_not_replace_classes_or_set_dates(workspace):
    source = import_text(
        workspace, "stu01 authorized ACID; readonly therefrom: 2026-10-01 notuntil: 2026-12-31."
    )
    candidate = workspace.suggest_candidates(source["id"])[0]
    assert candidate["change_mode"] == "add"
    assert candidate["valid_from"] is None
    assert candidate["valid_until"] is None

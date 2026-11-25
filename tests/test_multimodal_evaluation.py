from pathlib import Path

import pytest

from scripts.evaluate_multimodal import evaluate


ROOT = Path(__file__).resolve().parents[1]


def test_multimodal_evaluation_exposes_missed_id_without_inventing_a_match(monkeypatch):
    monkeypatch.setattr("scripts.evaluate_multimodal.extract_image_text", lambda raw: [
        {"locator": "OCR1 (unreviewed)", "text": "1ot_eth FLAMMABLE"},
    ])
    report = evaluate(ROOT)
    cases = {case["id"]: case for case in report["cases"]}
    assert set(cases) == {"text", "csv", "image_ocr", "image_manual", "similar_id_control"}
    assert cases["image_ocr"]["missed"] == [["Lot", "lot_eth"]]
    assert not cases["image_ocr"]["unexpected"]
    assert cases["image_manual"]["missed"] == []
    assert cases["similar_id_control"]["unexpected"] == []
    assert report["active_snapshot_unchanged"] is True
    assert report["label_status"] == "developer_authored_synthetic"
    assert report["aggregate"]["recall"] == pytest.approx(8 / 9)

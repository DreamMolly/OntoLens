from pathlib import Path

from ontolens.asset_evaluation import evaluate_asset_recognition


ROOT = Path(__file__).resolve().parents[1]


def test_asset_recognition_fixture_is_reproducible():
    report = evaluate_asset_recognition(ROOT, ROOT / "data/evaluation/asset-recognition.yaml")
    assert report["fixture_version"] == "asset-recognition-synthetic-v1"
    assert len(report["cases"]) == 5
    for value in report["aggregate"].values():
        assert value["precision"] == 1.0
        assert value["recall"] == 1.0
        assert value["f1"] == 1.0

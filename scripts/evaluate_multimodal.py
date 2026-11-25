"""Compare ways of recognizing the same synthetic assets with local evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ontolens.asset_evaluation import score_matches
from ontolens.documents import parse_document
from ontolens.image_ocr import extract_image_text
from ontolens.workspace import Workspace


ROOT = Path(__file__).resolve().parents[1]


def evaluate(root: Path) -> dict:
    image = root / "data/demo/synthetic-asset-label.png"
    raw_image = image.read_bytes()
    transcript = image.with_suffix(".transcript.md").read_text(encoding="utf-8")
    hazard = ("HazardClass", "FLAMMABLE")
    expected_assets = {hazard, ("Lot", "lot_eth")}
    inputs = [
        ("text", "label.txt", "批次 lot_eth，类别 FLAMMABLE。".encode(), "", expected_assets),
        ("csv", "label.csv", b"lot_id,hazard_class\nlot_eth,FLAMMABLE\n", "", expected_assets),
        ("image_ocr", image.name, raw_image, "", expected_assets),
        ("image_manual", image.name, raw_image, transcript, expected_assets),
        ("similar_id_control", "ocr-like.txt", b"1ot_eth FLAMMABLE\n", "", {hazard}),
    ]
    reports = []
    all_predicted, all_expected = set(), set()
    with TemporaryDirectory(prefix="ontolens-multimodal-") as temporary:
        workspace = Workspace(root, Path(temporary) / "multimodal.sqlite3", seed_demo=True)
        initial = workspace.version()
        for case_id, name, raw, manual, expected in inputs:
            media_type, chunks = parse_document(name, raw, manual)
            if case_id == "image_ocr":
                chunks = extract_image_text(raw)
            source = workspace.import_document(name, media_type, raw, chunks, "synthetic",
                                               external_model_allowed=False)
            entities = workspace.recognize_assets(source["id"])["entities"]
            predicted = {(item["type"], item["id"]) for item in entities}
            all_predicted.update((case_id, *item) for item in predicted)
            all_expected.update((case_id, *item) for item in expected)
            reports.append({
                "id": case_id, "media_type": media_type, "input_sha256": source["sha256"],
                "entities": score_matches(predicted, expected), "expected": sorted(expected),
                "missed": [list(item) for item in sorted(expected - predicted)],
                "unexpected": [list(item) for item in sorted(predicted - expected)],
                "evidence": [{key: item[key] for key in ("type", "id", "locator", "quote")} for item in entities],
                "ocr_fragments": chunks if case_id == "image_ocr" else [],
            })
        final = workspace.version()
        unchanged = (initial["id"], initial["sha256"]) == (final["id"], final["sha256"])
    return {
        "schema": "ontolens-multimodal-evaluation-1",
        "label_status": "developer_authored_synthetic",
        "scope": "One synthetic label represented as text, CSV, OCR and manual transcript, plus a similar-ID control.",
        "reference_snapshot_sha256": initial["sha256"],
        "active_snapshot_unchanged": unchanged,
        "similar_id_control_passed": reports[-1]["entities"]["f1"] == 1.0,
        "cases": reports,
        "aggregate": score_matches(all_predicted, all_expected),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime/multimodal-evaluation.json")
    args = parser.parse_args()
    report = evaluate(ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "aggregate": report["aggregate"],
                      "active_snapshot_unchanged": report["active_snapshot_unchanged"],
                      "similar_id_control_passed": report["similar_id_control_passed"]}))
    return int(not (report["active_snapshot_unchanged"] and report["similar_id_control_passed"]))


if __name__ == "__main__":
    raise SystemExit(main())

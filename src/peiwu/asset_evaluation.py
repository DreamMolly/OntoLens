from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import yaml

from peiwu.workspace import Workspace


def _scores(predicted: set[tuple], expected: set[tuple]) -> dict[str, int | float]:
    correct = len(predicted & expected)
    precision = correct / len(predicted) if predicted else (1.0 if not expected else 0.0)
    recall = correct / len(expected) if expected else (1.0 if not predicted else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"predicted": len(predicted), "expected": len(expected), "correct": correct,
            "precision": precision, "recall": recall, "f1": f1}


def evaluate_asset_recognition(root: Path, fixture: Path) -> dict[str, Any]:
    payload = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("fixture needs a cases list")
    with tempfile.TemporaryDirectory() as directory:
        workspace = Workspace(root, Path(directory) / "asset-evaluation.sqlite3")
        case_reports = []
        all_entities: list[tuple[set[tuple], set[tuple]]] = []
        all_relations: list[tuple[set[tuple], set[tuple]]] = []
        all_schema: list[tuple[set[tuple], set[tuple]]] = []
        for case in payload["cases"]:
            raw = case["text"].encode("utf-8")
            document = workspace.import_document(
                case["title"], "text/plain", raw,
                [{"locator": "L1", "text": case["text"]}], "synthetic",
            )
            actual = workspace.recognize_assets(document["id"])
            entities = {(item["type"], item["id"]) for item in actual["entities"]}
            relations = {(item["type"], item["subject"], item["object"]) for item in actual["relations"]}
            schema = {(item["relation"], *item["properties"]) for item in actual["schema_candidates"]}
            expected_entities = {tuple(item) for item in case["expected_entities"]}
            expected_relations = {tuple(item) for item in case["expected_relations"]}
            expected_schema = {tuple(item) for item in case["expected_schema_candidates"]}
            entity_score = _scores(entities, expected_entities)
            relation_score = _scores(relations, expected_relations)
            schema_score = _scores(schema, expected_schema)
            case_reports.append({"id": case["id"], "entities": entity_score,
                                 "relations": relation_score, "schema_candidates": schema_score})
            all_entities.append((entities, expected_entities))
            all_relations.append((relations, expected_relations))
            all_schema.append((schema, expected_schema))
    def aggregate(items):
        # A correct match in one document must not cancel a missed or spurious
        # match in another. Preserve each case's identity when micro-averaging.
        predicted = {(case_index, *entry) for case_index, item in enumerate(items) for entry in item[0]}
        expected = {(case_index, *entry) for case_index, item in enumerate(items) for entry in item[1]}
        return _scores(predicted, expected)
    return {
        "fixture_version": payload.get("version"), "scope": payload.get("scope"),
        "aggregation": "micro_per_case",
        "cases": case_reports,
        "aggregate": {"entities": aggregate(all_entities), "relations": aggregate(all_relations),
                      "schema_candidates": aggregate(all_schema)},
        "notice": "合成回归夹具只验证当前目录/别名规则，不是行业资产识别或低资源本体算法效果。",
    }

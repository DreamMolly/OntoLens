import json
from pathlib import Path

from peiwu.cli import main

ROOT = Path(__file__).resolve().parents[1]


def _decide(capsys, version: str) -> tuple[int, str]:
    code = main(
        [
            "decide",
            "--catalog",
            str(ROOT / "data" / "catalog.yaml"),
            "--rules",
            str(ROOT / "data" / "rules" / f"{version}.yaml"),
            "--request",
            str(ROOT / "data" / "examples" / "i01.json"),
        ]
    )
    captured = capsys.readouterr()
    assert captured.err == ""
    return code, captured.out


def test_i01_decide_repeats_identical_json(capsys):
    expected = {
        "v1": {
            "request_id": "I01",
            "decision": {
                "action": "ALLOW",
                "approved_quantity": 100.0,
                "reason_code": "ALLOWED",
                "rule_version": "v1",
            },
        },
        "v2": {
            "request_id": "I01",
            "decision": {
                "action": "DENY",
                "approved_quantity": None,
                "reason_code": "SESSION_INCOMPATIBLE",
                "rule_version": "v2",
            },
        },
    }
    for version, payload in expected.items():
        first_code, first_out = _decide(capsys, version)
        second_code, second_out = _decide(capsys, version)
        assert first_code == 0
        assert second_code == 0
        assert first_out == second_out
        assert json.loads(first_out) == payload
        assert first_out == json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

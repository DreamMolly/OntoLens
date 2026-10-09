import pytest

from peiwu.jev_replay import build_record, replay_record


def live_result():
    return {"status": "ready", "request_count": 1, "input_hash": "a" * 64,
            "model": "jev-1.13.0", "resolved_model": "jev-1.13.0",
            "question_version": "peiwu-evidence-support-v2", "candidates": [{"jev_probability": 0.8}]}


def test_record_and_replay_are_explicitly_distinguished():
    record = build_record(live_result(), "synthetic test")
    replay = replay_record(record)
    assert record["format"] == "peiwu-jev-replay-1"
    assert record["live_request_sent"] is True
    assert replay["status"] == "replay"
    assert replay["replay"] is True
    assert replay["live_request_sent"] is False
    assert replay["request_count"] == 0
    assert replay["code"] == "recorded_replay"
    assert replay["input_hash"] == "a" * 64


def test_record_rejects_fallback_or_missing_hash():
    with pytest.raises(ValueError):
        build_record({"status": "unavailable", "request_count": 0}, "synthetic")
    with pytest.raises(ValueError):
        build_record({"status": "ready", "request_count": 1}, "synthetic")


def test_replay_rejects_invalid_record():
    with pytest.raises(ValueError):
        replay_record({"format": "wrong"})
    with pytest.raises(ValueError):
        replay_record({"format": "peiwu-jev-replay-1", "recorded_result": {"status": "error", "request_count": 1}})

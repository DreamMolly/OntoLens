from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


FORMAT = "peiwu-jev-replay-1"


def build_record(result: dict[str, Any], scope: str) -> dict[str, Any]:
    if result.get("status") != "ready" or result.get("request_count", 0) < 1:
        raise ValueError("only a successful live JEV result can be recorded")
    if not isinstance(result.get("input_hash"), str) or len(result["input_hash"]) != 64:
        raise ValueError("record requires an input_hash")
    return {"format": FORMAT, "recorded_at": datetime.now(timezone.utc).isoformat(),
            "scope": scope, "live_request_sent": True, "recorded_result": copy.deepcopy(result)}


def replay_record(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("format") != FORMAT or not isinstance(record.get("recorded_result"), dict):
        raise ValueError("invalid JEV replay record")
    result = copy.deepcopy(record["recorded_result"])
    if result.get("status") != "ready" or result.get("request_count", 0) < 1:
        raise ValueError("replay record does not contain a successful live result")
    result.update({"status": "replay", "replay": True, "live_request_sent": False,
                   "request_count": 0, "recorded_request_count": record.get("recorded_result", {}).get("request_count"),
                   "reason": "录制回放；未请求 JEV 服务", "code": "recorded_replay"})
    return result

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from peiwu.model_explain import normalize_protocol


ROOT = Path(__file__).resolve().parents[1]


def load_local_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name and not os.environ.get(name):
            os.environ[name] = value.strip()


def local_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise argparse.ArgumentTypeError("Only a local HTTP origin is allowed")
    return value.rstrip("/")


def configuration() -> dict:
    protocol = normalize_protocol(os.getenv("PEIWU_MODEL_PROTOCOL"))
    return {"configured": bool(os.getenv("PEIWU_MODEL_BASE_URL") and os.getenv("PEIWU_MODEL_NAME")),
            "protocol": protocol, "model": os.getenv("PEIWU_MODEL_NAME", ""),
            "base_url_present": bool(os.getenv("PEIWU_MODEL_BASE_URL")),
            "api_key_present": bool(os.getenv("PEIWU_MODEL_API_KEY")),
            "live_request_sent": False}


def synthetic_request() -> dict:
    return {"request_id": "MODEL-EXPLAIN-01", "requester_id": "stu01", "lot_id": "lot_eth",
            "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL",
            "as_of": "2026-09-23"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight or explicitly test the optional local model explanation route")
    parser.add_argument("--url", type=local_url, default="http://127.0.0.1:8765")
    parser.add_argument("--live", action="store_true", help="Send one synthetic explanation request to the local workbench")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    load_local_env(ROOT / ".env")
    if not args.live:
        result = {"mode": "preflight", "scope": "local workbench only; no model request", "configuration": configuration()}
    else:
        with httpx.Client(base_url=args.url, timeout=35, trust_env=False) as client:
            status = client.get("/api/status")
            status.raise_for_status()
            csrf = status.json()["csrf_token"]
            headers = {"X-Peiwu-Token": csrf}
            check = client.post("/api/check", headers=headers, json=synthetic_request())
            check.raise_for_status()
            run_id = check.json()["run_id"]
            explanation = client.post(f"/api/runs/{run_id}/explain", headers=headers)
            result = {"mode": "live", "scope": "one synthetic local explanation request",
                      "live_request_sent": True, "http_status": explanation.status_code,
                      "run_id": run_id, "configuration": configuration()}
            if explanation.status_code == 200:
                payload = explanation.json()
                result.update({"model": payload.get("model"), "protocol": payload.get("protocol"),
                               "text_returned": isinstance(payload.get("text"), str), "verified": False})
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output is not None:
        output = args.output.resolve()
        if not output.is_relative_to(ROOT) or output.suffix != ".json":
            parser.error("Output must be a JSON file inside the project")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if not args.live or result.get("http_status") == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Check the optional JEV evidence layer without using real data by default."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from peiwu.jev import JevReranker
from peiwu.jev_replay import build_record, replay_record
from peiwu.workspace import Workspace


ROOT = Path(__file__).resolve().parents[1]


def load_local_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if name and not os.environ.get(name):
            os.environ[name] = value


def main() -> int:
    load_local_env(ROOT / ".env")
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="Send one synthetic query to the configured JEV endpoint")
    mode.add_argument("--replay", type=Path, default=None, help="Replay a recorded JEV result without a network request")
    parser.add_argument("--record-output", type=Path, default=None, help="Save a successful live result as a replay record")
    parser.add_argument("--query", default=None, help="Synthetic relevance query; fixed for review tasks")
    parser.add_argument("--task", choices=["relevance", "citation_review", "change_review", "relation_review"], default="relevance")
    parser.add_argument("--database", type=Path, default=ROOT / ".runtime" / "jev-preflight.sqlite3")
    args = parser.parse_args()
    if args.record_output is not None and not args.live:
        parser.error("--record-output requires --live")
    for path in (args.database, args.record_output, args.replay):
        if path is not None and not path.resolve().is_relative_to(ROOT):
            parser.error("All database and replay paths must stay inside the project")
    if args.replay is not None:
        replay = replay_record(json.loads(args.replay.resolve().read_text(encoding="utf-8")))
        print(json.dumps({"mode": "replay", "live_request_sent": False, "result": replay},
                         ensure_ascii=False, indent=2))
        return 0
    if args.task in {"citation_review", "change_review", "relation_review"} and args.query is not None:
        parser.error("review tasks use a fixed synthetic statement; arbitrary live claims are not authorized")
    if not args.database.resolve().is_relative_to(ROOT):
        parser.error("Database must stay inside the project")
    if not args.live and args.task == "relevance":
        result = {
            "mode": "preflight",
            "live_request_sent": False,
            "configuration": JevReranker().configuration(),
            "next": "Set TYPESAFE_API_KEY and rerun with --live to verify one synthetic request.",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    workspace = Workspace(ROOT, args.database)
    if args.task == "citation_review":
        version = workspace.version("demo-initial")
        source = workspace.document(version["snapshot"]["provenance"]["issues"])
        chunk = next(item for item in source["chunks"] if item["locator"] == "$.stu03")
        citation = {"source_id": source["id"], "sha256": source["sha256"],
                    "locator": chunk["locator"], "quote": chunk["text"]}
        configuration = workspace.rerank_evidence(
            "合成记录显示 stu03 未归还 OXIDIZER 类物料。", "demo-initial", 1,
            citations=[citation], allow_live=args.live, synthetic_claim=True,
        )
    elif args.task == "change_review":
        version = workspace.version("demo-initial")
        candidates = workspace.search("stu01", limit=2, version_id=version["id"])
        configuration = JevReranker().rerank(
            "合成授权变更：stu01 的 ACID 类别有效期发生变化；哪些历史申请应优先人工复核？",
            [{**item, "kind": "synthetic", "external_model_allowed": True} for item in candidates],
            limit=2, allow_live=args.live, purpose="change_review", synthetic_claim=True,
        )
    elif args.task == "relation_review":
        version = workspace.version("demo-initial")
        candidates = workspace.search("stu01", limit=2, version_id=version["id"])
        candidates = [{**item, "kind": "synthetic", "external_model_allowed": True,
                       "relation_subject": "stu01", "relation_type": "authorized_for",
                       "relation_object": "ACID"} for item in candidates]
        configuration = JevReranker().rerank(
            "合成来源是否支持 proposed 关系：stu01 authorized_for ACID？",
            candidates, limit=2, allow_live=args.live, purpose="relation_review", synthetic_claim=True,
        )
    else:
        configuration = workspace.rerank_evidence(args.query or "stu03 授权和未归还类别", limit=5, allow_live=True)
    print(json.dumps({"mode": "live" if args.live else "local_citation_preflight",
                      "live_request_sent": configuration["request_count"] > 0,
                      "result": configuration}, ensure_ascii=False, indent=2))
    if args.record_output is not None and args.live and configuration["status"] == "ready":
        record = build_record(configuration, "synthetic verify_jev task")
        args.record_output.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.record_output.resolve().write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"record_output": str(args.record_output.resolve())}, ensure_ascii=False))
    if not args.live:
        citation_ok = args.task == "citation_review" and configuration["citation_check"]["status"] == "passed"
        review_ok = args.task in {"change_review", "relation_review"} and configuration["status"] == "unavailable"
        return 0 if (citation_ok or review_ok) and configuration["request_count"] == 0 else 1
    return 0 if configuration["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())

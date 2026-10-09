"""Command line for decisions, evaluation, and promotion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ontolens.catalog import load_catalog
from ontolens.checker import decide
from ontolens.evaluate import evaluate, load_cases
from ontolens.gate import read_text, review_promotion
from ontolens.rules import load_rules


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ontolens")
    sub = parser.add_subparsers(dest="command", required=True)

    decide_cmd = sub.add_parser("decide")
    decide_cmd.add_argument("--catalog", default="data/catalog.yaml")
    decide_cmd.add_argument("--rules", required=True)
    decide_cmd.add_argument("--request", required=True)

    eval_cmd = sub.add_parser("eval")
    eval_cmd.add_argument("--catalog", default="data/catalog.yaml")
    eval_cmd.add_argument("--rules", required=True)
    eval_cmd.add_argument("--cases", required=True)
    eval_cmd.add_argument("--expect", default="gold", choices=("gold", "gold_v1", "gold_v2"))

    promote_cmd = sub.add_parser("promote")
    promote_cmd.add_argument("--catalog", default="data/catalog.yaml")
    promote_cmd.add_argument("--baseline", required=True)
    promote_cmd.add_argument("--candidate", required=True)
    promote_cmd.add_argument("--regression", default="data/cases/regression.yaml")
    promote_cmd.add_argument("--incidents", default="data/cases/incidents.yaml")
    promote_cmd.add_argument("--heldout", default="data/cases/heldout.yaml")

    args = parser.parse_args(argv)
    if args.command == "decide":
        return _decide(args)
    if args.command == "eval":
        return _eval(args)
    return _promote(args)


def _decide(args: argparse.Namespace) -> int:
    catalog = load_catalog(args.catalog)
    rules = load_rules(args.rules)
    request = _load_request(args.request)
    decision = decide(catalog, rules, request)
    _print({"request_id": request.get("request_id"), "decision": decision.as_dict()})
    return 0


def _eval(args: argparse.Namespace) -> int:
    catalog = load_catalog(args.catalog)
    rules = load_rules(args.rules)
    report = evaluate(catalog, rules, load_cases(args.cases), expect=args.expect)
    _print(report)
    return 0 if report["exact_match"] == report["total"] else 1


def _promote(args: argparse.Namespace) -> int:
    catalog = load_catalog(args.catalog)
    baseline = load_rules(args.baseline)
    candidate = load_rules(args.candidate)
    report = review_promotion(
        catalog,
        baseline,
        candidate,
        load_cases(args.regression),
        load_cases(args.incidents),
        load_cases(args.heldout),
        candidate_text=read_text(args.candidate),
    )
    _print(report)
    return 0 if report["accepted"] else 1


def _load_request(value: str) -> dict[str, Any]:
    path = Path(value)
    raw = path.read_text(encoding="utf-8") if path.exists() else value
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("request must be a JSON object")
    return data


def _print(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())

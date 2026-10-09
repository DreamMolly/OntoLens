from __future__ import annotations

import argparse
import json
from pathlib import Path

from ontolens.asset_evaluation import evaluate_asset_recognition


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=ROOT / "data/evaluation/asset-recognition.yaml")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_asset_recognition(ROOT, args.fixture)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

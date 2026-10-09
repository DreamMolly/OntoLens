"""Verify an offline public corpus and write only its dedicated verification report."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ontolens.public_corpus import PublicCorpusError, verify_public_corpus  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/public/official-lab-safety")
    args = parser.parse_args(argv)
    try:
        report = verify_public_corpus(args.corpus)
    except PublicCorpusError as exc:
        report = {"schema_version": "peiwu-public-corpus-verification-1", "passed": False,
                  "integrity_passed": False, "error": str(exc), "external_request_sent": False,
                  "production_database_used": False, "business_checker_called": False}
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["corpus_path"] = str(args.corpus.resolve())
    report["code_input_hashes"] = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in ("src/ontolens/public_corpus.py", "src/ontolens/workspace.py", "scripts/verify_public_corpus.py")}
    destination = ROOT / "artifacts/public-corpus-verification.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(destination),
                      "counts": report.get("counts"), "error": report.get("error")}, ensure_ascii=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

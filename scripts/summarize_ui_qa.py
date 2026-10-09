"""Publish portable UI receipts only when JUnit and fixture hashes agree."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]


def summarize(junit: Path, suite: str, runtime: str, output: str) -> None:
    document = ElementTree.parse(junit)
    cases = [case for case in document.iter("testcase")
             if case.get("classname", "").split(".")[-1] == suite]
    if len(cases) != 6 or any(case.find(tag) is not None for case in cases
                              for tag in ("failure", "error", "skipped")):
        raise ValueError("UI suite must contain six successful JUnit cases: " + suite)
    names = ("app.js", "style.css", "index.html", "date-controls.js")
    hashes = {name: hashlib.sha256((ROOT / "src/ontolens/static" / name).read_bytes()).hexdigest()
              for name in names}
    test_path = ROOT / "tests" / (suite + ".py")
    records = []
    for case in cases:
        record = json.loads((ROOT / ".runtime" / runtime / (case.get("name") + ".json")).read_text(encoding="utf-8"))
        if (record.get("page_errors") or record.get("external_browser_requests")
                or not record.get("static_sha256")
                or any(hashes.get(name) != value for name, value in record["static_sha256"].items())):
            raise ValueError("UI receipt errors or source mismatch: " + case.get("name"))
        if suite == "test_date_picker_interactions" and record.get("api_write_requests"):
            raise ValueError("Date interactions sent an API write")
        records.append({"name": case.get("name"), "status": "passed", "seconds": float(case.get("time", "0"))})
    receipt = {
        "format": "ontolens-ui-qa-1", "status": "passed",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Isolated synthetic Playwright fixtures; not live industry, real device or screen reader validation",
        "tests": len(records), "failures": 0, "errors": 0,
        "page_errors": 0, "external_browser_requests": 0,
        "static_sha256": hashes,
        "test_sha256": hashlib.sha256(test_path.read_bytes()).hexdigest(),
        "validation_command": ".venv/Scripts/python.exe -m pytest -q",
        "cases": records,
    }
    if suite == "test_date_picker_interactions":
        receipt["api_write_requests"] = 0
    (ROOT / "artifacts" / output).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output + ": verified")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args()
    summarize(args.junit, "test_select_interactions", "select-final-qa", "workbench-select-interaction-report.json")
    summarize(args.junit, "test_date_picker_interactions", "date-picker-qa", "workbench-date-interaction-report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

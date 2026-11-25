import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_competition_demo_uses_isolated_state_and_verifies_both_exports(tmp_path):
    database = tmp_path / "untouched.sqlite3"
    env = {**os.environ, "ONTOLENS_WORKSPACE_MODE": "operational",
           "ONTOLENS_AUTH_FILE": str(tmp_path / "absent-accounts.json"), "ONTOLENS_DB": str(database)}
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "scripts/verify_competition_demo.py"),
         "--output-dir", str(tmp_path / "demo")],
        env=env, cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=45,
    )
    assert result.returncode == 0, result.stderr
    output = Path(json.loads(result.stdout)["output"])
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["passed"] and not database.exists()
    assert report["scope"] == "synthetic_demo"
    assert [run["action"] for run in report["runs"]] == ["ALLOW", "DENY", "ALLOW"]
    assert [run["version_id"] for run in report["runs"]][::2] == ["demo-initial", "demo-initial"]
    assert report["runs"][1]["version_id"] != "demo-initial"
    for phase in ("before", "after"):
        assert (output / f"{phase}.json").is_file()
        verification = json.loads((output / f"{phase}-verification.json").read_text(encoding="utf-8"))
        assert verification["passed"]

"""Fetch the pinned optional upstream into a new directory without replacing local state."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def git(*arguments: str, cwd: Path) -> str:
    result = subprocess.run(["git", *arguments], cwd=cwd, text=True,
                            encoding="utf-8", capture_output=True, timeout=300)
    if result.returncode:
        raise RuntimeError("Git operation failed: " + result.stderr.strip()[:1200])
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Fetch only if third_party/nexent does not exist")
    args = parser.parse_args()
    specification = json.loads((ROOT / "nexent/upstream.json").read_text(encoding="utf-8"))
    if (specification.get("schema_version") != "ontolens-nexent-upstream-1"
            or specification.get("url") != "https://github.com/ModelEngine-Group/nexent.git"
            or not re.fullmatch(r"[0-9a-f]{40}", specification.get("commit", ""))
            or specification.get("destination") != "third_party/nexent"):
        raise ValueError("Invalid upstream specification")
    destination = ROOT / "third_party/nexent"
    expected = specification["commit"]
    if destination.exists():
        marker = destination / ".pinned-commit"
        if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != expected:
            raise ValueError("Existing upstream has a different or missing pin; no files changed")
        if (destination / ".git").exists():
            if git("rev-parse", "HEAD", cwd=destination) != expected:
                raise ValueError("Existing Git revision differs from the pin; no files changed")
            state = "existing_git_revision_matches"
        else:
            state = "existing_archive_marker_matches_vcs_unverified"
        print(json.dumps({"status": state, "commit": expected, "changed": False}))
        return 0
    if not args.apply:
        print(json.dumps({"status": "upstream_not_present", "commit": expected,
                          "changed": False, "next_step": "Run with --apply for the optional upstream source"}))
        return 0
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="nexent-bootstrap-", dir=runtime) as temporary:
        staging = Path(temporary) / "nexent"
        git("clone", "--filter=blob:none", "--no-checkout", specification["url"], str(staging), cwd=ROOT)
        git("checkout", "--detach", expected, cwd=staging)
        if git("rev-parse", "HEAD", cwd=staging) != expected:
            raise ValueError("Fetched upstream revision did not match")
        (staging / ".pinned-commit").write_text(expected + "\n", encoding="utf-8")
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():
            raise ValueError("Upstream destination appeared during fetch; no existing files changed")
        staging.rename(destination)
    print(json.dumps({"status": "pinned_upstream_fetched", "commit": expected,
                      "changed": True, "notice": "Source only; no credentials or deployment state created"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

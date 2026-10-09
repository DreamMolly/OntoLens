"""Validate public excerpts; explicitly import them into a stopped local workbench."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ontolens.public_corpus import load_public_corpus  # noqa: E402
from ontolens.workspace import Workspace, encode  # noqa: E402


def expected_documents(corpus):
    return [
        {
            "public_id": document["id"],
            "title": f'{document["title"]} · {document["published_at"]} · {document["id"]}',
            "raw": corpus.raw_excerpts[document["id"]],
            "sha256": document["excerpt_sha256"],
            "chunks": [{"locator": passage["locator"], "text": passage["quote"]}
                       for passage in document["passages"]],
        }
        for document in corpus.manifest["documents"]
    ]


def plan_import(connection, expected):
    """Check every canonical title before any insert; never repair conflicts."""
    plan = []
    for item in expected:
        rows = [] if connection is None else connection.execute(
            "SELECT * FROM documents WHERE title=?", (item["title"],)
        ).fetchall()
        if len(rows) > 1:
            raise ValueError(f"Duplicate canonical title: {item['public_id']}")
        if rows:
            stored = rows[0]
            if not (
                stored["kind"] == "public"
                and stored["external_model_allowed"] == 0
                and stored["sha256"] == item["sha256"]
                and bytes(stored["raw"]) == item["raw"]
                and hashlib.sha256(bytes(stored["raw"])).hexdigest() == item["sha256"]
                and json.loads(stored["chunks"]) == item["chunks"]
            ):
                raise ValueError(f"Existing source conflicts with verified excerpt: {item['public_id']}")
        plan.append({**item, "existing_id": rows[0]["id"] if rows else None})
    return plan


def business_state(connection):
    """Capture active version and all stored snapshots without reinitializing them."""
    active = connection.execute("SELECT value FROM settings WHERE key='active'").fetchone()
    if active is None:
        raise ValueError("Existing database has no active workbench; use a new database path")
    versions = [dict(row) for row in connection.execute("SELECT * FROM versions ORDER BY id")]
    return {"active_id": active["value"],
            "versions_sha256": hashlib.sha256(encode(versions).encode("utf-8")).hexdigest()}


def inspect_existing(database, expected):
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        state = business_state(connection)
        return plan_import(connection, expected), state


def run(database, corpus_path, apply):
    corpus = load_public_corpus(corpus_path)
    expected = expected_documents(corpus)
    existed = database.exists()
    if existed:
        plan, state_before = inspect_existing(database, expected)
    else:
        plan, state_before = plan_import(None, expected), None
    report = {
        "schema_version": "peiwu-public-corpus-import-1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if apply else "dry_run",
        "database": str(database),
        "database_existed": existed,
        "manifest_sha256": corpus.manifest_sha256,
        "documents": len(expected),
        "passages": sum(len(item["chunks"]) for item in expected),
        "would_import": sum(item["existing_id"] is None for item in plan),
        "imported": 0,
        "skipped": sum(item["existing_id"] is not None for item in plan),
        "database_initialized": False,
        "external_request_sent": False,
        "external_model_allowed": False,
        "business_checker_called": False,
        "business_snapshot_changed": False,
        "ledger_imported": False,
        "notice": "Public excerpts only; no domain-reviewed gold standard or business authorization.",
    }
    if not apply:
        report.update(passed=True, state_before=state_before, state_after=state_before)
        return report

    if not existed:
        # Only explicit apply can create the usual initial synthetic workbench.
        workspace = Workspace(ROOT, database)
        report["database_initialized"] = True
    else:
        # Avoid constructor migrations, reseeding, or permission repairs in an
        # existing workbench: this command changes only public sources and audit.
        workspace = Workspace.__new__(Workspace)
        workspace.root, workspace.database = ROOT, database
    with workspace.connect(write=True) as connection:
        state_before = business_state(connection)
        plan = plan_import(connection, expected)
        imported, skipped = [], []
        for item in plan:
            if item["existing_id"] is not None:
                skipped.append(item["public_id"])
                continue
            source_id = workspace._insert_document(
                connection, item["title"], "text/plain", item["raw"], item["chunks"], "public", False
            )
            workspace._event(connection, "source_imported", {
                "source_id": source_id, "kind": "public", "external_model_allowed": False,
                "public_corpus_id": item["public_id"], "manifest_sha256": corpus.manifest_sha256,
            })
            imported.append(item["public_id"])
        state_after = business_state(connection)
        if state_after != state_before:
            raise ValueError("Business snapshot changed during import; transaction rolled back")
        # Validate inserted raw bytes, hashes, kinds and exact physical-line chunks.
        if any(item["existing_id"] is None for item in plan_import(connection, expected)):
            raise ValueError("Incomplete public import; transaction rolled back")
    report.update(passed=True, imported=len(imported), skipped=len(skipped),
                  imported_ids=imported, skipped_ids=skipped,
                  state_before=state_before, state_after=state_after)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / ".runtime/workbench.sqlite3")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/public/official-lab-safety")
    parser.add_argument("--apply", action="store_true", help="Import into the selected database; stop its server first")
    args = parser.parse_args(argv)
    try:
        report = run(args.database.resolve(), args.corpus, args.apply)
    except (OSError, ValueError, sqlite3.Error, KeyError, TypeError) as exc:
        report = {"schema_version": "peiwu-public-corpus-import-1", "passed": False,
                  "mode": "apply" if args.apply else "dry_run", "error": str(exc),
                  "external_request_sent": False}
    destination = ROOT / ".runtime/public-corpus-import-receipt.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "mode": report["mode"],
                      "would_import": report.get("would_import"), "imported": report.get("imported"),
                      "skipped": report.get("skipped"), "error": report.get("error"),
                      "receipt": str(destination)}, ensure_ascii=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

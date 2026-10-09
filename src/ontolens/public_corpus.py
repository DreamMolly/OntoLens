"""Offline public-excerpt integrity and developer-authored lexical fixtures.

This module never calls the business decision checker, an external model, or a
source website. Local byte integrity is not source authenticity or legal review.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory
from urllib.parse import parse_qsl, urlsplit

from ontolens.workspace import Workspace


SCHEMA_VERSION = "ontolens-public-corpus-1"
SCOPE = "public_documents_with_synthetic_ledger"
LABEL_STATUS = "developer_authored_unreviewed"
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class PublicCorpusError(ValueError):
    """A corpus fails its local, fail-closed data contract."""


def _require(condition, message):
    if not condition:
        raise PublicCorpusError(message)


def _text(value, name):
    _require(isinstance(value, str) and bool(value.strip()), f"{name}: nonempty string required")
    return value


def _object(value, name):
    _require(isinstance(value, dict), f"{name}: object required")
    return value


def _records(value, name):
    _require(isinstance(value, list) and bool(value), f"{name}: nonempty array required")
    seen = set()
    for record in value:
        _object(record, name)
        identifier = record.get("id")
        _require(isinstance(identifier, str) and ID_PATTERN.fullmatch(identifier), f"{name}: invalid id")
        _require(identifier not in seen, f"{name}: duplicate id {identifier}")
        seen.add(identifier)
    return value


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise PublicCorpusError(f"non-finite JSON value: {value}")


def _public_url(value):
    value = _text(value, "url")
    _require(not any(char.isspace() for char in value) and "\\" not in value, "url: invalid characters")
    try:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise PublicCorpusError("url: malformed URL") from exc
    _require(parsed.scheme in ("http", "https") and hostname and parsed.username is None
             and parsed.password is None and port in (None, 80, 443),
             "url: public HTTP(S) source without credentials required")
    _require(hostname != "localhost" and not hostname.endswith((".localhost", ".local", ".internal")),
             "url: local host is not a public source")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        _require("." in hostname and not hostname.replace(".", "").isdigit(), "url: public hostname required")
    else:
        _require(address.is_global, "url: non-public IP address")
    secret_keys = {"token", "access_token", "api_key", "apikey", "password", "secret", "authorization"}
    _require(not any(key.lower() in secret_keys for key, _ in parse_qsl(parsed.query)), "url: credentials in query")


def _excerpt_path(root, value):
    value = _text(value, "excerpt_path")
    relative = Path(value)
    windows = PureWindowsPath(value)
    _require(not relative.is_absolute() and not windows.is_absolute() and not windows.drive
             and ".." not in relative.parts and ".." not in windows.parts and ":" not in value,
             "excerpt_path: relative contained path required")
    path = (root / relative).resolve()
    _require(path.is_relative_to(root) and path != root, "excerpt_path: path escapes corpus root")
    return path


@dataclass(frozen=True)
class PublicCorpus:
    root: Path
    manifest: dict
    manifest_sha256: str
    raw_excerpts: dict[str, bytes]
    data_hashes: dict[str, str]


def load_public_corpus(corpus: Path) -> PublicCorpus:
    """Validate structure and exact bytes before any Workspace import."""
    root = Path(corpus).resolve()
    try:
        raw_manifest = (root / "manifest.json").read_bytes()
        manifest = json.loads(raw_manifest.decode("utf-8"), object_pairs_hook=_strict_object,
                              parse_constant=_reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublicCorpusError(f"manifest unreadable or malformed: {exc}") from exc
    _object(manifest, "manifest")
    _require(manifest.get("schema_version") == SCHEMA_VERSION, "unsupported schema_version")
    _require(manifest.get("scope") == SCOPE, "scope must preserve public/synthetic boundary")
    documents = _records(manifest.get("documents"), "documents")
    bundles = _records(manifest.get("bundles"), "bundles")
    questions = _records(manifest.get("questions"), "questions")
    document_map = {item["id"]: item for item in documents}
    raw_excerpts, paths, passage_keys = {}, set(), set()
    data_hashes = {"manifest.json": hashlib.sha256(raw_manifest).hexdigest()}
    for document in documents:
        source_id = document["id"]
        for field in ("title", "publisher", "source_family"):
            _text(document.get(field), f"{source_id}.{field}")
        _public_url(document.get("url"))
        try:
            date.fromisoformat(_text(document.get("published_at"), "published_at"))
        except ValueError as exc:
            raise PublicCorpusError("published_at: ISO calendar date required") from exc
        _require(document.get("kind", "public") == "public", "document kind must be public")
        _require(document.get("external_model_allowed", False) is False, "external model use must remain disabled")
        for forbidden in ("requester_id", "person_id", "private_identity", "credentials"):
            _require(forbidden not in document, f"document contains private identity field: {forbidden}")
        path = _excerpt_path(root, document.get("excerpt_path"))
        _require(path not in paths, "duplicate excerpt_path")
        paths.add(path)
        try:
            raw = path.read_bytes()
            lines = raw.decode("utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise PublicCorpusError(f"excerpt unreadable or not UTF-8: {source_id}") from exc
        digest = hashlib.sha256(raw).hexdigest()
        expected_hash = document.get("excerpt_sha256")
        _require(isinstance(expected_hash, str) and SHA_PATTERN.fullmatch(expected_hash)
                 and digest == expected_hash, f"excerpt hash mismatch: {source_id}")
        _require(bool(lines) and all(line.strip() for line in lines), "excerpts require nonempty physical lines")
        passages = document.get("passages")
        _require(isinstance(passages, list) and len(passages) == len(lines), "passages must cover every excerpt line")
        for number, (line, passage) in enumerate(zip(lines, passages), 1):
            _object(passage, "passage")
            _require(passage.get("locator") == f"L{number}", "passage locators must be consecutive physical line numbers")
            _text(passage.get("source_locator"), "source_locator")
            _require(passage.get("quote") == line, f"quote mismatch: {source_id}#L{number}")
            passage_keys.add((source_id, passage["locator"]))
        raw_excerpts[source_id] = raw
        data_hashes[path.relative_to(root).as_posix()] = digest
    ledger_map = {}
    if "synthetic_ledger" in manifest:
        for ledger in _records(manifest["synthetic_ledger"], "synthetic_ledger"):
            _require(ledger.get("kind") == "synthetic", "ledger kind must remain synthetic")
            _text(ledger.get("notice"), "ledger.notice")
            path = _excerpt_path(root, ledger.get("path"))
            _require(path not in paths, "duplicate data path")
            paths.add(path)
            try:
                raw = path.read_bytes()
            except OSError as exc:
                raise PublicCorpusError("synthetic ledger unreadable") from exc
            digest = hashlib.sha256(raw).hexdigest()
            _require(bool(raw) and ledger.get("sha256") == digest, "synthetic ledger hash mismatch")
            data_hashes[path.relative_to(root).as_posix()] = digest
            ledger_map[ledger["id"]] = ledger
    bundle_map = {}
    for bundle in bundles:
        ids = bundle.get("source_ids")
        _require(isinstance(ids, list) and bool(ids) and all(isinstance(item, str) for item in ids),
                 "bundle.source_ids: nonempty string array required")
        _require(len(ids) == len(set(ids)), "duplicate source reference in bundle")
        _require(set(ids) <= document_map.keys(), "bundle references unknown document")
        if "ledger_id" in bundle:
            _require(isinstance(bundle["ledger_id"], str) and bundle["ledger_id"] in ledger_map,
                     "bundle references unknown synthetic ledger")
        bundle_map[bundle["id"]] = set(ids)
    for question in questions:
        for field in ("question", "query"):
            _text(question.get(field), f"question.{field}")
        _require(len(question["query"]) <= 300, "query exceeds Workspace query limit")
        bundle_id = question.get("bundle_id")
        _require(isinstance(bundle_id, str) and bundle_id in bundle_map, "question references unknown bundle")
        _require(question.get("label_status") == LABEL_STATUS, "labels must remain developer_authored_unreviewed")
        _require(question.get("expected") == {"status": "needs_review", "decision": None},
                 "expected must remain needs_review with null decision; no decision gold standard")
        evidence = question.get("required_evidence")
        _require(isinstance(evidence, list) and len(evidence) >= 2, "cross-document question requires at least two evidence references")
        keys = set()
        for edge in evidence:
            _object(edge, "required_evidence")
            source_id, locator = edge.get("source_id"), edge.get("locator")
            _require(isinstance(source_id, str) and isinstance(locator, str), "evidence source and locator must be strings")
            key = (source_id, locator)
            _require(key not in keys, "duplicate required evidence")
            _require(key in passage_keys and source_id in bundle_map[bundle_id], "evidence outside bundle or unknown locator")
            keys.add(key)
        _require(len({source_id for source_id, _ in keys}) >= 2, "required evidence must span different documents")
    return PublicCorpus(root, manifest, data_hashes["manifest.json"], raw_excerpts, data_hashes)


class _PublicOnlyWorkspace(Workspace):
    def _seed(self):
        """Intentionally omit demo documents and decision versions in temporary DBs."""

    def _insert_document(self, connection, title, media_type, raw, chunks, kind, external_model_allowed=False):
        # Workspace.search breaks score ties by internal ID. Stabilize those IDs
        # in this disposable database so the 30-hit cutoff is reproducible too.
        sequence = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        source_id = super()._insert_document(connection, title, media_type, raw, chunks, kind, external_model_allowed)
        stable_id = f"public_{sequence:06d}_{hashlib.sha256(raw).hexdigest()[:16]}"
        connection.execute("UPDATE documents SET id=? WHERE id=?", (stable_id, source_id))
        return stable_id


def public_document_lookup(workspace: Workspace, query: str, source_map: dict[str, dict]) -> list[dict]:
    """Retrieve only from an already isolated bundle; reject contaminated databases."""
    documents = workspace.documents()
    _require({document["id"] for document in documents} == source_map.keys(), "workspace contains sources outside bundle")
    for document in documents:
        original = source_map[document["id"]]
        _require(document["kind"] == "public" and document["external_model_allowed"] is False,
                 "workspace public/external-model boundary violated")
        _require(document["sha256"] == original["excerpt_sha256"], "workspace source hash differs from manifest")
        stored = workspace.document(document["id"], include_raw=True)
        _require(hashlib.sha256(stored["raw"]).hexdigest() == original["excerpt_sha256"],
                 "workspace raw bytes differ from manifest")
        _require(stored["chunks"] == [{"locator": passage["locator"], "text": passage["quote"]}
                                     for passage in original["passages"]], "workspace chunks differ from manifest")
    citations = []
    for hit in workspace.search(query, limit=30):
        original = source_map[hit["id"]]
        passages = {passage["locator"]: passage for passage in original["passages"]}
        passage = passages.get(hit["locator"])
        _require(passage is not None and hit["text"] == passage["quote"], "retrieved quote differs from manifest")
        citations.append({"source_id": original["id"], "locator": passage["locator"],
                          "source_locator": passage["source_locator"], "quote": passage["quote"],
                          "sha256": original["excerpt_sha256"], "url": original["url"], "score": hit["score"]})
    return sorted(citations, key=lambda item: (-item["score"], item["source_id"], item["locator"]))


def verify_public_corpus(corpus: Path) -> dict:
    """Run local fixtures. A passing report is only a lexical locator baseline."""
    loaded = load_public_corpus(corpus)
    manifest = loaded.manifest
    documents = {document["id"]: document for document in manifest["documents"]}
    results = []
    with TemporaryDirectory(prefix="ontolens-public-corpus-") as temporary:
        for index, bundle in enumerate(manifest["bundles"]):
            workspace = _PublicOnlyWorkspace(loaded.root, Path(temporary) / f"bundle-{index}.sqlite3")
            source_map = {}
            for source_id in bundle["source_ids"]:
                document = documents[source_id]
                imported = workspace.import_document(
                    document["title"], "text/plain", loaded.raw_excerpts[source_id],
                    [{"locator": passage["locator"], "text": passage["quote"]} for passage in document["passages"]],
                    kind="public", external_model_allowed=False)
                source_map[imported["id"]] = document
            for question in manifest["questions"]:
                if question["bundle_id"] != bundle["id"]:
                    continue
                citations = public_document_lookup(workspace, question["query"], source_map)
                retrieved = {(item["source_id"], item["locator"]) for item in citations}
                missing = [edge for edge in question["required_evidence"]
                           if (edge["source_id"], edge["locator"]) not in retrieved]
                results.append({"question_id": question["id"], "bundle_id": bundle["id"],
                                "label_status": LABEL_STATUS, "status": "needs_review", "decision": None,
                                "citations": citations, "missing_required_evidence": missing,
                                "required_locators_found": not missing,
                                "missing_conditions": ["site_specific_authorization_and_inventory",
                                                       "current_local_rules_and_applicability",
                                                       "independent_professional_review"]
                                + (["required_public_evidence_not_retrieved"] if missing else [])})
    found = sum(result["required_locators_found"] for result in results)
    required_total = sum(len(question["required_evidence"]) for question in manifest["questions"])
    located_total = required_total - sum(len(result["missing_required_evidence"]) for result in results)
    return {"schema_version": "ontolens-public-corpus-verification-1", "scope": SCOPE,
            "passed": found == len(results), "integrity_passed": True,
            "external_request_sent": False, "production_database_used": False,
            "business_checker_called": False, "synthetic_ledger_imported": False,
            "label_status": LABEL_STATUS, "source_authenticity_verified": False,
            "independent_review_completed": False, "semantic_correctness_measured": False,
            "legal_compliance_established": False,
            "metric_scope": "developer_fixture_lexical_retrieval_evidence_coverage_only",
            "limitations": ["Hashes bind local excerpts, not live source authenticity or completeness.",
                            "Public URL metadata is checked offline; source content and identity require review.",
                            "Developer-authored queries and evidence labels are not an independent gold standard.",
                            "Shared reference documents and source families are not independent or blind samples.",
                            "Synthetic ledger bytes are verified but are not imported or used for business decisions.",
                            "Workspace search returns at most 30 lexical matches; no model semantics are evaluated."],
            "data_hashes": loaded.data_hashes,
            "counts": {"documents": len(documents), "bundles": len(manifest["bundles"]),
                       "passages": sum(len(document["passages"]) for document in documents.values()),
                       "synthetic_ledgers": len(manifest.get("synthetic_ledger", [])),
                       "source_families": len({document["source_family"] for document in documents.values()}),
                       "questions": len(results), "questions_all_required_locators_found": found,
                       "required_locators": required_total, "retrieved_required_locators": located_total},
            "developer_fixture_locator_recall": located_total / required_total,
            "questions": results}

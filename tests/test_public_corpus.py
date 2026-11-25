import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from ontolens.public_corpus import (
    LABEL_STATUS, PublicCorpusError, _PublicOnlyWorkspace, load_public_corpus,
    public_document_lookup, verify_public_corpus,
)
from ontolens.workspace import Workspace


def save(root, manifest):
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def corpus(tmp_path):
    documents = []
    for source_id, line in (("a", "storage needs safety review"), ("b", "storage requires authorization"),
                            ("other", "storage storage storage unrelated package")):
        raw = (line + "\n").encode()
        (tmp_path / f"{source_id}.txt").write_bytes(raw)
        documents.append({"id": source_id, "title": source_id, "publisher": "Fixture publisher",
                          "url": f"https://www.example.org/{source_id}", "published_at": "2026-01-01",
                          "source_family": "fixture", "excerpt_path": f"{source_id}.txt",
                          "excerpt_sha256": hashlib.sha256(raw).hexdigest(),
                          "passages": [{"locator": "L1", "source_locator": "Article 1", "quote": line}]})
    ledger_raw = b'{"notice":"synthetic fixture only"}\n'
    (tmp_path / "ledger.json").write_bytes(ledger_raw)
    manifest = {"schema_version": "ontolens-public-corpus-1", "scope": "public_documents_with_synthetic_ledger",
                "documents": documents,
                "synthetic_ledger": [{"id": "ledger", "path": "ledger.json", "kind": "synthetic",
                                      "sha256": hashlib.sha256(ledger_raw).hexdigest(), "notice": "Synthetic fixture"}],
                "bundles": [{"id": "bundle", "source_ids": ["a", "b"], "ledger_id": "ledger"},
                            {"id": "unrelated", "source_ids": ["other"]}],
                "questions": [{"id": "q1", "bundle_id": "bundle", "question": "What needs review?",
                               "query": "storage", "required_evidence": [{"source_id": "a", "locator": "L1"},
                                                                          {"source_id": "b", "locator": "L1"}],
                               "expected": {"status": "needs_review", "decision": None}, "label_status": LABEL_STATUS}]}
    save(tmp_path, manifest)
    return tmp_path, manifest


def test_public_fixture_isolation_stable_citations_and_explicit_weak_label_boundary(corpus, monkeypatch):
    root, manifest = corpus
    imports = []
    original = Workspace.import_document

    def record_import(self, *args, **kwargs):
        imports.append(kwargs)
        return original(self, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("business checker must not run")

    monkeypatch.setattr(Workspace, "import_document", record_import)
    monkeypatch.setattr(Workspace, "check", forbidden)
    report = verify_public_corpus(root)
    assert report == verify_public_corpus(root)
    assert report["passed"] and report["integrity_passed"]
    assert report["counts"]["synthetic_ledgers"] == 1
    assert all(item == {"kind": "public", "external_model_allowed": False} for item in imports)
    result = report["questions"][0]
    assert {item["source_id"] for item in result["citations"]} == {"a", "b"}
    assert all(item["source_locator"] == "Article 1" and len(item["sha256"]) == 64 for item in result["citations"])
    assert result["status"] == "needs_review" and result["decision"] is None
    assert result["missing_conditions"] and result["label_status"] == LABEL_STATUS
    assert report["developer_fixture_locator_recall"] == 1.0
    assert report["semantic_correctness_measured"] is False
    assert report["legal_compliance_established"] is False
    assert report["independent_review_completed"] is False
    assert report["synthetic_ledger_imported"] is False
    assert "answer_accuracy" not in json.dumps(report)
    assert not list(root.glob("*.sqlite3"))


def test_missing_retrieval_fails_fixture_but_still_requires_review(corpus):
    root, manifest = corpus
    manifest["questions"][0]["query"] = "no matching keyword"
    save(root, manifest)
    report = verify_public_corpus(root)
    assert report["integrity_passed"] and not report["passed"]
    assert report["developer_fixture_locator_recall"] == 0
    result = report["questions"][0]
    assert result["status"] == "needs_review" and result["decision"] is None
    assert len(result["missing_required_evidence"]) == 2
    assert "required_public_evidence_not_retrieved" in result["missing_conditions"]


@pytest.fixture
def alignment_corpus(corpus):
    root, manifest = corpus
    mapping = {
        "id": "training-prerequisite", "status": "proposed", "ontology_version": "ontolens-ontology-1",
        "relation": "authorized_for", "mapping_kind": "prerequisite_only",
        "source_id": "a", "locator": "L1",
        "review_checks": ["Verify training evidence", "Verify local authorization separately"],
    }
    manifest["alignment_candidates"] = [mapping]
    save(root, manifest)
    return root, manifest, mapping


def test_alignment_candidate_resolves_claim_to_version_and_evidence(alignment_corpus):
    root, manifest, mapping = alignment_corpus
    report = verify_public_corpus(root)
    assert report["passed"]
    candidate, = report["alignment_candidates"]
    assert candidate == {**mapping, "source_locator": "Article 1", "url": "https://www.example.org/a",
                         "sha256": manifest["documents"][0]["excerpt_sha256"],
                         "quote": "storage needs safety review", "decision": None}
    assert report["business_checker_called"] is False
    assert report["independent_review_completed"] is False


@pytest.mark.parametrize("field,value", [
    ("relation", "unregistered"),
    ("locator", "L99"),
    ("ontology_version", "outdated"),
    ("mapping_kind", "equivalent"),
    ("status", "published"),
    ("decision", {"action": "ALLOW"}),
    ("review_checks", []),
])
def test_alignment_candidate_rejects_broken_or_publishable_records(alignment_corpus, field, value):
    root, manifest, mapping = alignment_corpus
    mapping[field] = value
    save(root, manifest)
    with pytest.raises(PublicCorpusError, match="alignment"):
        load_public_corpus(root)


@pytest.mark.parametrize("mutation,match", [
    (lambda m: m["documents"].append(m["documents"][0].copy()), "duplicate id"),
    (lambda m: m["documents"][0].update(excerpt_path="../outside.txt"), "relative contained"),
    (lambda m: m["documents"][0].update(excerpt_path="C:\\private.txt"), "relative contained"),
    (lambda m: m["documents"][0]["passages"][0].update(quote="rewritten"), "quote mismatch"),
    (lambda m: m["documents"][0]["passages"][0].update(locator="L2"), "consecutive"),
    (lambda m: m["documents"][0].update(kind="private"), "kind must be public"),
    (lambda m: m["documents"][0].update(external_model_allowed=True), "external model"),
    (lambda m: m["bundles"][0]["source_ids"].append("unknown"), "unknown document"),
    (lambda m: m["questions"][0]["required_evidence"][1].update(source_id="other"), "outside bundle"),
    (lambda m: m["questions"][0]["required_evidence"][1].update(locator="L99"), "unknown locator"),
    (lambda m: m["questions"][0].update(label_status="gold_standard"), "developer_authored_unreviewed"),
    (lambda m: m["questions"][0].update(expected={"status": "decided", "decision": {"action": "ALLOW"}}), "no decision gold"),
    (lambda m: m["questions"][0].update(query="  "), "nonempty string"),
    (lambda m: m["synthetic_ledger"][0].update(kind="private"), "ledger kind"),
    (lambda m: m["synthetic_ledger"][0].update(path="../private.csv"), "relative contained"),
    (lambda m: m["bundles"][0].update(ledger_id="unknown"), "unknown synthetic ledger"),
])
def test_manifest_negative_controls(corpus, mutation, match):
    root, manifest = corpus
    mutation(manifest)
    save(root, manifest)
    with pytest.raises(PublicCorpusError, match=match):
        load_public_corpus(root)


@pytest.mark.parametrize("url", ["file:///private/file", "http://127.0.0.1/doc", "http://localhost/doc",
                                 "http://192.168.1.2/doc", "https://user:pass@example.org/doc",
                                 "https://example.org/doc?token=secret"])
def test_nonpublic_or_credentialed_urls_rejected(corpus, url):
    root, manifest = corpus
    manifest["documents"][0]["url"] = url
    save(root, manifest)
    with pytest.raises(PublicCorpusError, match="url:"):
        load_public_corpus(root)


@pytest.mark.parametrize("filename", ["a.txt", "ledger.json"])
def test_tampered_bytes_rejected_before_import(corpus, filename, monkeypatch):
    root, _ = corpus
    (root / filename).write_bytes(b"tampered bytes\n")
    monkeypatch.setattr(Workspace, "import_document", lambda *args, **kwargs: pytest.fail("import before validation"))
    with pytest.raises(PublicCorpusError, match="hash mismatch"):
        verify_public_corpus(root)


@pytest.mark.parametrize("payload", ['{"schema_version":1,"schema_version":2}', '{"value":NaN}'])
def test_ambiguous_json_rejected(corpus, payload):
    root, _ = corpus
    (root / "manifest.json").write_text(payload, encoding="utf-8")
    with pytest.raises(PublicCorpusError):
        load_public_corpus(root)


def test_same_document_references_are_not_cross_document(corpus):
    root, manifest = corpus
    doc = manifest["documents"][0]
    raw = (doc["passages"][0]["quote"] + "\nsecond storage rule\n").encode()
    (root / "a.txt").write_bytes(raw)
    doc["excerpt_sha256"] = hashlib.sha256(raw).hexdigest()
    doc["passages"].append({"locator": "L2", "source_locator": "Article 2", "quote": "second storage rule"})
    manifest["questions"][0]["required_evidence"][1] = {"source_id": "a", "locator": "L2"}
    save(root, manifest)
    with pytest.raises(PublicCorpusError, match="different documents"):
        load_public_corpus(root)


def test_lookup_rejects_unmapped_source_in_workspace(corpus, tmp_path):
    root, manifest = corpus
    workspace = _PublicOnlyWorkspace(root, tmp_path / "isolation.sqlite3")
    document = manifest["documents"][0]
    imported = workspace.import_document("a", "text/plain", (root / "a.txt").read_bytes(),
                                         [{"locator": "L1", "text": document["passages"][0]["quote"]}], "public")
    workspace.import_document("private", "text/plain", b"storage", [{"locator": "L1", "text": "storage"}], "private")
    with pytest.raises(PublicCorpusError, match="outside bundle"):
        public_document_lookup(workspace, "storage", {imported["id"]: document})


def test_cli_writes_only_dedicated_report_in_test_root(corpus, tmp_path, monkeypatch):
    root, _ = corpus
    project = Path(__file__).resolve().parents[1]
    script_path = project / "scripts/verify_public_corpus.py"
    spec = importlib.util.spec_from_file_location("verify_public_corpus_cli", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    test_project = tmp_path / "cli-project"
    for relative in ("src/ontolens/public_corpus.py", "src/ontolens/ontology.py",
                     "src/ontolens/workspace.py", "scripts/verify_public_corpus.py"):
        destination = test_project / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((project / relative).read_bytes())
    monkeypatch.setattr(module, "ROOT", test_project)
    assert module.main(["--corpus", str(root)]) == 0
    report_path = test_project / "artifacts/public-corpus-verification.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passed"] and "src/ontolens/ontology.py" in report["code_input_hashes"]
    assert report["data_hashes"]["manifest.json"] == hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
    assert list((test_project / "artifacts").iterdir()) == [report_path]
    (root / "a.txt").write_bytes(b"tampered\n")
    assert module.main(["--corpus", str(root)]) == 1
    failed = json.loads(report_path.read_text(encoding="utf-8"))
    assert failed["passed"] is False and "hash mismatch" in failed["error"]


def test_tied_retrieval_cutoff_is_reproducible(corpus):
    root, manifest = corpus
    for doc in manifest["documents"][:2]:
        lines = [f"storage clause {number}" for number in range(20)]
        raw = ("\n".join(lines) + "\n").encode()
        (root / doc["excerpt_path"]).write_bytes(raw)
        doc["excerpt_sha256"] = hashlib.sha256(raw).hexdigest()
        doc["passages"] = [{"locator": f"L{number}", "source_locator": f"Article {number}", "quote": line}
                           for number, line in enumerate(lines, 1)]
    save(root, manifest)
    first = verify_public_corpus(root)
    second = verify_public_corpus(root)
    assert first == second
    assert len(first["questions"][0]["citations"]) == 30

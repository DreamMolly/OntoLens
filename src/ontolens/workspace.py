from __future__ import annotations

import base64
import copy
import csv
import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from ontolens.catalog import HAZARD_CLASSES, load_catalog
from ontolens.audit_context import audit_actor
from ontolens.checker import decide
from ontolens.evaluate import evaluate, load_cases
from ontolens.gate import review_promotion
from ontolens.jev import JevReranker
from ontolens.ledger_import import GROUPS, candidate_invariants, canonical, original_chunks, parse_bundle, snapshot_report
from ontolens.ontology import schema as ontology_schema
from ontolens.rules import load_rules


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier(prefix: str) -> str:
    return prefix + uuid4().hex[:20]


class WorkspaceError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


CLASS_ALIASES = {
    "FLAMMABLE": ("FLAMMABLE", "易燃"),
    "OXIDIZER": ("OXIDIZER", "氧化剂"),
    "ACID": ("ACID", "酸"),
    "BASE": ("BASE", "碱"),
    "WATER_REACTIVE": ("WATER_REACTIVE", "遇水"),
    "TOXIC": ("TOXIC", "有毒"),
    "COMPRESSED_GAS": ("COMPRESSED_GAS", "压缩气体"),
    "GENERAL": ("GENERAL", "一般"),
}


def _terms_pattern(*terms: str) -> str:
    """Bound English tokens without requiring spaces around Chinese aliases."""
    patterns = []
    for term in terms:
        escaped = re.escape(term)
        patterns.append(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])" if term.isascii() else escaped)
    return "(?:" + "|".join(patterns) + ")"


class Workspace:
    def __init__(self, root: Path, database: Path, seed_demo: bool = True):
        self.root = root.resolve()
        self.database = database.resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect(write=True) as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, media_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL, kind TEXT NOT NULL, external_model_allowed INTEGER NOT NULL DEFAULT 0, chunks TEXT NOT NULL,
                    raw BLOB NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS versions (
                    id TEXT PRIMARY KEY, parent_id TEXT, snapshot TEXT NOT NULL,
                    sha256 TEXT NOT NULL, label TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY, parent_id TEXT NOT NULL, snapshot TEXT NOT NULL,
                    patch TEXT NOT NULL, status TEXT NOT NULL, version_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, request TEXT NOT NULL, result TEXT NOT NULL,
                    version_id TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL,
                    payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
            """)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(documents)")}
            if "external_model_allowed" not in columns:
                connection.execute("ALTER TABLE documents ADD COLUMN external_model_allowed INTEGER NOT NULL DEFAULT 0")
            imports = connection.execute("SELECT payload FROM audit WHERE event='source_imported'").fetchall()
            for row in imports:
                payload = json.loads(row["payload"])
                if payload.get("external_model_allowed") is not True:
                    changed = connection.execute(
                        "UPDATE documents SET external_model_allowed=0 WHERE id=? AND kind='synthetic' AND external_model_allowed=1",
                        (payload.get("source_id"),),
                    )
                    if changed.rowcount:
                        self._event(connection, "source_permission_restored", {
                            "source_id": payload["source_id"], "external_model_allowed": False,
                            "basis": "source_imported audit",
                        })
        self._seed() if seed_demo else self._seed_operational()

    def _seed_operational(self):
        with self.connect(write=True) as connection:
            if connection.execute("SELECT value FROM settings WHERE key='active'").fetchone():
                return
            snapshot = {"catalog": {group: {} for group in GROUPS[:4]}, "issues": {},
                        "provenance": {}, "person_evidence": {}, "validity": {}, "rules": "",
                        "mode": "imported_workspace", "schema_version": "ontolens-snapshot-1"}
            encoded = encode(snapshot)
            connection.execute("INSERT INTO versions VALUES(?,?,?,?,?,?)", (
                "operational-initial", None, encoded, digest(encoded.encode()), "空业务工作区", timestamp()))
            connection.execute("INSERT INTO settings VALUES('active','operational-initial')")
            self._event(connection, "operational_initialized", {"catalog_empty": True, "human_reviewer": None})

    def import_ledger_bundle(self, manifest: dict, files: dict[str, bytes]):
        try:
            parsed = parse_bundle(manifest, files)
        except (ValueError, TypeError, KeyError, RecursionError, csv.Error, UnicodeError, yaml.YAMLError) as error:
            raise WorkspaceError("业务资料包无效：" + str(error)) from error
        parent = self.version()
        facts = parsed["data"]
        provenance, bindings = {}, {}
        candidate_id = identifier("cand_")
        with self.connect(write=True) as connection:
            for group in GROUPS:
                source = manifest["sources"][group]
                raw = files[source["file"]]
                # Original bytes are never replaced by reconstructed business records.
                original_id = self._insert_document(
                    connection, source["file"], source["media_type"], raw,
                    original_chunks(group, raw, source["media_type"]), source["kind"], False)
                if group == "rules":
                    # Rule graph L1 must refer to the version value, regardless of original ordering.
                    ordered = {"version": facts[group]["version"], **facts[group]}
                    normalized = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False)
                    chunks = [{"locator": "L" + str(i), "text": line}
                              for i, line in enumerate(normalized.splitlines(), 1)]
                    media = "application/yaml"
                else:
                    normalized = canonical(facts[group])
                    chunks = [{"locator": "$." + entity, "text": canonical(row)}
                              for entity, row in sorted(facts[group].items())]
                    media = "application/json"
                normalized_id = self._insert_document(
                    connection, "normalized-" + group + (".yaml" if group == "rules" else ".json"),
                    media, normalized.encode("utf-8"), chunks, source["kind"], False)
                provenance[group] = normalized_id
                provenance["original_" + group] = original_id
                bindings[group] = {"original_source_id": original_id, "normalized_source_id": normalized_id,
                                   "file": source["file"], "sha256": source["sha256"],
                                   "mapping": "parsed entity IDs preserve JSON/YAML keys or CSV id column",
                                   "entity_locators": {entity: {"original": "$." + entity, "normalized": "$." + entity}
                                                       for entity in facts[group]} if group != "rules" else {},
                                   "rules_mapping": "whole original rule document parsed into normalized YAML" if group == "rules" else None}
            snapshot = {"catalog": {group: facts[group] for group in GROUPS[:4]},
                        "issues": facts["issues"], "rules": normalized,
                        "provenance": provenance, "person_evidence": {}, "validity": parsed["validity"],
                        "mode": "imported_workspace", "schema_version": "ontolens-snapshot-1",
                        "import_manifest": manifest, "import_bindings": bindings}
            patch = {"type": "ledger_bundle", "label": manifest["label"],
                     "operator": manifest["authorization"]["operator"],
                     "counts": {group: len(facts[group]) for group in GROUPS[:5]},
                     "source_count": 6, "external_model_allowed": False}
            connection.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?,?)", (
                candidate_id, parent["id"], encode(snapshot), encode(patch), "proposed", None, timestamp()))
            self._event(connection, "ledger_bundle_candidate_created", {"candidate_id": candidate_id, **patch})
        return self.candidate(candidate_id)

    @contextmanager
    def connect(self, write: bool = False):
        connection = sqlite3.connect(self.database, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _event(self, connection, event: str, payload: dict) -> dict:
        actor = audit_actor.get()
        if actor is not None:
            payload = {**payload, "actor": dict(actor)}
        created_at = timestamp()
        cursor = connection.execute("INSERT INTO audit(event,payload,created_at) VALUES(?,?,?)",
                                    (event, encode(payload), created_at))
        return {"audit_sequence": cursor.lastrowid, "created_at": created_at}

    def _insert_document(self, connection, title, media_type, raw, chunks, kind, external_model_allowed=False):
        source_id = identifier("doc_")
        connection.execute("""INSERT INTO documents
            (id,title,media_type,sha256,kind,external_model_allowed,chunks,raw,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""", (
            source_id, title, media_type, digest(raw), kind, int(bool(external_model_allowed)), encode(chunks), raw, timestamp(),
        ))
        return source_id

    def _seed(self):
        with self.connect(write=True) as connection:
            if connection.execute("SELECT value FROM settings WHERE key='active'").fetchone():
                return
            catalog = load_catalog(self.root / "data/catalog.yaml")
            provenance = {}
            for group, title in (("people", "合成人员授权"), ("chemicals", "合成物料属性"),
                                 ("lots", "合成批次台账"), ("cabinets", "合成柜位限制")):
                chunks = [{"locator": "$." + entity, "text": encode(fields)}
                          for entity, fields in catalog[group].items()]
                raw = encode(catalog[group]).encode("utf-8")
                provenance[group] = self._insert_document(
                    connection, title + ".json", "application/json", raw, chunks, "synthetic", True)
            issues = {person: [] for person in catalog["people"]}
            issues["stu03"] = ["OXIDIZER"]
            provenance["issues"] = self._insert_document(
                connection, "合成未归还记录.json", "application/json", encode(issues).encode(),
                [{"locator": "$." + person, "text": encode(classes)}
                 for person, classes in issues.items()], "synthetic", True)
            rule_text = (self.root / "data/rules/v2.yaml").read_text(encoding="utf-8")
            provenance["rules"] = self._insert_document(
                connection, "教学规则-v2.yaml", "text/plain", rule_text.encode(),
                [{"locator": "L" + str(index), "text": line}
                 for index, line in enumerate(rule_text.splitlines(), 1)], "synthetic", True)
            snapshot = {"catalog": catalog, "issues": issues, "provenance": provenance,
                        "person_evidence": {}, "validity": {}, "rules": rule_text,
                        "mode": "synthetic_demo", "schema_version": "ontolens-snapshot-1"}
            encoded = encode(snapshot)
            connection.execute("INSERT INTO versions VALUES(?,?,?,?,?,?)", (
                "demo-initial", None, encoded, digest(encoded.encode()), "初始合成快照", timestamp()))
            connection.execute("INSERT INTO settings VALUES('active','demo-initial')")
            self._event(connection, "demo_initialized", {"human_reviewer": None})

    def document(self, source_id: str, include_raw: bool = False) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM documents WHERE id=?", (source_id,)).fetchone()
        if row is None:
            raise WorkspaceError("来源不存在", 404)
        result = dict(row)
        result["external_model_allowed"] = bool(result["external_model_allowed"])
        result["chunks"] = json.loads(result["chunks"])
        if not include_raw:
            result.pop("raw")
        return result

    def documents(self):
        with self.connect() as connection:
            rows = connection.execute("SELECT id,title,media_type,sha256,kind,external_model_allowed,created_at FROM documents ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "external_model_allowed": bool(row["external_model_allowed"])} for row in rows]

    def import_document(self, title, media_type, raw, chunks, kind, external_model_allowed=False):
        if kind not in ("synthetic", "public", "private"):
            raise WorkspaceError("来源性质无效")
        if kind == "private" and external_model_allowed:
            raise WorkspaceError("私有资料不能标记为允许发送给外部模型", 409)
        with self.connect(write=True) as connection:
            source_id = self._insert_document(connection, title, media_type, raw, chunks, kind, external_model_allowed)
            self._event(connection, "source_imported", {"source_id": source_id, "kind": kind,
                        "external_model_allowed": bool(external_model_allowed)})
        return self.document(source_id)

    def active_id(self):
        with self.connect() as connection:
            return connection.execute("SELECT value FROM settings WHERE key='active'").fetchone()[0]

    def version(self, version_id: str | None = None):
        version_id = version_id or self.active_id()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM versions WHERE id=?", (version_id,)).fetchone()
        if row is None:
            raise WorkspaceError("版本不存在", 404)
        result = dict(row)
        result["snapshot"] = json.loads(result["snapshot"])
        return result

    def versions(self):
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT id,parent_id,sha256,label,created_at FROM versions ORDER BY created_at DESC")]

    def search(self, query: str, limit: int = 12, version_id: str | None = None):
        allowed = None
        if version_id:
            snapshot = self.version(version_id)["snapshot"]
            allowed = set(snapshot["provenance"].values()) | {
                evidence["source_id"] for evidence in snapshot["person_evidence"].values()}
        words = query.casefold().split()
        results = []
        for document in self.documents():
            if allowed is not None and document["id"] not in allowed:
                continue
            for chunk in self.document(document["id"])["chunks"]:
                haystack = (document["title"] + " " + chunk["locator"] + " " + chunk["text"]).casefold()
                score = sum(word in haystack for word in words)
                if not words or score:
                    results.append({**document, **chunk, "score": score})
        return sorted(results, key=lambda result: (-result["score"], result["id"], result["locator"]))[:limit]

    def rerank_evidence(self, query: str, version_id: str | None = None, limit: int = 12, *,
                        allow_live: bool = False, citations: list[dict] | None = None,
                        synthetic_claim: bool = False):
        if not query.strip() or len(query) > 300 or type(limit) is not int or not 1 <= limit <= 30:
            raise WorkspaceError("查询需要 1–300 个非空字符，候选数必须是 1–30 的整数", 422)
        version = self.version(version_id)
        if citations is None:
            candidates = self.search(query, limit=limit, version_id=version["id"])
            result = JevReranker().rerank(query, candidates, limit=limit, allow_live=allow_live)
        else:
            if not 1 <= len(citations) <= limit:
                raise WorkspaceError("引用数量必须为 1–limit，不能截断后遗漏引用", 422)
            allowed = set(version["snapshot"]["provenance"].values()) | {
                item["source_id"] for item in version["snapshot"]["person_evidence"].values()}
            candidates, checks, seen = [], [], set()
            for citation in citations:
                source_id, locator = citation["source_id"], citation["locator"]
                code = "matched"
                document = None
                if (source_id, locator) in seen:
                    code = "duplicate_reference"
                elif source_id not in allowed:
                    code = "source_not_in_snapshot"
                else:
                    try:
                        document = self.document(source_id, include_raw=True)
                    except WorkspaceError:
                        code = "source_missing"
                    if document is not None:
                        chunk = next((item for item in document["chunks"] if item["locator"] == locator), None)
                        if citation["sha256"] != document["sha256"] or digest(document["raw"]) != document["sha256"]:
                            code = "hash_mismatch"
                        elif chunk is None:
                            code = "locator_missing"
                        elif not citation["quote"].strip() or chunk["text"] != citation["quote"]:
                            code = "quote_mismatch"
                seen.add((source_id, locator))
                checks.append({"source_id": source_id, "locator": locator, "code": code, "valid": code == "matched"})
                if code == "matched":
                    candidates.append({key: document[key] for key in
                                       ("id", "title", "kind", "sha256", "external_model_allowed")})
                    candidates[-1].update({"source_id": source_id, "locator": locator, "text": citation["quote"]})
            valid = all(item["valid"] for item in checks)
            judge = JevReranker()
            result = judge.rerank(query, candidates if valid else [], limit=limit,
                                  allow_live=allow_live if valid else False, purpose="citation_review",
                                  synthetic_claim=synthetic_claim)
            if not valid:
                result.update({"status": "unavailable", "code": "citation_integrity_failed",
                               "reason": "引用字面核对失败，未请求 JEV；需要人工复核"})
            result["citation_check"] = {"status": "passed" if valid else "failed", "references": checks,
                                         "notice": "只验证来源字面一致；不证明陈述语义正确"}
            result["citation_input_hash"] = digest(encode({"query": query, "citations": citations,
                                                          "snapshot_hash": version["sha256"]}).encode())
        result.update({"version_id": version["id"], "snapshot_hash": version["sha256"]})
        with self.connect(write=True) as connection:
            audit = {
                key: result[key] for key in ("status", "code", "model", "resolved_model", "question_version",
                    "version_id", "snapshot_hash", "input_hash", "request_count", "usage", "elapsed_ms", "fallback")
            }
            if citations is not None:
                audit.update({"citation_check": result["citation_check"], "citation_input_hash": result["citation_input_hash"],
                              "scores": [{key: item.get(key) for key in ("source_id", "locator", "sha256",
                                         "jev_probability", "jev_contradiction_probability", "jev_review_hint")}
                                         for item in result["candidates"]]})
            self._event(connection, "jev_citations_reviewed" if citations is not None else "jev_evidence_reranked", audit)
        return result

    def suggest_candidates(self, source_id: str):
        document = self.document(source_id)
        catalog = self.version()["snapshot"]["catalog"]
        suggestions = []
        for chunk in document["chunks"]:
            text = chunk["text"]
            people = [person_id for person_id in catalog["people"] if re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(person_id)}(?![A-Za-z0-9_])", text)]
            classes = [class_name for class_name, aliases in CLASS_ALIASES.items()
                       if re.search(_terms_pattern(*aliases), text, re.IGNORECASE)]
            if not people or not classes or not re.search(
                _terms_pattern("授权", "类别", "class", "classes", "authorize", "authorized", "authorizes"),
                text, re.IGNORECASE,
            ):
                continue
            for person_id in people:
                current = catalog["people"][person_id]["classes"]
                replacement = bool(re.search(_terms_pattern("仅保留", "只保留", "only"), text, re.IGNORECASE))
                proposed = sorted(set(classes))
                from_match = re.search(_terms_pattern("生效", "from") + r"\s*[:：]?\s*(20\d\d-\d\d-\d\d)",
                                       text, re.IGNORECASE)
                until_match = re.search(_terms_pattern("有效至", "截至", "until") + r"\s*[:：]?\s*(20\d\d-\d\d-\d\d)",
                                        text, re.IGNORECASE)
                suggestions.append({
                    "source_id": source_id,
                    "source_title": document["title"],
                    "locator": chunk["locator"],
                    "quote": text,
                    "requester_id": person_id,
                    "current_classes": current,
                    "proposed_classes": proposed,
                    "change_mode": "replace" if replacement else "add",
                    "valid_from": from_match.group(1) if from_match else None,
                    "valid_until": until_match.group(1) if until_match else None,
                    "status": "proposed",
                    "review_required": True,
                    "method": "deterministic_alias_match",
                    "notice": "结构化候选，仅供人工确认；没有自动发布或改判",
                })
        return suggestions

    def recognize_assets(self, source_id: str) -> dict:
        document = self.document(source_id)
        catalog = self.version()["snapshot"]["catalog"]
        entity_catalog = {
            "Person": set(catalog["people"]),
            "Chemical": set(catalog["chemicals"]),
            "Lot": set(catalog["lots"]),
            "StorageZone": set(catalog["cabinets"]),
            "HazardClass": set(HAZARD_CLASSES),
        }
        aliases = {entity_id: entity_id for values in entity_catalog.values() for entity_id in values}
        aliases.update({alias: class_name for class_name, values in CLASS_ALIASES.items() for alias in values})
        entities = []
        seen = set()
        for chunk in document["chunks"]:
            text = chunk["text"]
            for type_id, candidates in entity_catalog.items():
                for entity_id in candidates:
                    if not re.search(rf"(?<![A-Za-z0-9_]){re.escape(entity_id)}(?![A-Za-z0-9_])", text):
                        continue
                    key = (chunk["locator"], type_id, entity_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    entities.append({
                        "id": entity_id, "type": type_id, "source_id": source_id,
                        "locator": chunk["locator"], "quote": text,
                        "method": "deterministic_catalog_match", "status": "observed",
                    })
            for alias, class_name in aliases.items():
                if class_name not in HAZARD_CLASSES or not re.search(_terms_pattern(alias), text, re.IGNORECASE):
                    continue
                key = (chunk["locator"], "HazardClass", class_name)
                if key not in seen:
                    seen.add(key)
                    entities.append({
                        "id": class_name, "type": "HazardClass", "source_id": source_id,
                        "locator": chunk["locator"], "quote": text,
                        "method": "deterministic_alias_match", "status": "observed",
                    })
        relations = []
        schema_candidates = []
        for suggestion in self.suggest_candidates(source_id):
            for class_name in suggestion["proposed_classes"]:
                relations.append({
                    "type": "authorized_for", "subject": suggestion["requester_id"],
                    "object": class_name, "source_id": source_id, "locator": suggestion["locator"],
                    "quote": suggestion["quote"], "status": "proposed",
                    "review_required": True, "method": suggestion["method"],
                })
            properties = []
            if suggestion["valid_from"]:
                properties.append("valid_from")
            if suggestion["valid_until"]:
                properties.append("valid_until")
            if properties:
                schema_candidates.append({
                    "kind": "relation_property",
                    "relation": "authorized_for",
                    "subject_type": "Person",
                    "object_type": "HazardClass",
                    "properties": properties,
                    "source_id": source_id,
                    "locator": suggestion["locator"],
                    "quote": suggestion["quote"],
                    "status": "proposed",
                    "review_required": True,
                    "method": "authorization_validity_pattern",
                    "notice": "候选扩展已有关系的有效期字段；尚未自动对齐任何行业标准或发布 schema",
                })
        return {
            "source_id": source_id, "source_title": document["title"],
            "media_type": document["media_type"], "entities": entities, "relations": relations,
            "schema_candidates": schema_candidates,
            "schema": ontology_schema(), "mode": self.version()["snapshot"].get("mode", "synthetic_demo"),
            "notice": "资产识别使用当前目录和别名匹配；关系候选必须审核，当前未对齐真实行业规范",
        }

    def ontology(self) -> dict:
        return ontology_schema()

    def graph(self, requester_id, lot_id, cabinet_id, version_id=None):
        version = self.version(version_id)
        snapshot = version["snapshot"]
        catalog = snapshot["catalog"]
        if not snapshot["provenance"]:
            return {"version_id": version["id"], "edges": [], "mode": snapshot["mode"],
                    "description": "业务资料尚未导入，无可解析来源"}
        # The rule source is part of the immutable snapshot.  Do not label
        # every graph with the seed version: once a snapshot is restored or a
        # future candidate carries a different rule card, the graph must point
        # at the rule version that actually produced the decision.
        rule_version = "unknown"
        try:
            rule_document = yaml.safe_load(snapshot.get("rules", ""))
            if isinstance(rule_document, dict) and isinstance(rule_document.get("version"), str):
                rule_version = rule_document["version"]
        except (TypeError, yaml.YAMLError):
            # A malformed snapshot will be rejected by the decision path; keep
            # graph inspection deterministic rather than raising while showing
            # unresolved evidence for a needs_review request.
            pass
        lot = catalog["lots"].get(lot_id, {})
        chemical_id = lot.get("chemical_id", "unknown")
        chemical = catalog["chemicals"].get(chemical_id, {})
        hazard = chemical.get("hazard_class", "unknown")
        person_source = snapshot["person_evidence"].get(requester_id, {})
        links = [
            (requester_id, "授权类别", encode(catalog["people"].get(requester_id, {}).get("classes", [])),
             person_source.get("source_id", snapshot["provenance"]["people"]),
             person_source.get("locator", "$." + requester_id)),
            (lot_id, "所属物料", chemical_id, snapshot["provenance"]["lots"], "$." + lot_id),
            (chemical_id, "危害类别", hazard, snapshot["provenance"]["chemicals"], "$." + chemical_id),
            (cabinet_id, "允许类别", encode(catalog["cabinets"].get(cabinet_id, {}).get("allowed_classes", [])),
             snapshot["provenance"]["cabinets"], "$." + cabinet_id),
            (requester_id, "未归还类别（合成）" if snapshot.get("mode") == "synthetic_demo" else "未归还类别", encode(snapshot["issues"].get(requester_id, [])),
             snapshot["provenance"]["issues"], "$." + requester_id),
            ("决定", "规则版本", rule_version, snapshot["provenance"]["rules"], "L1"),
        ]
        edges = []
        for subject, relation, target, source_id, locator in links:
            document = self.document(source_id)
            chunk = next((item for item in document["chunks"] if item["locator"] == locator), None)
            edge = {"subject": subject, "relation": relation, "target": target,
                    "source_id": source_id, "title": document["title"], "locator": locator,
                    "quote": chunk["text"] if chunk else None, "sha256": document["sha256"]}
            if chunk is None:
                # A needs_review run can explain which source was consulted even
                # when the requested entity has no corresponding locator.
                edge["unresolved"] = True
            edges.append(edge)
        return {"version_id": version["id"], "edges": edges, "mode": snapshot.get("mode", "synthetic_demo"),
                "description": "确定性关系路径，非自动本体生成"}

    def _calculate(self, snapshot: dict, request: dict):
        catalog = snapshot["catalog"]
        requester = request["requester_id"]

        def needs_review(code: str, message: str, fields: list[str], evidence: list[str], next_step: str):
            # Keep the stop condition machine-readable so an operator can ask
            # for exactly the missing material.  This object is advisory only:
            # it never contains, or implies, one of the four business actions.
            return {"status": "needs_review", "decision": None, "message": message,
                    "review": {"reason_code": code, "severity": "blocking",
                               "blocking_fields": fields, "requested_evidence": evidence,
                               "next_step": next_step, "decision_blocked": True,
                               "synthetic_boundary": ("仅用于合成演示复核；不得视为真实行业或专业审核结论"
                                                      if snapshot.get("mode") == "synthetic_demo" else
                                                      "导入资料的规则核验；未核实来源真实性或专业审核，不执行实际出库")}}

        for group, field in (("people", "requester_id"), ("lots", "lot_id"), ("cabinets", "destination_cabinet_id")):
            if request[field] not in catalog[group]:
                return needs_review("MISSING_REFERENCE", "资料快照没有该人员、批次或柜位", [field],
                                    [f"{group} 快照中 {request[field]} 的可核验记录"],
                                    "补充带来源定位的人员、批次或柜位记录，再重新核验")
        validity = snapshot["validity"].get(requester, {})
        at = date.fromisoformat(request["as_of"])
        if validity.get("from") and at < date.fromisoformat(validity["from"]):
            return needs_review("AUTHORIZATION_NOT_ACTIVE", "授权证据尚未生效", ["as_of", "authorization.valid_from"],
                                ["带生效日期和来源定位的授权记录"], "确认生效日期或更正核验日期后重新核验")
        if validity.get("until") and at > date.fromisoformat(validity["until"]):
            return needs_review("AUTHORIZATION_EXPIRED", "授权证据已过期，请复核", ["as_of", "authorization.valid_until"],
                                ["带有效期和来源定位的最新授权记录"], "补充有效授权或由人工确认适用的有效期后重新核验")
        lot = catalog["lots"][request["lot_id"]]
        unit = catalog["chemicals"][lot["chemical_id"]]["unit"]
        if request["unit"] != unit:
            return needs_review("UNIT_MISMATCH", "数量单位与物料证据不一致", ["unit", "material.unit"],
                                ["物料属性中单位字段的来源定位", "申请数量单位的原始记录"],
                                "核对单位换算依据；未完成专业复核前不得换算或生成决定")
        rules = yaml.safe_load(snapshot["rules"])
        rules["pair_set"] = {frozenset(pair) for pair in rules["incompatible_pairs"]}
        trusted = {**request, "open_issue_classes": snapshot["issues"][requester]}
        return {"status": "ready", "decision": decide(catalog, rules, trusted).as_dict(),
                "message": ("合成资料的程序决定；不代表专业审核或实际出库"
                            if snapshot.get("mode") == "synthetic_demo" else
                            "导入资料的规则核验结果；不代表专业审核或实际出库"), "unit": unit}

    def check(self, request: dict, version_id: str | None = None):
        version = self.version(version_id)
        result = self._calculate(version["snapshot"], request)
        result.update({"version_id": version["id"], "snapshot_hash": version["sha256"],
                       "mode": version["snapshot"].get("mode", "synthetic_demo"), "human_reviewer": None,
                       "evidence": self.graph(request["requester_id"], request["lot_id"],
                                              request["destination_cabinet_id"], version["id"])["edges"]})
        run_id = identifier("run_")
        result["run_id"] = run_id
        result["review_records"] = []
        with self.connect(write=True) as connection:
            connection.execute("INSERT INTO runs VALUES(?,?,?,?,?)", (
                run_id, encode(request), encode(result), version["id"], timestamp()))
            self._event(connection, "decision_checked", {"run_id": run_id, "status": result["status"]})
        return result

    def run(self, run_id):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise WorkspaceError("判定记录不存在", 404)
        result = json.loads(row["result"])
        result["review_records"] = self.review_records(run_id)
        return {**dict(row), "request": json.loads(row["request"]), "result": result}

    def review_records(self, run_id: str):
        """Return append-only human follow-up records for one run."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT sequence,payload,created_at FROM audit WHERE event='human_review_recorded' "
                "AND json_extract(payload, '$.run_id')=? ORDER BY sequence", (run_id,)
            ).fetchall()
        records = []
        for row in rows:
            payload = json.loads(row["payload"])
            if payload.get("run_id") == run_id:
                records.append({**payload, "created_at": row["created_at"], "audit_sequence": row["sequence"]})
        return records

    def record_review(self, run_id: str, reviewer: str, review_status: str, note: str,
                      evidence_ids: list[Any] | None = None,
                      evidence_references: list[Any] | None = None):
        run = self.run(run_id)
        if run["result"].get("status") != "needs_review":
            raise WorkspaceError("只有 needs_review 记录可以进入人工复核队列", 409)
        reviewer = reviewer.strip()
        note = note.strip()
        if not reviewer or not note or len(reviewer) > 120 or len(note) > 1000:
            raise WorkspaceError("人工复核人和复核记录不能为空")
        allowed = {"queued", "in_review", "evidence_requested", "closed_no_decision"}
        if review_status not in allowed:
            raise WorkspaceError("人工复核状态无效")
        # Keep accepting the old ``evidence_ids: [source_id]`` shape, but turn
        # every value into an immutable source/locator/hash reference before
        # writing the append-only audit event.  This prevents a source id from
        # silently referring to a different passage after export/replay.
        edges = [edge for edge in run["result"].get("evidence", []) if isinstance(edge, dict)]
        by_source: dict[str, list[dict]] = {}
        for edge in edges:
            source_id = edge.get("source_id")
            if isinstance(source_id, str) and source_id:
                by_source.setdefault(source_id, []).append(edge)

        def as_mapping(value: Any) -> dict | None:
            if isinstance(value, dict):
                return value
            model_dump = getattr(value, "model_dump", None)
            if callable(model_dump):
                dumped = model_dump(exclude_unset=True)
                return dumped if isinstance(dumped, dict) else None
            return None

        raw_values = list(evidence_ids or [])
        explicit_values = list(evidence_references or [])
        if len(raw_values) + len(explicit_values) > 40:
            raise WorkspaceError("复核来源引用过多")
        legacy_ids: list[str] = []
        structured: list[dict] = []
        for value in raw_values + explicit_values:
            if isinstance(value, str):
                legacy_ids.append(value)
                continue
            mapped = as_mapping(value)
            if mapped is None:
                raise WorkspaceError("复核记录的来源引用格式无效")
            structured.append(mapped)

        unknown_evidence = sorted({source_id for source_id in legacy_ids if source_id not in by_source})
        if unknown_evidence:
            raise WorkspaceError("复核记录引用了当前运行不存在的来源：" + ", ".join(unknown_evidence))

        canonical: list[dict] = []
        seen_refs: set[tuple[str, str, str]] = set()

        def append_edge(edge: dict):
            source_id = edge.get("source_id")
            locator = edge.get("locator")
            sha256 = edge.get("sha256")
            if not all(isinstance(item, str) and item for item in (source_id, locator, sha256)):
                raise WorkspaceError("当前运行的来源定位不完整，无法写入复核记录")
            key = (source_id, locator, sha256)
            if key in seen_refs:
                return
            seen_refs.add(key)
            quote = edge.get("quote")
            canonical.append({"source_id": source_id, "locator": locator,
                              "sha256": sha256, "quote": quote,
                              "unresolved": bool(edge.get("unresolved") is True or quote is None)})

        # Legacy source-only values are expanded to all matching graph edges.
        # The audit payload records the concrete locators, so old clients gain
        # replayable provenance without changing their request shape.
        for source_id in dict.fromkeys(legacy_ids):
            for edge in by_source[source_id]:
                append_edge(edge)

        for reference in structured:
            source_id = reference.get("source_id")
            locator = reference.get("locator")
            if not isinstance(source_id, str) or not isinstance(locator, str):
                raise WorkspaceError("复核记录的来源引用必须包含 source_id 和 locator")
            matches = [edge for edge in by_source.get(source_id, []) if edge.get("locator") == locator]
            if not matches:
                raise WorkspaceError("复核记录引用了当前运行不存在的来源定位：" + source_id + "#" + locator)
            for edge in matches:
                expected_hash = edge.get("sha256")
                if reference.get("sha256") != expected_hash:
                    raise WorkspaceError("复核记录来源哈希与当前运行不一致：" + source_id + "#" + locator)
                if "quote" in reference and reference["quote"] != edge.get("quote"):
                    raise WorkspaceError("复核记录引用原文与当前运行不一致：" + source_id + "#" + locator)
                unresolved = edge.get("quote") is None or edge.get("unresolved") is True
                if type(reference.get("unresolved", False)) is not bool or reference.get("unresolved", False) != unresolved:
                    raise WorkspaceError("缺失原文必须明确标记为未解决引用")
                append_edge(edge)

        evidence_ids = list(dict.fromkeys(legacy_ids + [item["source_id"] for item in structured]))
        record = {"schema_version": "ontolens-review-1", "id": identifier("review_"),
                  "run_id": run_id, "version_id": run["version_id"],
                  "snapshot_hash": run["result"]["snapshot_hash"],
                  "request_sha256": digest(encode(run["request"]).encode("utf-8")),
                  "reviewer": reviewer, "review_status": review_status,
                  "note": note, "evidence_ids": evidence_ids,
                  "evidence_references": canonical,
                  "decision_written": False,
                  "reviewer_identity_verified": False,
                  "boundary": "人工记录不改变原始判定；needs_review 仍无业务决定"}
        with self.connect(write=True) as connection:
            # Validate the original bytes and stored passage under the same
            # write transaction as the audit entry. Never record a stale
            # passage as reviewed after its stored source has changed.
            documents = {}
            for ref in canonical:
                source_id = ref["source_id"]
                if source_id not in documents:
                    documents[source_id] = connection.execute(
                        "SELECT sha256,raw,chunks FROM documents WHERE id=?", (source_id,)).fetchone()
                document = documents[source_id]
                if (document is None or document["sha256"] != ref["sha256"]
                        or digest(document["raw"]) != ref["sha256"]):
                    raise WorkspaceError("来源原始字节或哈希已改变，请重新核对", 409)
                chunks = json.loads(document["chunks"])
                matches = [item for item in chunks if item.get("locator") == ref["locator"]]
                if ref["unresolved"]:
                    if ref["quote"] is not None or matches:
                        raise WorkspaceError("未解决引用与来源定位状态不一致", 409)
                elif len(matches) != 1 or matches[0].get("text") != ref["quote"]:
                    raise WorkspaceError("来源定位或原文已改变，请重新核对", 409)
            receipt = self._event(connection, "human_review_recorded", record)
        return {**record, **receipt}

    def runs(self, limit=50):
        with self.connect() as connection:
            ids = [row[0] for row in connection.execute("SELECT id FROM runs ORDER BY created_at DESC LIMIT ?", (limit,))]
        return [self.run(run_id) for run_id in ids]

    def candidate(self, candidate_id):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row:
            raise WorkspaceError("候选不存在", 404)
        return {**dict(row), "snapshot": json.loads(row["snapshot"]), "patch": json.loads(row["patch"])}

    def candidates(self):
        with self.connect() as connection:
            ids = [row[0] for row in connection.execute("SELECT id FROM candidates ORDER BY created_at DESC")]
        return [{key: value for key, value in self.candidate(candidate_id).items() if key != "snapshot"}
                for candidate_id in ids]

    def propose(self, patch: dict):
        parent = self.version(patch["parent_id"])
        snapshot = copy.deepcopy(parent["snapshot"])
        if snapshot.get("mode") == "imported_workspace":
            raise WorkspaceError("业务授权更新须重新导入带完整原始来源的资料包；合成来源候选不能覆盖业务台账", 409)
        if patch["requester_id"] not in snapshot["catalog"]["people"]:
            raise WorkspaceError("候选人员不存在")
        document = self.document(patch["source_id"])
        if document["kind"] != "synthetic":
            raise WorkspaceError("无专业审核时只允许发布合成演示来源；真实资料保留待审核", 409)
        if not any(chunk["locator"] == patch["locator"] and chunk["text"].strip() for chunk in document["chunks"]):
            raise WorkspaceError("需要选择一个真实存在的非空来源片段")
        if not set(patch["classes"]).issubset(HAZARD_CLASSES):
            raise WorkspaceError("授权类别不受当前 schema 支持")
        snapshot["catalog"]["people"][patch["requester_id"]]["classes"] = patch["classes"]
        snapshot["person_evidence"][patch["requester_id"]] = {
            "source_id": patch["source_id"], "locator": patch["locator"], "sha256": document["sha256"],
            "review_type": "demo_operator_confirmation", "human_reviewer": None}
        snapshot["validity"][patch["requester_id"]] = {"from": patch["valid_from"], "until": patch["valid_until"]}
        candidate_id = identifier("cand_")
        with self.connect(write=True) as connection:
            connection.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?,?)", (
                candidate_id, parent["id"], encode(snapshot), encode(patch), "proposed", None, timestamp()))
            self._event(connection, "demo_candidate_created", {"candidate_id": candidate_id})
        return self.candidate(candidate_id)

    def preview(self, candidate_id):
        candidate = self.candidate(candidate_id)
        parent = self.version(candidate["parent_id"])
        changes = []
        for run in self.runs(500):
            if run["version_id"] != parent["id"]:
                continue
            before = self._calculate(parent["snapshot"], run["request"])
            after = self._calculate(candidate["snapshot"], run["request"])
            if before != after:
                changes.append({"run_id": run["id"], "request_id": run["request"]["request_id"],
                                "before": before, "after": after})
        imported = candidate["patch"].get("type") == "ledger_bundle"
        gate = None
        if imported:
            documents = {source_id: self.document(source_id, include_raw=True)
                         for source_id in candidate["snapshot"]["provenance"].values()}
            gate = snapshot_report(candidate["snapshot"], documents)
            if gate["accepted"]:
                gate["invariants"] = candidate_invariants(candidate["snapshot"])
                gate["accepted"] = gate["invariants"]["accepted"]
        return {"candidate_id": candidate_id, "parent_id": parent["id"], "changes": changes,
                "compared_scope": "最近 500 条记录中属于候选父版本的申请",
                "evaluation": {"label": "候选业务资料结构和原始文件一致性检查", "v2_gate": gate} if imported else self.baseline(),
                "structural_validation": gate,
                "semantic_review": "未做专业审核；只检查导入结构、来源一致性和引用约束" if imported else "未做专业审核；只检查合成演示结构与既有基准"}

    def publish(self, candidate_id, expected_active, note):
        candidate = self.candidate(candidate_id)
        if not note.strip():
            raise WorkspaceError("请填写发布说明")
        report = self.preview(candidate_id)
        if not report["evaluation"]["v2_gate"]["accepted"]:
            raise WorkspaceError("候选结构或来源核验未通过", 409)
        with self.connect(write=True) as connection:
            current = connection.execute("SELECT value FROM settings WHERE key='active'").fetchone()[0]
            status = connection.execute("SELECT status FROM candidates WHERE id=?", (candidate_id,)).fetchone()[0]
            if current != expected_active or current != candidate["parent_id"] or status != "proposed":
                raise WorkspaceError("当前版本已改变或候选已处理，请重新预览", 409)
            if candidate["patch"].get("type") == "ledger_bundle":
                documents = {}
                for source_id in candidate["snapshot"]["provenance"].values():
                    row = connection.execute("SELECT * FROM documents WHERE id=?", (source_id,)).fetchone()
                    if row is None:
                        raise WorkspaceError("候选来源已丢失", 409)
                    documents[source_id] = {**dict(row), "chunks": json.loads(row["chunks"])}
                if not snapshot_report(candidate["snapshot"], documents)["accepted"]:
                    raise WorkspaceError("发布事务内来源核验失败", 409)
            version_id = identifier("ver_")
            snapshot_text = encode(candidate["snapshot"])
            connection.execute("INSERT INTO versions VALUES(?,?,?,?,?,?)", (
                version_id, current, snapshot_text, digest(snapshot_text.encode()),
                candidate["patch"].get("label", "合成授权变更"), timestamp()))
            connection.execute("UPDATE settings SET value=? WHERE key='active'", (version_id,))
            connection.execute("UPDATE candidates SET status='published',version_id=? WHERE id=?", (version_id, candidate_id))
            self._event(connection, "ledger_version_published" if candidate["patch"].get("type") == "ledger_bundle" else "demo_version_published", {"version_id": version_id, "parent_id": current,
                        "note": note, "human_reviewer": None, "report": report})
        return self.version(version_id)

    def rollback(self, target_id, expected_active, note):
        self.version(target_id)
        if not note.strip():
            raise WorkspaceError("请填写回滚原因")
        with self.connect(write=True) as connection:
            current = connection.execute("SELECT value FROM settings WHERE key='active'").fetchone()[0]
            if current != expected_active:
                raise WorkspaceError("当前版本已改变，请刷新", 409)
            cursor = current
            ancestors = set()
            while cursor:
                ancestors.add(cursor)
                row = connection.execute("SELECT parent_id FROM versions WHERE id=?", (cursor,)).fetchone()
                cursor = row[0] if row else None
            if target_id == current or target_id not in ancestors:
                raise WorkspaceError("只能回滚到当前版本的历史祖先", 409)
            connection.execute("UPDATE settings SET value=? WHERE key='active'", (target_id,))
            self._event(connection, "demo_version_rolled_back", {"from": current, "to": target_id, "note": note})
        return self.version(target_id)

    def audit(self):
        with self.connect() as connection:
            return [{**dict(row), "payload": json.loads(row["payload"])} for row in connection.execute(
                "SELECT * FROM audit ORDER BY sequence DESC LIMIT 300")]

    def baseline(self):
        catalog = load_catalog(self.root / "data/catalog.yaml")
        rules = {version: load_rules(self.root / f"data/rules/{version}.yaml") for version in ("v1", "v2", "v3")}
        cases = {name: load_cases(self.root / f"data/cases/{name}.yaml") for name in ("regression", "incidents", "heldout")}
        def gate(version):
            return review_promotion(catalog, rules["v1"], rules[version], cases["regression"],
                                    cases["incidents"], cases["heldout"],
                                    candidate_text=(self.root / f"data/rules/{version}.yaml").read_text(encoding="utf-8"))
        return {"label": "冻结合成规则基准，非行业准确率、非本体算法评测", "v1": evaluate(catalog, rules["v1"], cases["heldout"]),
                "v2": evaluate(catalog, rules["v2"], cases["heldout"]), "v2_gate": gate("v2"), "v3_gate": gate("v3")}

    def export(self, run_id):
        run = self.run(run_id)
        version = self.version(run["version_id"])
        snapshot = version["snapshot"]
        # An authorization override replaces its graph edge, but the original
        # people source still supports roles, bans and the rest of the snapshot.
        source_ids = set(snapshot["provenance"].values()) | {
            item["source_id"] for item in snapshot["person_evidence"].values()
        } | {edge["source_id"] for edge in run["result"]["evidence"]}
        sources = []
        for source_id in sorted(source_ids):
            source = self.document(source_id, include_raw=True)
            # Parsed chunks lose BOMs, whitespace and binary file data. Preserve
            # exact bytes so a detached replay can recompute every source hash.
            source["raw_base64"] = base64.b64encode(source.pop("raw")).decode("ascii")
            source["raw_encoding"] = "base64"
            sources.append(source)
        return {"format": "ontolens-replay-1", "run": run, "version": version,
                "sources": sources,
                "mode": snapshot.get("mode", "synthetic_demo"),
                "notice": "合成演示复现包；无人员身份或专业审核背书" if snapshot.get("mode") == "synthetic_demo" else "导入资料复现包；可核验字节、来源映射和程序结果，不验证身份、真实性或专业审核"}

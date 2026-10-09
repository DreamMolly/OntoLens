"""Operator-authorized ledger bundles; originals and normalized facts stay separate."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from datetime import date
from itertools import islice, product
from typing import Any

import yaml

from ontolens.catalog import HAZARD_CLASSES, LOT_STATUSES
from ontolens.checker import decide

GROUPS = ("people", "chemicals", "lots", "cabinets", "issues", "rules")
SCHEMA = "peiwu-ledger-bundle-1"
MAX_FILE_BYTES = 2_000_000


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _mapping_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate mapping key: " + str(key))
        result[key] = value
    return result


class StrictLoader(yaml.SafeLoader):
    pass


def _yaml_mapping(loader, node):
    return _mapping_pairs(loader.construct_pairs(node, deep=True))


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _yaml_mapping)


def parse_source(group: str, raw: bytes, media_type: str) -> dict:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_FILE_BYTES:
        raise ValueError(group + " file must contain 1..2000000 bytes")
    text = raw.decode("utf-8-sig")
    if media_type == "application/json":
        data = json.loads(text, object_pairs_hook=_mapping_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError("non-finite JSON")))
    elif media_type in ("application/yaml", "text/yaml", "application/x-yaml"):
        if any(isinstance(token, yaml.tokens.AliasToken) for token in yaml.scan(text)):
            raise ValueError("YAML aliases are not supported in original ledgers")
        data = yaml.load(text, Loader=StrictLoader)
    elif media_type == "text/csv" and group != "rules":
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or "id" not in reader.fieldnames:
            raise ValueError(group + " CSV needs unique column names including id")
        data = {}
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("CSV row width mismatch")
            entity_id = row.pop("id")
            if entity_id in data:
                raise ValueError("duplicate CSV id: " + entity_id)
            for field in ("classes", "allowed_classes"):
                if field in row:
                    row[field] = json.loads(row[field])
            if "banned" in row:
                if row["banned"] not in ("true", "false"):
                    raise ValueError("CSV banned must be true or false")
                row["banned"] = row["banned"] == "true"
            for field in ("on_hand", "per_issue_limit"):
                if field in row:
                    row[field] = float(row[field])
            data[entity_id] = row.get("classes") if group == "issues" else row
    else:
        raise ValueError(group + " unsupported media type")
    if not isinstance(data, dict):
        raise ValueError(group + " must be an entity mapping")
    # Dates in YAML are normalized to ISO strings; originals remain unchanged.
    for row in data.values():
        if isinstance(row, dict):
            for key, value in row.items():
                if isinstance(value, date):
                    row[key] = value.isoformat()
    canonical(data)
    return data


def original_chunks(group: str, raw: bytes, media_type: str) -> list[dict]:
    """Locate exact source substrings, alongside lossless raw-byte preservation."""
    text = raw.decode("utf-8-sig")
    chunks = [{"locator": "L" + str(i), "text": line} for i, line in enumerate(text.splitlines(), 1)]
    if group == "rules":
        return chunks
    if media_type == "application/json":
        decoder = json.JSONDecoder()
        offset = text.index("{") + 1
        while offset < len(text):
            while offset < len(text) and text[offset].isspace(): offset += 1
            if text[offset] == "}": break
            key, offset = decoder.raw_decode(text, offset)
            while text[offset].isspace(): offset += 1
            offset += 1  # validated colon
            while text[offset].isspace(): offset += 1
            start = offset
            _, offset = decoder.raw_decode(text, offset)
            chunks.append({"locator": "$." + key, "text": text[start:offset]})
            while text[offset].isspace(): offset += 1
            if text[offset] == ",": offset += 1
    elif media_type in ("application/yaml", "text/yaml", "application/x-yaml"):
        node = yaml.compose(text)
        for key, value in node.value:
            chunks.append({"locator": "$." + key.value, "text": text[value.start_mark.index:value.end_mark.index]})
    else:
        lines = text.splitlines(keepends=True)
        reader = csv.DictReader(io.StringIO(text, newline=""))
        previous_line = 1
        for row in reader:
            chunks.append({"locator": "$." + row["id"], "text": "".join(lines[previous_line:reader.line_num])})
            previous_line = reader.line_num
    return chunks


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError(field + " must be non-empty text")


def _classes(value, field, empty=False):
    if (not isinstance(value, list) or (not value and not empty)
            or any(not isinstance(item, str) or item not in HAZARD_CLASSES for item in value)
            or len(set(value)) != len(value)):
        raise ValueError(field + " must contain unique supported classes")


def _number(value, field, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(field + " must be numeric")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value < 0 or (positive and value == 0):
        raise ValueError(field + " must be finite and " + ("positive" if positive else "non-negative"))


def _date(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(field + " must use YYYY-MM-DD")
    return date.fromisoformat(value)


def validate_facts(data: dict) -> dict:
    """Validate the supported domain, explicit authorizations and all references."""
    for group in GROUPS:
        if not isinstance(data.get(group), dict) or not data[group]:
            raise ValueError(group + " must be a non-empty mapping")
        if group != "rules":
            for entity_id, row in data[group].items():
                if not isinstance(entity_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", entity_id):
                    raise ValueError(group + " IDs must use ASCII letters, digits, underscore or hyphen")
                if group != "issues" and not isinstance(row, dict):
                    raise ValueError(group + "." + entity_id + " must be a mapping")
    validity = {}
    for entity_id, person in data["people"].items():
        if person.get("role") not in ("student", "teacher") or not isinstance(person.get("banned"), bool):
            raise ValueError(entity_id + " needs supported role and boolean banned")
        _classes(person.get("classes"), entity_id + ".classes", empty=True)
        _text(person.get("authorization_basis"), entity_id + ".authorization_basis")
        start = person.get("valid_from")
        end = person.get("valid_until")
        if _date(start, entity_id + ".valid_from") > _date(end, entity_id + ".valid_until"):
            raise ValueError(entity_id + " needs ordered ISO authorization dates")
        validity[entity_id] = {"from": start, "until": end}
    for entity_id, chemical in data["chemicals"].items():
        if chemical.get("hazard_class") not in HAZARD_CLASSES:
            raise ValueError(entity_id + " has unsupported hazard_class")
        _number(chemical.get("per_issue_limit"), entity_id + ".per_issue_limit", positive=True)
        if chemical.get("unit") not in ("mL", "L", "g", "kg", "cylinder"):
            raise ValueError(entity_id + " has unsupported quantity unit")
    for entity_id, lot in data["lots"].items():
        if lot.get("chemical_id") not in data["chemicals"] or lot.get("status") not in LOT_STATUSES:
            raise ValueError(entity_id + " has unknown chemical or status")
        _number(lot.get("on_hand"), entity_id + ".on_hand")
    for entity_id, cabinet in data["cabinets"].items():
        _classes(cabinet.get("allowed_classes"), entity_id + ".allowed_classes")
    if set(data["issues"]) != set(data["people"]):
        raise ValueError("issues must explicitly cover every person, including empty lists")
    for entity_id, classes in data["issues"].items():
        _classes(classes, entity_id + ".issues", empty=True)
    rules = data["rules"]
    _text(rules.get("version"), "rules.version")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", rules["version"]):
        raise ValueError("rule version must be a plain version identifier")
    _number(rules.get("student_fraction"), "rules.student_fraction")
    if rules["student_fraction"] > 1:
        raise ValueError("student_fraction must be at most 1")
    for flag in ("session_incompatibility", "deny_students"):
        if not isinstance(rules.get(flag), bool):
            raise ValueError("rules." + flag + " must be boolean")
    if not isinstance(rules.get("incompatible_pairs"), list):
        raise ValueError("rules.incompatible_pairs must be a list")
    for pair in rules["incompatible_pairs"]:
        _classes(pair, "rules.incompatible_pairs")
        if len(pair) != 2:
            raise ValueError("incompatible pair must have two classes")
    return validity


def parse_bundle(manifest: dict, files: dict[str, bytes]) -> dict:
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ValueError("unsupported ledger manifest schema")
    canonical(manifest)
    authorization = manifest.get("authorization", {})
    if not isinstance(authorization, dict) or authorization.get("local_operation_authorized") is not True:
        raise ValueError("explicit local operation authorization is required")
    for field in ("operator", "basis"):
        _text(authorization.get(field), "authorization." + field)
    metadata = manifest.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a mapping")
    for field in ("authorized_by", "purpose", "recorded_at"):
        _text(metadata.get(field), "metadata." + field)
    _date(metadata["recorded_at"], "metadata.recorded_at")
    _text(manifest.get("label"), "label")
    sources = manifest.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(GROUPS):
        raise ValueError("manifest must reference all six source groups")
    names = []
    data = {}
    for group in GROUPS:
        source = sources[group]
        if not isinstance(source, dict):
            raise ValueError(group + " source must be a mapping")
        name = source.get("file")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,150}", name) or name in (".", ".."):
            raise ValueError("file must be a plain filename")
        names.append(name)
        if source.get("kind") not in ("private", "public", "synthetic"):
            raise ValueError("source kind must be explicit")
        # Published policy text cannot assert individual access entitlements.
        if group == "people" and source["kind"] == "public":
            raise ValueError("public policy alone cannot grant personal authorization; use an authorized private ledger")
        if source.get("external_model_allowed", False) is not False:
            raise ValueError("business ledger import never grants external model access")
        raw = files.get(name)
        if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != source.get("sha256"):
            raise ValueError(group + " original file SHA256 mismatch or missing file")
        data[group] = parse_source(group, raw, source.get("media_type"))
    if len(set(names)) != 6 or set(files) != set(names):
        raise ValueError("bundle requires exactly six distinct original files")
    validity = validate_facts(data)
    return {"data": data, "validity": validity, "manifest": manifest}


def snapshot_report(snapshot: dict, documents: dict[str, dict]) -> dict:
    """Reparse originals and compare normalized facts before publishing."""
    failures = []
    try:
        manifest = snapshot["import_manifest"]
        files = {}
        for group, binding in snapshot["import_bindings"].items():
            original = documents[binding["original_source_id"]]
            normalized = documents[snapshot["provenance"][group]]
            if hashlib.sha256(original["raw"]).hexdigest() != original["sha256"]:
                raise ValueError(group + " original source modified")
            if hashlib.sha256(normalized["raw"]).hexdigest() != normalized["sha256"]:
                raise ValueError(group + " normalized source modified")
            files[binding["file"]] = original["raw"]
            if original["chunks"] != original_chunks(group, original["raw"], manifest["sources"][group]["media_type"]):
                raise ValueError(group + " original locator/value mismatch")
            expected = yaml.safe_load(snapshot["rules"]) if group == "rules" else (snapshot["issues"] if group == "issues" else snapshot["catalog"][group])
            if group == "rules":
                raw = snapshot["rules"].encode("utf-8")
                chunks = [{"locator": "L" + str(i), "text": line} for i, line in enumerate(snapshot["rules"].splitlines(), 1)]
            else:
                raw = canonical(expected).encode("utf-8")
                chunks = [{"locator": "$." + entity, "text": canonical(row)} for entity, row in sorted(expected.items())]
            if normalized["raw"] != raw or normalized["chunks"] != chunks:
                raise ValueError(group + " normalized locator/value mismatch")
        parsed = parse_bundle(manifest, files)
        facts = parsed["data"]
        if snapshot["validity"] != parsed["validity"]:
            raise ValueError("authorization validity differs from originals")
        for group in GROUPS:
            expected = yaml.safe_load(snapshot["rules"]) if group == "rules" else (snapshot["issues"] if group == "issues" else snapshot["catalog"][group])
            if facts[group] != expected:
                raise ValueError(group + " snapshot differs from original source")
    except (KeyError, ValueError, TypeError, IndexError, RecursionError, csv.Error, yaml.YAMLError, UnicodeError) as error:
        failures.append(str(error))
    return {"accepted": not failures, "failures": failures,
            "scope": "imported source bytes, schema, references, authorization dates and normalized facts",
            "professional_review_verified": False}


def candidate_invariants(snapshot: dict) -> dict:
    """Bounded executable checks against this candidate's own supported domain."""
    catalog = snapshot["catalog"]
    rules = yaml.safe_load(snapshot["rules"])
    rules["pair_set"] = {frozenset(pair) for pair in rules["incompatible_pairs"]}
    checked = 0
    failures = []
    actions = {action: 0 for action in ("ALLOW", "DENY", "LIMIT", "ISOLATE")}
    combinations = product(sorted(catalog["people"]), sorted(catalog["lots"]), sorted(catalog["cabinets"]))
    for person_id, lot_id, cabinet_id in islice(combinations, 1000):
        person = catalog["people"][person_id]
        lot = catalog["lots"][lot_id]
        material = catalog["chemicals"][lot["chemical_id"]]
        quantity = float(material["per_issue_limit"]) * 2
        if not math.isfinite(quantity):
            quantity = float(material["per_issue_limit"])
        result = decide(catalog, rules, {"requester_id": person_id, "lot_id": lot_id,
                        "destination_cabinet_id": cabinet_id, "quantity": quantity,
                        "open_issue_classes": snapshot["issues"][person_id]}).as_dict()
        checked += 1
        action = result["action"]
        if action not in actions:
            failures.append("unsupported action")
            continue
        actions[action] += 1
        approved = result["approved_quantity"]
        if action in ("ALLOW", "LIMIT"):
            cap = float(material["per_issue_limit"]) * (1 if person["role"] == "teacher" else rules["student_fraction"])
            if not isinstance(approved, (int, float)) or not math.isfinite(approved) or not 0 <= approved <= min(quantity, cap, lot["on_hand"]):
                failures.append("approved quantity exceeds request, supported role cap or original stock")
        elif approved is not None:
            failures.append("blocked action contains approved quantity")
        if person["banned"] and action != "DENY":
            failures.append("banned person permitted")
        if not person["banned"] and lot["status"] != "available" and action != "ISOLATE":
            failures.append("unavailable lot not isolated")
    return {"accepted": not failures, "checked_requests": checked, "actions": actions,
            "failures": failures, "bounded": True, "maximum_combinations": 1000,
            "scope": "program invariants using candidate facts; excludes authenticity and professional semantics"}

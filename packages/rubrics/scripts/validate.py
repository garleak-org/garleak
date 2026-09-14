#!/usr/bin/env python3
"""Validate Garleak rubric files.

Usage:
    python scripts/validate.py              # every rubric under the package root
    python scripts/validate.py PATH [...]   # given rubric files or directories

Checks each file against schema/rubric.schema.json, then the rules the schema cannot
express (file layout, item ids, changelog), then the stability of item ids between
consecutive versions of the same rubric. Exit status is 0 when clean and 1 otherwise.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "rubric.schema.json"
FILE_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)\.yaml$")
SKIP_DIRS = {"schema", "scripts", "tests", ".venv", "__pycache__"}


# --------------------------------------------------------------------------- loading


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps dates as strings and refuses duplicate keys."""


_Loader.yaml_implicit_resolvers = {
    key: [r for r in resolvers if r[0] != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _construct_mapping(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark
            )
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_yaml(path: Path):
    with open(path, encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_Loader)


def load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def make_validator() -> Draft202012Validator:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def semver(text: str) -> tuple[int, int, int]:
    major, minor, patch = (int(x) for x in text.split("."))
    return major, minor, patch


# --------------------------------------------------------------------------- discovery


def find_rubric_files(paths: list[Path] | None = None) -> list[Path]:
    """Return rubric files. A directory is either a rubric directory (holding v*.yaml)
    or a root whose child directories are rubric directories."""
    found: list[Path] = []
    for p in paths or [ROOT]:
        p = Path(p)
        if p.is_file():
            found.append(p)
            continue
        own = sorted(f for f in p.glob("v*.yaml") if FILE_RE.match(f.name))
        if own:
            found.extend(own)
            continue
        for child in sorted(p.iterdir()):
            if child.is_dir() and child.name not in SKIP_DIRS and not child.name.startswith("."):
                found.extend(sorted(f for f in child.glob("v*.yaml") if FILE_RE.match(f.name)))
    return found


# --------------------------------------------------------------------------- per file


def check_file(path: Path, data, validator: Draft202012Validator) -> list[str]:
    where = str(path)
    errors = [
        f"{where}: schema: {'/'.join(str(x) for x in e.absolute_path) or '(root)'}: {e.message}"
        for e in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    ]
    if errors:
        return errors  # the checks below assume the schema holds

    version = data["version"]
    m = FILE_RE.match(path.name)
    if not m:
        errors.append(f"{where}: file name must be v<MAJOR>.<MINOR>.<PATCH>.yaml")
    elif ".".join(m.groups()) != version:
        errors.append(f"{where}: file name says {'.'.join(m.groups())} but version is {version}")
    if path.parent.name != data["id"]:
        errors.append(f"{where}: directory {path.parent.name!r} does not match id {data['id']!r}")

    log_versions = [c["version"] for c in data["changelog"]]
    if log_versions[0] != version:
        errors.append(f"{where}: first changelog entry is {log_versions[0]}, expected {version}")
    if len(set(log_versions)) != len(log_versions):
        errors.append(f"{where}: changelog has repeated versions")
    if [semver(v) for v in log_versions] != sorted((semver(v) for v in log_versions), reverse=True):
        errors.append(f"{where}: changelog must be newest first")

    if data["status"] == "active" and (not data.get("effective_date") or not data.get("rfc")):
        errors.append(f"{where}: an active rubric needs effective_date and rfc")

    prefix = data["item_prefix"]
    tiers = set(data["applies_to_tiers"])
    ids = [item["id"] for item in data["items"]]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"{where}: item id {dup} appears more than once")
    id_set = set(ids)

    for item in data["items"]:
        iid, tier = item["id"], item["tier"]
        if not iid.startswith(f"{prefix}.{tier}."):
            errors.append(f"{where}: item {iid} must start with {prefix}.{tier}.")
        if tier not in tiers:
            errors.append(f"{where}: item {iid} is at {tier}, not in applies_to_tiers")
        added = semver(item["added_in"])
        if added > semver(version):
            errors.append(f"{where}: item {iid} added_in {item['added_in']} is after {version}")
        dep = item.get("deprecated_in")
        if dep is not None and not (added <= semver(dep) <= semver(version)):
            errors.append(f"{where}: item {iid} deprecated_in {dep} is out of range")
        rep = item.get("replaced_by")
        if rep is not None:
            if dep is None:
                errors.append(f"{where}: item {iid} has replaced_by but is not deprecated")
            if rep not in id_set:
                errors.append(f"{where}: item {iid} replaced_by {rep}, which is not in this file")

    for tier in sorted(tiers):
        live_required = [
            i for i in data["items"]
            if i["tier"] == tier and i["required"] and i.get("deprecated_in") is None
        ]
        if not live_required:
            errors.append(f"{where}: {tier} has no required, non-deprecated item")
    return errors


# --------------------------------------------------------------------------- across versions


def _bump(old: str, new: str) -> str:
    o, n = semver(old), semver(new)
    if n[0] > o[0]:
        return "major"
    if n[0] == o[0] and n[1] > o[1]:
        return "minor"
    return "patch"


def check_stability(old: dict, new: dict, where: str = "") -> list[str]:
    """Rules for moving from one version of a rubric to the next (SPEC.md 10.3)."""
    tag = f"{where}{old['id']} {old['version']} -> {new['version']}"
    errors: list[str] = []
    if semver(new["version"]) <= semver(old["version"]):
        return [f"{tag}: version must increase"]
    if old["id"] != new["id"] or old["item_prefix"] != new["item_prefix"]:
        errors.append(f"{tag}: id and item_prefix must not change")

    bump = _bump(old["version"], new["version"])
    old_items = {i["id"]: i for i in old["items"]}
    new_items = {i["id"]: i for i in new["items"]}

    def needs_major(reason: str) -> None:
        if bump != "major":
            errors.append(f"{tag}: {reason} needs a MAJOR bump, got {bump}")

    for iid, o in old_items.items():
        n = new_items.get(iid)
        if n is None:
            errors.append(f"{tag}: item {iid} was removed; deprecate it instead")
            continue
        if n["tier"] != o["tier"]:
            errors.append(f"{tag}: item {iid} changed tier")
        if n["added_in"] != o["added_in"]:
            errors.append(f"{tag}: item {iid} changed added_in")
        was_dep, is_dep = o.get("deprecated_in"), n.get("deprecated_in")
        if was_dep is not None and is_dep != was_dep:
            errors.append(f"{tag}: item {iid} deprecation cannot be undone or moved")
        if was_dep is None and is_dep is not None:
            needs_major(f"deprecating {iid}")
        if n["criteria"] != o["criteria"]:
            needs_major(f"changing the criteria of {iid}")
        if n["required"] != o["required"]:
            needs_major(f"changing whether {iid} is required")

    for iid, n in new_items.items():
        if iid in old_items:
            continue
        if n["added_in"] != new["version"]:
            errors.append(f"{tag}: new item {iid} must have added_in {new['version']}")
        if n["required"]:
            needs_major(f"adding required item {iid}")
        elif bump == "patch":
            errors.append(f"{tag}: adding advisory item {iid} needs at least a MINOR bump")

    new_log = new["changelog"]
    for entry in old["changelog"]:
        if entry not in new_log:
            errors.append(f"{tag}: changelog entry for {entry['version']} was dropped or edited")
    return errors


# --------------------------------------------------------------------------- whole tree


def validate_tree(paths: list[Path] | None = None) -> tuple[list[str], dict]:
    """Validate every rubric file found. Returns (errors, stats)."""
    validator = make_validator()
    errors: list[str] = []
    by_id: dict[str, list[tuple[tuple[int, int, int], Path, dict]]] = defaultdict(list)
    files = find_rubric_files(paths)
    if not files:
        return ["no rubric files found"], {"files": 0, "rubrics": 0, "items": 0}

    for path in files:
        try:
            data = load_yaml(path)
        except yaml.YAMLError as exc:
            errors.append(f"{path}: YAML: {exc}")
            continue
        file_errors = check_file(path, data, validator)
        errors.extend(file_errors)
        if not file_errors:
            by_id[data["id"]].append((semver(data["version"]), path, data))

    latest_owner: dict[str, str] = {}
    n_items = 0
    for rid, versions in sorted(by_id.items()):
        versions.sort(key=lambda t: t[0])
        for (_, _, old), (_, new_path, new) in zip(versions, versions[1:]):
            errors.extend(check_stability(old, new, where=f"{new_path}: "))
        latest = versions[-1][2]
        n_items += len(latest["items"])
        for item in latest["items"]:
            other = latest_owner.get(item["id"])
            if other is not None and other != rid:
                errors.append(f"item id {item['id']} is used by both {other} and {rid}")
            latest_owner[item["id"]] = rid

    stats = {"files": len(files), "rubrics": len(by_id), "items": n_items}
    return errors, stats


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] or None
    errors, stats = validate_tree(paths)
    for line in errors:
        print(line, file=sys.stderr)
    if errors:
        print(f"FAILED: {len(errors)} problem(s)", file=sys.stderr)
        return 1
    print(f"ok: {stats['files']} file(s), {stats['rubrics']} rubric(s), {stats['items']} item(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

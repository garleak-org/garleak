"""Tests for the rubric files and the validator in scripts/validate.py."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("rubric_validate", ROOT / "scripts" / "validate.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

FILES = V.find_rubric_files()


def _load(rid: str, version: str = "1.0.0") -> dict:
    return V.load_yaml(ROOT / rid / f"v{version}.yaml")


def _write(dirpath: Path, data: dict) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    path = dirpath / f"v{data['version']}.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def _bumped(data: dict, version: str, change: str) -> dict:
    new = copy.deepcopy(data)
    new["version"] = version
    new["changelog"].insert(0, {"version": version, "date": "2026-10-01", "rfc": None, "changes": [change]})
    return new


# --------------------------------------------------------------------------- the real files


def test_schema_is_a_valid_json_schema():
    Draft202012Validator.check_schema(V.load_schema())


def test_rubric_files_found():
    ids = {p.parent.name for p in FILES}
    assert {"citations", "computational", "mathematics"} <= ids


@pytest.mark.parametrize("path", FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_each_file_validates(path):
    errors = V.check_file(path, V.load_yaml(path), V.make_validator())
    assert errors == []


def test_whole_tree_validates():
    errors, stats = V.validate_tree()
    assert errors == []
    assert stats["rubrics"] >= 3


def test_item_ids_unique_within_and_across_rubrics():
    seen: dict[str, str] = {}
    for path in FILES:
        data = V.load_yaml(path)
        for item in data["items"]:
            owner = seen.setdefault(item["id"], f"{data['id']}")
            assert owner == data["id"], f"{item['id']} in {owner} and {data['id']}"
        ids = [i["id"] for i in data["items"]]
        assert len(ids) == len(set(ids))


def test_citations_is_universal_t1():
    data = _load("citations")
    assert data["field"] == "universal"
    assert data["applies_to_tiers"] == ["T1"]
    ids = {i["id"] for i in data["items"]}
    assert {"cit.T1.exists", "cit.T1.metadata-agree", "cit.T1.supports-central", "cit.T1.supports-sample"} <= ids


def test_citations_automation_uses_citecheck_for_existence_and_metadata():
    items = {i["id"]: i for i in _load("citations")["items"]}
    for iid in ("cit.T1.exists", "cit.T1.metadata-agree"):
        assert items[iid]["automation"]["level"] == "partial"
        assert "citecheck" in items[iid]["automation"]["tools"]
    assert items["cit.T1.supports-central"]["automation"]["level"] == "none"


def test_citations_sampling_rule():
    item = next(i for i in _load("citations")["items"] if i["id"] == "cit.T1.supports-sample")
    assert item["sampling"]["minimum"] == 5
    assert item["sampling"]["fraction"] == 0.1
    assert item["sampling"]["drawn_by"] == "platform"


@pytest.mark.parametrize("rid", ["computational", "mathematics"])
def test_field_rubrics_cover_t2_to_t4(rid):
    data = _load(rid)
    assert data["applies_to_tiers"] == ["T2", "T3", "T4"]
    for tier in ("T2", "T3", "T4"):
        assert any(i["tier"] == tier and i["required"] for i in data["items"])
        assert tier in data["tier_meanings"]


@pytest.mark.parametrize("rid", ["computational", "mathematics"])
def test_t4_requires_independence(rid):
    items = {i["id"]: i for i in _load(rid)["items"]}
    item = items[f"{_load(rid)['item_prefix']}.T4.independent-verifier"]
    assert item["required"] is True
    assert any(e["kind"] == "attestation" for e in item["evidence"])


def test_loader_keeps_dates_as_strings():
    data = _load("citations")
    assert isinstance(data["changelog"][0]["date"], str)


# --------------------------------------------------------------------------- validator behaviour


def test_duplicate_item_id_is_caught(tmp_path):
    data = _load("citations")
    data["items"].append(copy.deepcopy(data["items"][0]))
    _write(tmp_path / "citations", data)
    errors, _ = V.validate_tree([tmp_path])
    assert any("appears more than once" in e for e in errors)


def test_bad_item_id_fails_schema(tmp_path):
    data = _load("computational")
    data["items"][0]["id"] = "comp.T5.code-available"
    _write(tmp_path / "computational", data)
    errors, _ = V.validate_tree([tmp_path])
    assert any("schema" in e for e in errors)


def test_item_prefix_and_tier_must_match_id(tmp_path):
    data = _load("computational")
    data["items"][0]["tier"] = "T3"
    _write(tmp_path / "computational", data)
    errors, _ = V.validate_tree([tmp_path])
    assert any("must start with comp.T3." in e for e in errors)


def test_duplicate_yaml_key_is_caught(tmp_path):
    d = tmp_path / "citations"
    d.mkdir()
    text = (ROOT / "citations" / "v1.0.0.yaml").read_text(encoding="utf-8")
    (d / "v1.0.0.yaml").write_text(text + "\ntitle: Again\n", encoding="utf-8")
    errors, _ = V.validate_tree([tmp_path])
    assert any("duplicate key" in e for e in errors)


def test_deprecation_with_major_bump_is_stable(tmp_path):
    old = _load("citations")
    new = _bumped(old, "2.0.0", "Deprecate the in-text match item.")
    item = next(i for i in new["items"] if i["id"] == "cit.T1.in-text-match")
    item["deprecated_in"] = "2.0.0"
    _write(tmp_path / "citations", old)
    _write(tmp_path / "citations", new)
    errors, _ = V.validate_tree([tmp_path])
    assert errors == []


def test_removing_an_item_is_caught(tmp_path):
    old = _load("citations")
    new = _bumped(old, "2.0.0", "Drop an item.")
    new["items"] = [i for i in new["items"] if i["id"] != "cit.T1.in-text-match"]
    _write(tmp_path / "citations", old)
    _write(tmp_path / "citations", new)
    errors, _ = V.validate_tree([tmp_path])
    assert any("was removed; deprecate it instead" in e for e in errors)


def test_changed_criteria_need_major_bump(tmp_path):
    old = _load("mathematics")
    new = _bumped(old, "1.1.0", "Loosen a criterion.")
    new["items"][0]["criteria"]["pass"] = "Most statements are precise."
    _write(tmp_path / "mathematics", old)
    _write(tmp_path / "mathematics", new)
    errors, _ = V.validate_tree([tmp_path])
    assert any("needs a MAJOR bump" in e for e in errors)


def test_new_required_item_needs_major_bump(tmp_path):
    old = _load("computational")
    new = _bumped(old, "1.1.0", "Add a required item.")
    extra = copy.deepcopy(new["items"][0])
    extra.update(id="comp.T2.readme-present", title="A README exists", added_in="1.1.0")
    new["items"].append(extra)
    _write(tmp_path / "computational", old)
    _write(tmp_path / "computational", new)
    errors, _ = V.validate_tree([tmp_path])
    assert any("adding required item comp.T2.readme-present needs a MAJOR bump" in e for e in errors)


def test_new_advisory_item_with_minor_bump_is_fine(tmp_path):
    old = _load("computational")
    new = _bumped(old, "1.1.0", "Add an advisory item.")
    extra = copy.deepcopy(new["items"][0])
    extra.update(id="comp.T2.readme-present", title="A README exists", added_in="1.1.0", required=False)
    new["items"].append(extra)
    _write(tmp_path / "computational", old)
    _write(tmp_path / "computational", new)
    errors, _ = V.validate_tree([tmp_path])
    assert errors == []


def test_changelog_history_must_be_kept(tmp_path):
    old = _load("citations")
    new = _bumped(old, "1.0.1", "Fix a typo.")
    new["changelog"] = new["changelog"][:1]
    _write(tmp_path / "citations", old)
    _write(tmp_path / "citations", new)
    errors, _ = V.validate_tree([tmp_path])
    assert any("changelog entry for 1.0.0 was dropped" in e for e in errors)


def test_undeprecating_is_caught(tmp_path):
    base = _load("citations")
    v2 = _bumped(base, "2.0.0", "Deprecate.")
    next(i for i in v2["items"] if i["id"] == "cit.T1.in-text-match")["deprecated_in"] = "2.0.0"
    v3 = _bumped(v2, "3.0.0", "Bring it back.")
    next(i for i in v3["items"] if i["id"] == "cit.T1.in-text-match")["deprecated_in"] = None
    for d in (base, v2, v3):
        _write(tmp_path / "citations", d)
    errors, _ = V.validate_tree([tmp_path])
    assert any("deprecation cannot be undone" in e for e in errors)


def test_cli_exit_status(tmp_path, capsys):
    assert V.main([]) == 0
    assert "ok:" in capsys.readouterr().out
    data = _load("citations")
    data["version"] = "1.0.1"  # changelog no longer matches
    _write(tmp_path / "citations", data)
    assert V.main([str(tmp_path)]) == 1

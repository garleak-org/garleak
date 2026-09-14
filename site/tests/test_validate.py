# SPDX-License-Identifier: AGPL-3.0-or-later
"""The validator and the immutability guard."""

import os
import shutil
import subprocess

import pytest
import yaml

from garleak_archive.immutability import guard
from garleak_archive.validate import validate_path

from .conftest import EXAMPLE, REAL, copy_example


def errors(root):
    return [i.message for i in validate_path(root)[1] if i.level == "error"]


def test_both_archives_validate():
    assert errors(REAL) == []
    assert errors(EXAMPLE) == []


def test_tampered_v1_is_caught(tmp_path):
    root = copy_example(tmp_path)
    body = root / "papers" / "4471" / "v1.0" / "body.md"
    body.write_text(body.read_text().replace("1.2 Gyr", "0.6 Gyr"))
    assert any("v1.0 does not match v1_sha256" in e for e in errors(root))


def test_tampered_later_version_is_caught(tmp_path):
    root = copy_example(tmp_path)
    meta = root / "papers" / "4471" / "v2.0" / "meta.yaml"
    meta.write_text(meta.read_text() + "\n# edited\n")
    assert any("v2.0 does not match version_sha256" in e for e in errors(root))


def test_tampered_scratch_is_caught(tmp_path):
    root = copy_example(tmp_path)
    p = root / "scratches" / "8812.yaml"
    p.write_text(p.read_text().replace("Gaia DR4", "Gaia DR5"))
    assert any("do not match v1_sha256" in e for e in errors(root))


def test_every_version_needs_a_stored_hash(tmp_path):
    root = copy_example(tmp_path)
    p = root / "papers" / "4420" / "paper.yaml"
    data = yaml.safe_load(p.read_text())
    del data["version_sha256"]["1.2"]
    p.write_text(yaml.safe_dump(data))
    assert any("no hash for v1.2" in e for e in errors(root))


@pytest.mark.parametrize("field,value", [
    ("affiliations", [{"ror": "0abcdef12"}]),   # held (SPEC §11.1, H)
    ("real_name", "Hidden Person"),             # held
    ("email_domain", "example.edu"),            # held
])
def test_held_fields_are_rejected(tmp_path, field, value):
    root = copy_example(tmp_path)
    p = root / "accounts" / "kestrel.yaml"
    data = yaml.safe_load(p.read_text())
    data[field] = value
    p.write_text(yaml.safe_dump(data))
    assert any(f"unknown field '{field}'" in e for e in errors(root))


def test_pseudonymous_account_cannot_carry_orcid(tmp_path):
    root = copy_example(tmp_path)
    p = root / "accounts" / "kestrel.yaml"
    p.write_text(p.read_text() + "orcid: 0000-0002-1825-0097\n")
    assert any("pseudonymous account must not carry an ORCID" in e for e in errors(root))


def test_verification_must_attach_to_an_existing_version(tmp_path):
    root = copy_example(tmp_path)
    p = root / "papers" / "4471" / "verifications" / "4471-08.yaml"
    p.write_text(p.read_text().replace("version: '3.0'", "version: '3.1'"))
    assert any("version 3.1 does not exist" in e for e in errors(root))


def test_rubric_must_exist(tmp_path):
    root = copy_example(tmp_path)
    p = root / "papers" / "4471" / "verifications" / "4471-08.yaml"
    p.write_text(p.read_text().replace("version: 1.0.0", "version: 9.0.0"))
    assert any("rubric computational 9.0.0 does not exist" in e for e in errors(root))


def test_ids_are_unique(tmp_path):
    root = copy_example(tmp_path)
    src = root / "papers" / "4471" / "verifications" / "4471-08.yaml"
    dst = root / "papers" / "4420" / "verifications" / "4471-08.yaml"
    shutil.copy(src, dst)
    dst.write_text(dst.read_text().replace("version: '3.0'", "version: '1.2'"))
    assert any("is also used in" in e for e in errors(root))


def test_agent_paper_is_maintained_by_its_operator():
    from garleak_archive.loader import load_archive

    assert load_archive(EXAMPLE).papers[4505].maintainers == ["kosei"]


@pytest.fixture
def repo(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    root = copy_example(tmp_path)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, env=env, check=True, capture_output=True)

    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    return root, git


def test_guard_passes_on_an_unchanged_tree(repo):
    root, _ = repo
    assert guard(root, "HEAD") == []


def test_guard_catches_an_edit_made_together_with_its_hash(repo):
    root, _ = repo
    from garleak_archive.hashing import tree_sha256

    d = root / "papers" / "4471"
    (d / "v1.0" / "body.md").write_text("rewritten\n")
    p = d / "paper.yaml"
    p.write_text(p.read_text().replace(yaml.safe_load(p.read_text())["v1_sha256"], tree_sha256(d / "v1.0")))
    errs = guard(root, "HEAD")
    assert any("v1.0 differs" in e for e in errs) and any("changed v1_sha256" in e for e in errs)


def test_guard_catches_a_deleted_version_and_a_scratch_edit(repo):
    root, _ = repo
    shutil.rmtree(root / "papers" / "4471" / "v1.1")
    s = root / "scratches" / "8813.yaml"
    s.write_text(s.read_text().replace("faint gaps", "fainter gaps"))
    errs = guard(root, "HEAD")
    assert any("v1.1 existed" in e for e in errs)
    assert any("8813.yaml changed a content field" in e for e in errs)

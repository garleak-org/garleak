# SPDX-License-Identifier: AGPL-3.0-or-later
"""Git-level immutability guard for CI (SPEC §6.1, CLAUDE.md invariant 1).

The stored hashes (v1_sha256 and version_sha256 in paper.yaml, v1_sha256 in a scratch)
catch accidental edits, but someone could edit a version and its hash together. This
guard compares the working tree with a base git revision. Every version directory that
exists at the base must still exist, byte for byte, its stored hash must not change, and
every scratch's content fields must be unchanged.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import yaml

from .hashing import scratch_content_sha256, tree_manifest

VERSION_DIR = re.compile(r"^v[1-9][0-9]*\.(0|[1-9][0-9]*)$")


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True).stdout


def _ls(repo: Path, ref: str, path: str) -> list[str]:
    try:
        out = _git(repo, "ls-tree", "--name-only", ref, "--", path.rstrip("/") + "/")
    except subprocess.CalledProcessError:
        return []
    return out.decode().splitlines()


def _base_manifest(repo: Path, ref: str, vdir_rel: str) -> str | None:
    listing = _git(repo, "ls-tree", "-r", "--name-only", ref, "--", vdir_rel + "/").decode().splitlines()
    files = [f for f in listing if not f.endswith("/.DS_Store")]
    if not files:
        return None
    lines = []
    for f in sorted(files, key=lambda s: ("./" + s[len(vdir_rel) + 1:]).encode()):
        data = _git(repo, "show", f"{ref}:{f}")
        lines.append(f"{hashlib.sha256(data).hexdigest()}  ./{f[len(vdir_rel) + 1:]}\n")
    return "".join(lines)


def _yaml_at(repo: Path, ref: str, rel: str):
    try:
        return yaml.safe_load(_git(repo, "show", f"{ref}:{rel}"))
    except subprocess.CalledProcessError:
        return None


def guard(archive_root: Path, base_ref: str) -> list[str]:
    archive_root = Path(archive_root).resolve()
    repo = Path(_git(archive_root, "rev-parse", "--show-toplevel").decode().strip())
    rel = archive_root.relative_to(repo).as_posix()
    errors: list[str] = []

    for pdir in _ls(repo, base_ref, f"{rel}/papers"):
        name = pdir.rsplit("/", 1)[-1]
        if not name.isdigit():
            continue
        for entry in _ls(repo, base_ref, pdir):
            vname = entry.rsplit("/", 1)[-1]
            if not VERSION_DIR.match(vname):
                continue
            base = _base_manifest(repo, base_ref, entry)
            if base is None:
                continue
            here = repo / entry
            if not here.is_dir():
                errors.append(f"{entry} existed at {base_ref} and has been removed; versions are immutable (§6.1.2)")
            elif tree_manifest(here) != base:
                errors.append(f"{entry} differs from {base_ref}; versions are immutable (§6.1.1, §6.1.2)")
        old = _yaml_at(repo, base_ref, f"{pdir}/paper.yaml")
        if not isinstance(old, dict):
            continue
        try:
            new = yaml.safe_load((repo / pdir / "paper.yaml").read_text())
        except OSError:
            errors.append(f"{pdir}/paper.yaml existed at {base_ref} and has been removed")
            continue
        if not isinstance(new, dict) or old.get("v1_sha256") != new.get("v1_sha256"):
            errors.append(f"{pdir}/paper.yaml changed v1_sha256; it is fixed at admission")
        new_hashes = (new or {}).get("version_sha256") or {}
        for key, value in (old.get("version_sha256") or {}).items():
            if new_hashes.get(key) != value:
                errors.append(f"{pdir}/paper.yaml changed the stored hash of v{key}")

    for entry in _ls(repo, base_ref, f"{rel}/scratches"):
        if not entry.endswith(".yaml"):
            continue
        old = _yaml_at(repo, base_ref, entry)
        if not isinstance(old, dict) or "v1_sha256" not in old:
            continue
        path = repo / entry
        if not path.exists():
            errors.append(f"{entry} existed at {base_ref} and has been removed")
            continue
        new = yaml.safe_load(path.read_text())
        if not isinstance(new, dict):
            errors.append(f"{entry} is no longer a mapping")
            continue
        if new.get("v1_sha256") != old.get("v1_sha256"):
            errors.append(f"{entry} changed v1_sha256; it is fixed at admission")
        if scratch_content_sha256(new) != scratch_content_sha256(old):
            errors.append(f"{entry} changed a content field of v1.0; a scratch's v1.0 is immutable (§6.1.1)")
    return errors

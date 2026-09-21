# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tree hash of a version directory, the immutability guard for v1.0 (SPEC §6.1).

The hash is reproducible with standard tools:

    cd archive/papers/4471/v1.0 && find . -type f ! -name .DS_Store | LC_ALL=C sort \
      | xargs shasum -a 256 | shasum -a 256

That is, sha256 over the lines "<sha256 of file>  ./<relative path>\\n", sorted by path.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

IGNORED = {".DS_Store", "Thumbs.db"}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_manifest(directory: Path) -> str:
    entries = []
    for p in directory.rglob("*"):
        if p.is_file() and p.name not in IGNORED:
            entries.append("./" + p.relative_to(directory).as_posix())
    lines = []
    for rel in sorted(entries, key=lambda s: s.encode("utf-8")):
        lines.append(f"{file_sha256(directory / rel[2:])}  {rel}\n")
    return "".join(lines)


def tree_sha256(directory: Path) -> str:
    return hashlib.sha256(tree_manifest(directory).encode("utf-8")).hexdigest()


# A sketch keeps its one version in the same file as its checks and claims, so its
# v1.0 hash covers only the content fields, serialized as canonical JSON (sorted keys,
# UTF-8, no insignificant whitespace, dates as YYYY-MM-DD strings).
SKETCH_CONTENT_FIELDS = ("id", "author", "date", "statement", "detail", "models", "assistance")


def sketch_content(data: dict) -> str:
    from .schema import jsonable

    content = {k: data[k] for k in SKETCH_CONTENT_FIELDS if k in data}
    return json.dumps(jsonable(content), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sketch_content_sha256(data: dict) -> str:
    return hashlib.sha256(sketch_content(data).encode("utf-8")).hexdigest()

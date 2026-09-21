# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared fixtures: full builds of the site, and a small archive writer for rule tests."""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import pytest
import yaml

from garleak_archive.hashing import sketch_content_sha256, tree_sha256
from garleak_archive.rubrics import RubricSet
from garleak_site.build import Builder, load_config

SITE = Path(__file__).resolve().parents[1]
REPO = SITE.parent
EXAMPLE = REPO / "archive-example"
REAL = REPO / "archive"
RUBRICS = REPO / "packages" / "rubrics"
BUILD_DATE = dt.date(2026, 9, 14)


@pytest.fixture(scope="session")
def config() -> dict:
    return load_config(SITE / "config.yaml")


@pytest.fixture(scope="session")
def built(tmp_path_factory, config):
    """The site exactly as CI builds it: archive/ at the root, archive-example/ under /example/."""
    out = tmp_path_factory.mktemp("site") / "_site"
    stats = Builder(config, out, BUILD_DATE).build()
    return out, stats


@pytest.fixture(scope="session")
def built_as_root(tmp_path_factory, config):
    """The example archive built at the root, to test the rules for a populated real archive."""
    out = tmp_path_factory.mktemp("rootsite") / "_site"
    cfg = dict(config, archive=EXAMPLE, example_archive=None)
    Builder(cfg, out, BUILD_DATE, allow_example_at_root=True).build()
    return out


def page(root: Path, path: str) -> str:
    p = root / path.lstrip("/")
    return (p / "index.html" if path.endswith("/") else p).read_text(encoding="utf-8")


def copy_example(tmp_path: Path) -> Path:
    """A copy of archive-example whose rubrics path still resolves."""
    root = tmp_path / "archive-example"
    shutil.copytree(EXAMPLE, root)
    cfg = yaml.safe_load((root / "archive.yaml").read_text())
    cfg["rubrics"] = str(RUBRICS)
    (root / "archive.yaml").write_text(yaml.safe_dump(cfg))
    return root


class ArchiveMaker:
    """Writes a small, valid archive for rule tests."""

    def __init__(self, root: Path, example: bool = False):
        self.root = root
        self.rubrics = RubricSet.load(RUBRICS)
        (root / "accounts").mkdir(parents=True)
        (root / "papers").mkdir()
        (root / "sketches").mkdir()
        (root / "archive.yaml").write_text(yaml.safe_dump({
            "name": "test archive", "example": example, "as_of": "2026-09-14",
            "recent_count": 50, "rubrics": str(RUBRICS),
        }))
        shutil.copy(REAL / "categories.yaml", root / "categories.yaml")
        for h, name in (("author", "A. Author"), ("vera", "V. Era"), ("otto", "O. Tto")):
            self.account(h, name)

    def account(self, handle: str, name: str, **extra) -> None:
        data = {"handle": handle, "display_name": name, "kind": "human", "identity_path": "orcid"}
        data.update(extra)
        (self.root / "accounts" / f"{handle}.yaml").write_text(yaml.safe_dump(data))

    def paper(self, n: int, versions: list[tuple], category: str = "phys.astro", families=("computational",),
              reopens: dict | None = None) -> Path:
        """versions: (number, change, date, body)."""
        d = self.root / "papers" / str(n)
        for number, change, date, body in versions:
            vd = d / f"v{number}"
            vd.mkdir(parents=True)
            meta = {
                "title": f"Test paper {n}", "authors": ["author"], "abstract": f"Abstract of {n}.",
                "date": date, "change": change, "submitted_by": "author",
                "assistance": {"writing": "W2", "analysis": "A1"}, "models": [{"name": "model-x"}],
                "rubric_families": list(families),
            }
            if reopens and number in reopens:
                meta["reopens"] = reopens[number]
            (vd / "meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
            (vd / "body.md").write_text(body)
        gated = self.root.joinpath("categories.yaml").read_text().split(f"code: {category}")[1].split("- code:")[0]
        data = {
            "id": f"paper:{n}", "category": category, "submitter": "author", "created": versions[0][2],
            "license": "CC-BY-4.0", "gated": "gated: true" in gated, "track": "human-prompted",
            "v1_sha256": tree_sha256(d / "v1.0"),
        }
        later = {v[0]: tree_sha256(d / f"v{v[0]}") for v in versions[1:]}
        if later:
            data["version_sha256"] = later
        (d / "paper.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
        return d

    def verification(self, n: int, vid: str, version: str, tier: str, date: str, verifier: str = "vera",
                     rubric: str | None = None, fail: bool = False, independent: bool = True) -> None:
        rubric = rubric or ("citations" if tier == "T1" else "computational")
        rub = self.rubrics.get(rubric, "1.0.0")
        items = [{"id": i.id, "verdict": "pass"} for i in rub.required_at(tier)]
        if fail:
            items[0]["verdict"] = "fail"
            items[0]["note"] = "does not hold"
        data = {
            "id": vid, "version": version, "kind": "paper", "tier": tier,
            "rubric": {"id": rubric, "version": "1.0.0"}, "verifier": verifier, "date": date,
            "result": "failed" if fail else "passed", "summary": "Checked.", "items": items,
            "independent": {"value": independent, "computed_at": date, "sources": ["test"]},
            "status": "active",
        }
        if tier == "T4":
            data["t4_attestation"] = {"text": "No conflict known.", "date": date}
        d = self.root / "papers" / str(n) / "verifications"
        d.mkdir(exist_ok=True)
        (d / f"{vid}.yaml").write_text(yaml.safe_dump(data, sort_keys=False))

    def sketch(self, n: int, statement: str, date: str = "2026-09-13", **extra) -> Path:
        data = {"id": f"sketch:{n}", "category": "phys.astro", "author": "author", "date": date,
                "statement": statement, "models": [{"name": "model-x"}],
                "assistance": {"writing": "W3", "analysis": None}}
        data.update(extra)
        data["v1_sha256"] = sketch_content_sha256(data)
        p = self.root / "sketches" / f"{n}.yaml"
        p.write_text(yaml.safe_dump(data, sort_keys=False))
        return p


@pytest.fixture
def maker(tmp_path) -> ArchiveMaker:
    return ArchiveMaker(tmp_path / "archive")

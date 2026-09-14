# SPDX-License-Identifier: AGPL-3.0-or-later
"""Identifier grammar, SPEC §2.3.2 and §2.3.3."""

import pytest

from garleak_archive.ids import Identifier, IdentifierError, VersionNumber, is_identifier


@pytest.mark.parametrize("text,form", [
    ("paper:4471", "concept"),
    ("paper:4471v3", "series"),
    ("paper:4471v3.2", "exact"),
    ("paper:4471v3.0", "exact"),
    ("scratch:8812v1.0", "exact"),
    ("paper:1v10.12", "exact"),
])
def test_valid(text, form):
    ident = Identifier.parse(text)
    assert ident.form == form
    assert str(ident) == text


@pytest.mark.parametrize("text", [
    "paper:0", "paper:04471", "paper:4471v0", "paper:4471v03", "paper:4471v3.02", "paper:4471v3.",
    "paper:4471v", "Paper:4471", "preprint:4471", "4471", "", "paper:4471v3.2.1", "paper: 4471",
    "scratch:-1",
])
def test_invalid(text):
    assert not is_identifier(text)
    with pytest.raises(IdentifierError):
        Identifier.parse(text)


def test_papers_and_scratches_are_unrelated():
    assert Identifier.parse("paper:4471") != Identifier.parse("scratch:4471")


def test_url_keys_round_trip():
    ident = Identifier.parse("paper:4471v3.2")
    assert ident.url_key == "4471v3.2"
    assert Identifier.from_url_key("paper", "4471v3.2") == ident
    assert Identifier.from_url_key("paper", "4471").form == "concept"


def test_version_order_is_numeric():
    assert VersionNumber.parse("1.10") > VersionNumber.parse("1.9")
    assert VersionNumber.parse("2.0") > VersionNumber.parse("1.10")
    assert VersionNumber.parse("1.0").is_initial


def test_yaml_float_versions_are_refused():
    with pytest.raises(IdentifierError):
        VersionNumber.parse(1.1)  # YAML reads 1.10 as 1.1, so versions must be quoted

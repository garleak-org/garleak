# SPDX-License-Identifier: AGPL-3.0-or-later
"""Identifier grammar (SPEC §2.3).

    identifier = type ":" number [ version ]
    type       = "paper" / "scratch"
    number     = nonzero *DIGIT
    version    = "v" major [ "." minor ]
    major      = nonzero *DIGIT
    minor      = "0" / ( nonzero *DIGIT )

Three forms resolve differently (§2.3.3): concept (`paper:4471`), series
(`paper:4471v3`, the latest minor in major 3) and exact (`paper:4471v3.2`).
URL keys drop the type prefix because the path already carries it
(`/abs/4471v3.2/`, `/scratch/8812/`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TYPES = ("paper", "scratch")
_NUM = r"[1-9][0-9]*"
_MINOR = r"(?:0|[1-9][0-9]*)"
IDENTIFIER_RE = re.compile(rf"^(paper|scratch):({_NUM})(?:v({_NUM})(?:\.({_MINOR}))?)?$")
URL_KEY_RE = re.compile(rf"^({_NUM})(?:v({_NUM})(?:\.({_MINOR}))?)?$")
VERSION_RE = re.compile(rf"^({_NUM})\.({_MINOR})$")


class IdentifierError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class VersionNumber:
    """An exact version, major.minor. Ordered numerically, so 1.10 sorts after 1.9."""

    major: int
    minor: int

    @classmethod
    def parse(cls, text: str) -> VersionNumber:
        if not isinstance(text, str):
            raise IdentifierError(
                f"version {text!r} must be a quoted string such as \"1.0\" "
                "(YAML reads 1.10 as the number 1.1)"
            )
        s = text[1:] if text.startswith("v") else text
        m = VERSION_RE.match(s)
        if not m:
            raise IdentifierError(f"not a version number: {text!r}")
        return cls(int(m[1]), int(m[2]))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"

    @property
    def is_initial(self) -> bool:
        return self.major == 1 and self.minor == 0

    def next_minor(self) -> VersionNumber:
        return VersionNumber(self.major, self.minor + 1)

    def next_major(self) -> VersionNumber:
        return VersionNumber(self.major + 1, 0)


V1 = VersionNumber(1, 0)


@dataclass(frozen=True)
class Identifier:
    type: str
    number: int
    major: int | None = None
    minor: int | None = None

    def __post_init__(self) -> None:
        if self.type not in TYPES:
            raise IdentifierError(f"unknown type {self.type!r}")
        if self.number < 1:
            raise IdentifierError("numbers start at 1")
        if self.minor is not None and self.major is None:
            raise IdentifierError("a minor version needs a major version")

    @classmethod
    def parse(cls, text: str) -> Identifier:
        m = IDENTIFIER_RE.match(text or "")
        if not m:
            raise IdentifierError(f"not a Garleak identifier: {text!r}")
        return cls(
            m[1],
            int(m[2]),
            int(m[3]) if m[3] else None,
            int(m[4]) if m[4] is not None else None,
        )

    @classmethod
    def from_url_key(cls, type_: str, key: str) -> Identifier:
        m = URL_KEY_RE.match(key or "")
        if not m:
            raise IdentifierError(f"not an identifier path: {key!r}")
        return cls(type_, int(m[1]), int(m[2]) if m[2] else None, int(m[3]) if m[3] is not None else None)

    @property
    def form(self) -> str:
        if self.major is None:
            return "concept"
        return "series" if self.minor is None else "exact"

    @property
    def version(self) -> VersionNumber | None:
        if self.major is None or self.minor is None:
            return None
        return VersionNumber(self.major, self.minor)

    @property
    def url_key(self) -> str:
        s = str(self.number)
        if self.major is not None:
            s += f"v{self.major}"
            if self.minor is not None:
                s += f".{self.minor}"
        return s

    def concept(self) -> Identifier:
        return Identifier(self.type, self.number)

    def __str__(self) -> str:
        return f"{self.type}:{self.url_key}"


def exact(type_: str, number: int, version: VersionNumber) -> Identifier:
    return Identifier(type_, number, version.major, version.minor)


def is_identifier(text: str) -> bool:
    return bool(IDENTIFIER_RE.match(text or ""))

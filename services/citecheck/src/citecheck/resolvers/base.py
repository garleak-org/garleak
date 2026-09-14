# SPDX-License-Identifier: AGPL-3.0-or-later
"""Resolver interface. A resolver looks up identifiers and/or searches by metadata."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..http import FetchError, Http, OfflineMiss
from ..models import Record, Reference


@dataclass
class Lookup:
    status: str  # found | not_found | error | offline_miss | skipped
    records: list[Record] = field(default_factory=list)
    query: str = ""
    note: str | None = None

    @property
    def record(self) -> Record | None:
        return self.records[0] if self.records else None


class Resolver:
    """Base class. Subclasses set `name`, `kinds` (identifier kinds they resolve), and
    `searchable` (whether they support metadata search)."""

    name = "base"
    kinds: tuple[str, ...] = ()
    searchable = False

    def __init__(self, http: Http):
        self.http = http

    def available(self) -> bool:
        return True

    def prefetch(self, kind: str, values: list[str]) -> None:
        """Optional batching hook, called once with every identifier of `kind` in the paper."""

    def lookup(self, kind: str, value: str) -> Lookup:
        return Lookup("skipped", query=value)

    def search(self, ref: Reference) -> Lookup:
        return Lookup("skipped")

    def _guard(self, query: str, fn) -> Lookup:
        try:
            return fn()
        except OfflineMiss:
            return Lookup("offline_miss", query=query, note="not in cache (offline mode)")
        except FetchError as e:
            return Lookup("error", query=query, note=str(e))
        except (ValueError, KeyError, TypeError, IndexError) as e:
            return Lookup("error", query=query, note=f"could not read response: {type(e).__name__}")

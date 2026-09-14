# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Phase 1 ORCID path (SPEC §3.7.2).

An account completes the ORCID path when its public ORCID record lists the GitHub profile
URL of the account that opened the issue. The record is read from
`https://pub.orcid.org/v3.0/<iD>/researcher-urls`. The iD's check digit is validated first
(ISO 7064 MOD 11-2), so a mistyped iD never reaches the API.

Anonymous reads share a per-IP quota, and Actions runners share IP addresses, so a
registered public-API client is recommended: set ORCID_CLIENT_ID and ORCID_CLIENT_SECRET
(exchanged for a /read-public token at run time), or ORCID_READ_PUBLIC_TOKEN. Nothing
else changes without them.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .http import Http, HttpError

ORCID_RE = re.compile(r"^(\d{4})-?(\d{4})-?(\d{4})-?(\d{3}[\dX])$")
GITHUB_PROFILE_RE = re.compile(r"^https?://(?:www\.)?github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/?$", re.I)


def normalize_orcid(text: str) -> str | None:
    """`0000-0002-1825-0097` from the forms people paste (with or without the orcid.org
    prefix or dashes, lowercase x). None when it is not shaped like an iD."""
    t = (text or "").strip()
    for prefix in ("https://orcid.org/", "http://orcid.org/", "orcid.org/"):
        if t.lower().startswith(prefix):
            t = t[len(prefix):]
    m = ORCID_RE.match(t.upper())
    return "-".join(m.groups()) if m else None


def orcid_checksum_ok(orcid: str) -> bool:
    digits = orcid.replace("-", "")
    if not re.fullmatch(r"\d{15}[\dX]", digits):
        return False
    total = 0
    for ch in digits[:-1]:
        total = (total + int(ch)) * 2
    result = (12 - total % 11) % 11
    return digits[-1] == ("X" if result == 10 else str(result))


def github_login_from_url(url: str) -> str | None:
    m = GITHUB_PROFILE_RE.match((url or "").strip())
    return m[1] if m else None


def github_url_for(urls: list[str], login: str) -> str | None:
    """The first URL that is exactly the GitHub profile of `login` (case-insensitive)."""
    for u in urls:
        got = github_login_from_url(u)
        if got and got.lower() == login.lower():
            return u.strip()
    return None


@dataclass
class OrcidRecord:
    orcid: str
    status: str  # ok | not_found | error
    urls: list[str] = field(default_factory=list)
    name: str | None = None
    http_status: int | None = None
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> OrcidRecord:
        return cls(d["orcid"], d["status"], list(d.get("urls") or []), d.get("name"), d.get("http_status"),
                   d.get("error", ""))


class OrcidClient:
    def __init__(self, http: Http, *, api_base: str, token_url: str, timeout: float = 20.0,
                 cache_dir: Path | None = None, cache_hours: float = 24.0, token: str | None = None,
                 client_id: str | None = None, client_secret: str | None = None, clock=time.time):
        self.http = http
        self.api_base = api_base.rstrip("/")
        self.token_url = token_url
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache_seconds = cache_hours * 3600
        self._token = token
        self._client_id = client_id
        self._client_secret = client_secret
        self._exchanged = False
        self.clock = clock

    @classmethod
    def from_config(cls, http: Http, cfg: dict, cache_dir: Path | None = None) -> OrcidClient:
        o = cfg["orcid"]
        return cls(http, api_base=o["api_base"], token_url=o["token_url"], timeout=o["timeout_seconds"],
                   cache_dir=cache_dir, cache_hours=o["cache_hours"],
                   token=os.environ.get("ORCID_READ_PUBLIC_TOKEN") or None,
                   client_id=os.environ.get("ORCID_CLIENT_ID") or None,
                   client_secret=os.environ.get("ORCID_CLIENT_SECRET") or None)

    # -------------------------------------------------------- auth

    def _bearer(self) -> str | None:
        if self._token or self._exchanged or not (self._client_id and self._client_secret):
            return self._token
        self._exchanged = True
        data = urllib.parse.urlencode({
            "client_id": self._client_id, "client_secret": self._client_secret,
            "grant_type": "client_credentials", "scope": "/read-public",
        }).encode()
        try:
            r = self.http.request("POST", self.token_url, data=data, timeout=self.timeout, headers={
                "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"})
            if r.status == 200:
                self._token = json.loads(r.body.decode("utf-8")).get("access_token")
        except (HttpError, ValueError):
            self._token = None  # fall back to anonymous reads
        return self._token

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        tok = self._bearer()
        if tok:
            h["Authorization"] = f"Bearer {tok}"
        return h

    # -------------------------------------------------------- cache (positive answers only)

    def _cache_path(self, orcid: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / f"{hashlib.sha256(self.api_base.encode()).hexdigest()[:8]}-{orcid}.json"

    def _cache_get(self, orcid: str) -> OrcidRecord | None:
        p = self._cache_path(orcid)
        if not p or not p.is_file():
            return None
        try:
            d = json.loads(p.read_text())
        except ValueError:
            return None
        if self.clock() - float(d.get("fetched", 0)) > self.cache_seconds:
            return None
        return OrcidRecord.from_dict(d["record"])

    def _cache_put(self, rec: OrcidRecord) -> None:
        p = self._cache_path(rec.orcid)
        if not p or rec.status != "ok":
            return  # a missing URL may be added at any moment, so misses are never cached
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"fetched": self.clock(), "record": rec.to_dict()}))

    # -------------------------------------------------------- reads

    def _get_json(self, path: str) -> tuple[int, dict | None]:
        r = self.http.request("GET", f"{self.api_base}/{path}", headers=self._headers(), timeout=self.timeout,
                              max_bytes=2_000_000)
        if r.status != 200:
            return r.status, None
        try:
            return 200, json.loads(r.body.decode("utf-8"))
        except ValueError:
            return 200, None

    def lookup(self, orcid: str) -> OrcidRecord:
        cached = self._cache_get(orcid)
        if cached:
            return cached
        try:
            status, data = self._get_json(f"{orcid}/researcher-urls")
        except HttpError as e:
            return OrcidRecord(orcid, "error", error=str(e))
        if status == 404:
            return OrcidRecord(orcid, "not_found", http_status=404)
        if status != 200 or data is None:
            return OrcidRecord(orcid, "error", http_status=status, error="unexpected answer from ORCID")
        urls = []
        for item in data.get("researcher-url") or []:
            value = ((item or {}).get("url") or {}).get("value")
            if value:
                urls.append(str(value))
        rec = OrcidRecord(orcid, "ok", urls, self._name(orcid), 200)
        self._cache_put(rec)
        return rec

    def _name(self, orcid: str) -> str | None:
        """The public name on the record, for the moderator's comparison. Best effort."""
        try:
            status, data = self._get_json(f"{orcid}/person")
        except HttpError:
            return None
        if status != 200 or not data:
            return None
        name = data.get("name") or {}

        def val(key):
            return ((name.get(key) or {}) or {}).get("value")

        credit = val("credit-name")
        if credit:
            return credit
        parts = [val("given-names"), val("family-name")]
        joined = " ".join(p for p in parts if p)
        return joined or None

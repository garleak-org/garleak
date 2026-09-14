# SPDX-License-Identifier: AGPL-3.0-or-later
"""HTTP layer: per-host rate limiting, retries, and an on-disk response cache.

Secrets (API tokens) travel only in request headers or in query parameters that are
stripped before anything is logged, hashed into a cache key, or written to disk.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from . import __version__

# Query parameters that must never reach a cache key, a cache file, or a log line.
SECRET_PARAMS = frozenset({"mailto", "api_key", "api-key", "apikey", "token", "key", "access_token"})

CACHEABLE_STATUSES = (200, 404, 410)
RETRY_STATUSES = (429, 500, 502, 503, 504)


class OfflineMiss(Exception):
    """Raised in offline mode when a request is not in the cache."""


class FetchError(Exception):
    """Raised when a request fails after retries (network error, 5xx, rate limiting)."""


def strip_secrets(url: str) -> str:
    parts = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in SECRET_PARAMS]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def default_cache_dir() -> Path:
    env = os.environ.get("CITECHECK_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "citecheck"


@dataclass
class Response:
    status: int
    url: str
    content_type: str
    content: bytes
    from_cache: bool = False

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.content.decode("utf-8", errors="replace"))


class Cache:
    """Content-addressed cache. One JSON metadata file (plus a .bin body) per request.

    Layout: <root>/<namespace>/<key[:2]>/<key>.json and <key>.bin
    Positive responses never expire. Negative ones (404/410) expire after negative_ttl
    seconds when online, because new records do get registered.
    """

    def __init__(self, root: Path | str, negative_ttl: float = 7 * 86400):
        self.root = Path(root)
        self.negative_ttl = negative_ttl

    @staticmethod
    def make_key(url: str, accept: str | None) -> str:
        h = hashlib.sha256()
        h.update(f"GET {strip_secrets(url)}\naccept={accept or ''}".encode())
        return h.hexdigest()

    def _paths(self, ns: str, key: str) -> tuple[Path, Path]:
        d = self.root / ns / key[:2]
        return d / f"{key}.json", d / f"{key}.bin"

    def get(self, ns: str, key: str, offline: bool) -> Response | None:
        meta_p, body_p = self._paths(ns, key)
        if not meta_p.exists() or not body_p.exists():
            return None
        try:
            meta = json.loads(meta_p.read_text())
        except (OSError, ValueError):
            return None
        status = int(meta.get("status", 0))
        if not offline and status not in CACHEABLE_STATUSES:
            return None  # recorded failures are replayed offline only
        if not offline and status != 200 and time.time() - meta.get("fetched_at", 0) > self.negative_ttl:
            return None
        return Response(status=status, url=meta.get("url", ""), content_type=meta.get("content_type", ""),
                        content=body_p.read_bytes(), from_cache=True)

    def put(self, ns: str, key: str, resp: Response) -> None:
        meta_p, body_p = self._paths(ns, key)
        meta_p.parent.mkdir(parents=True, exist_ok=True)
        tmp = body_p.with_suffix(".bin.tmp")
        tmp.write_bytes(resp.content)
        tmp.replace(body_p)
        meta = {"url": strip_secrets(resp.url), "status": resp.status,
                "content_type": resp.content_type, "fetched_at": time.time()}
        meta_p.write_text(json.dumps(meta, indent=1))


class RateLimiter:
    """Minimum spacing between requests that share a key (usually a host)."""

    def __init__(self) -> None:
        self._next: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, key: str, interval: float) -> None:
        with self._lock:
            now = time.monotonic()
            t = max(now, self._next.get(key, 0.0))
            self._next[key] = t + interval
        delay = t - now
        if delay > 0:
            time.sleep(delay)

    def push_back(self, key: str, seconds: float) -> None:
        with self._lock:
            self._next[key] = max(self._next.get(key, 0.0), time.monotonic() + seconds)


class Http:
    def __init__(self, cache: Cache | None, offline: bool = False, timeout: float = 30.0,
                 max_retries: int = 3, verbose: bool = False, client: httpx.Client | None = None):
        self.cache = cache
        self.offline = offline
        self.max_retries = max_retries
        self.verbose = verbose
        ua = f"citecheck/{__version__} (+https://garleak.org)"
        mailto = os.environ.get("CITECHECK_MAILTO", "").strip()
        if mailto:
            ua += f" (mailto:{mailto})"
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=True,
                                             headers={"User-Agent": ua})
        self.limiter = RateLimiter()
        self.stats: dict[str, dict[str, int]] = {}

    def _stat(self, host: str, field: str) -> None:
        self.stats.setdefault(host, {"requests": 0, "cache_hits": 0, "errors": 0})[field] += 1

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[citecheck] {msg}", file=sys.stderr)

    def get(self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None,
            ns: str = "misc", rate_key: str | None = None, interval: float = 1.0,
            use_cache: bool = True, max_retries: int | None = None, timeout: float | None = None) -> Response:
        """GET with cache, rate limit, and retries. Raises OfflineMiss or FetchError."""
        full = str(httpx.URL(url, params=params)) if params else url
        accept = (headers or {}).get("Accept")
        host = urlsplit(full).netloc
        rate_key = rate_key or host
        key = Cache.make_key(full, accept)
        safe_url = strip_secrets(full)
        if self.cache is not None and use_cache:
            hit = self.cache.get(ns, key, self.offline)
            if hit is not None:
                self._stat(host, "cache_hits")
                self._log(f"cache {hit.status} {safe_url}")
                if hit.status not in CACHEABLE_STATUSES:
                    # a failure recorded during an earlier live run (offline replay only)
                    raise FetchError(f"recorded failure ({hit.text}): {safe_url}")
                return hit
        if self.offline:
            raise OfflineMiss(f"offline and not cached: {safe_url}")
        retries = self.max_retries if max_retries is None else max_retries
        last_err = ""
        last_status = 0
        for attempt in range(retries + 1):
            self.limiter.wait(rate_key, interval)
            self._stat(host, "requests")
            try:
                if timeout is not None:
                    r = self.client.get(full, headers=headers, timeout=timeout)
                else:
                    r = self.client.get(full, headers=headers)
            except httpx.HTTPError as e:
                last_err = f"{type(e).__name__}"
                self._log(f"error {last_err} {safe_url}")
                time.sleep(min(30.0, interval * 2 ** attempt + 1))
                continue
            self._log(f"GET {r.status_code} {safe_url}")
            if r.status_code in RETRY_STATUSES:
                last_err = f"HTTP {r.status_code}"
                last_status = r.status_code
                ra = r.headers.get("Retry-After", "")
                wait = float(ra) if ra.replace(".", "", 1).isdigit() else min(60.0, max(interval, 2.0) * 2 ** (attempt + 1))
                wait = min(wait, 90.0)
                self.limiter.push_back(rate_key, wait)
                continue
            resp = Response(status=r.status_code, url=str(r.url), content_type=r.headers.get("content-type", ""),
                            content=r.content)
            if self.cache is not None and use_cache and r.status_code in CACHEABLE_STATUSES:
                self.cache.put(ns, key, Response(resp.status, full, resp.content_type, resp.content))
            return resp
        self._stat(host, "errors")
        if self.cache is not None and use_cache:
            # Recorded so that an offline replay of this run behaves the same way.
            # Never served online (see Cache.get).
            self.cache.put(ns, key, Response(last_status, full, "citecheck/failure",
                                             (last_err or "request failed").encode()))
        raise FetchError(f"{last_err or 'request failed'} after {retries + 1} attempt{'s' if retries else ''}: "
                         f"{safe_url}")

    def close(self) -> None:
        self.client.close()

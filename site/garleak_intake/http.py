# SPDX-License-Identifier: AGPL-3.0-or-later
"""A minimal HTTP client behind an interface the tests replace. Standard library only."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

USER_AGENT = "garleak-intake/0.1 (+https://garleak.org)"


class HttpError(Exception):
    """The request could not be completed (network, timeout, size, redirect)."""


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict = field(default_factory=dict)
    url: str = ""


class Http(Protocol):
    def request(self, method: str, url: str, *, headers: dict | None = None, data: bytes | None = None,
                timeout: float = 20.0, max_bytes: int | None = None) -> Response: ...


class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise HttpError("refused a redirect to a URL that is not https")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibHttp:
    def __init__(self, user_agent: str = USER_AGENT):
        self.user_agent = user_agent
        self._opener = urllib.request.build_opener(_HttpsOnly())

    def request(self, method: str, url: str, *, headers: dict | None = None, data: bytes | None = None,
                timeout: float = 20.0, max_bytes: int | None = None) -> Response:
        if not url.startswith("https://"):
            raise HttpError("only https URLs are fetched")
        h = {"User-Agent": self.user_agent}
        h.update(headers or {})
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with self._opener.open(req, timeout=timeout) as r:
                body = r.read(max_bytes + 1) if max_bytes else r.read()
                if max_bytes and len(body) > max_bytes:
                    raise HttpError(f"the file is larger than {max_bytes} bytes")
                return Response(r.status, body, dict(r.headers), r.geturl())
        except urllib.error.HTTPError as e:
            return Response(e.code, e.read(65536) if e.fp else b"", dict(e.headers or {}), url)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise HttpError(str(getattr(e, "reason", e))) from e

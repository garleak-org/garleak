# SPDX-License-Identifier: AGPL-3.0-or-later
"""Files attached to an issue form.

GitHub stores a file dragged into an issue textarea and leaves a link such as
`[paper.md](https://github.com/user-attachments/files/123/paper.md)`. A field that holds
nothing but one such link is replaced by the file. Links are followed only when they
start with a prefix listed in config.yaml (`intake.attachment_prefixes`), only over https,
and only up to the size limit for that field."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .http import Http, HttpError

MD_LINK = re.compile(r"^!?\[[^\]]*\]\((https://[^)\s]+)\)$")
BARE = re.compile(r"^<?(https://\S+?)>?$")


class AttachmentError(Exception):
    pass


def sole_link(text: str) -> str | None:
    """The URL when the text is exactly one link, in markdown or bare form."""
    t = (text or "").strip()
    m = MD_LINK.match(t) or BARE.match(t)
    return m[1] if m else None


def filename(url: str) -> str:
    return url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1].lower()


@dataclass
class Fetcher:
    http: Http | None
    prefixes: list[str]
    offline: bool = False

    def allowed(self, url: str) -> bool:
        return any(url.startswith(p) for p in self.prefixes)

    def fetch(self, url: str, max_bytes: int) -> bytes:
        if not self.allowed(url):
            raise AttachmentError("the link is not a file attached to this issue on GitHub")
        if self.offline or self.http is None:
            raise AttachmentError("attachments cannot be downloaded in offline mode")
        try:
            r = self.http.request("GET", url, timeout=60, max_bytes=max_bytes)
        except HttpError as e:
            raise AttachmentError(f"the download failed ({e})") from e
        if r.status != 200:
            raise AttachmentError(f"GitHub answered HTTP {r.status}")
        return r.body


def text_field(text: str, fetcher: Fetcher, max_bytes: int, suffixes: tuple[str, ...]) -> tuple[str, str | None]:
    """The field's text, or the attached file it links to. Returns (content, url or None)."""
    link = sole_link(text)
    if link and fetcher.allowed(link):
        if not filename(link).endswith(suffixes):
            raise AttachmentError(f"attach a file ending in {' or '.join(suffixes)}")
        data = fetcher.fetch(link, max_bytes)
        try:
            return data.decode("utf-8"), link
        except UnicodeDecodeError as e:
            raise AttachmentError("the attached file is not UTF-8 text") from e
    if len(text.encode("utf-8")) > max_bytes:
        raise AttachmentError(f"the text is larger than {max_bytes} bytes")
    return text, None


def pdf_field(text: str, fetcher: Fetcher, max_bytes: int) -> tuple[bytes | None, str | None]:
    if not (text or "").strip():
        return None, None
    link = sole_link(text)
    if not link or not fetcher.allowed(link):
        raise AttachmentError("drag the PDF into the field so that GitHub attaches it")
    if not filename(link).endswith(".pdf"):
        raise AttachmentError("the attachment is not a .pdf file")
    data = fetcher.fetch(link, max_bytes)
    if not data.startswith(b"%PDF-"):
        raise AttachmentError("the attached file is not a PDF")
    return data, link

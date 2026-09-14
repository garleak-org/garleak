# SPDX-License-Identifier: AGPL-3.0-or-later
"""The ORCID iD checksum, the GitHub URL match, and the public-API client (offline)."""

import json

import pytest

from garleak_intake.http import HttpError, Response
from garleak_intake.orcid import OrcidClient, github_url_for, normalize_orcid, orcid_checksum_ok

from .intake_support import FakeHttp

ID = "0000-0002-1825-0097"
BASE = "https://pub.orcid.org/v3.0"
URLS = f"{BASE}/{ID}/researcher-urls"
PERSON = f"{BASE}/{ID}/person"
TOKEN = "https://orcid.org/oauth/token"


@pytest.mark.parametrize("orcid,ok", [
    ("0000-0002-1825-0097", True),
    ("0000-0001-5109-3700", True),
    ("0000-0002-1694-233X", True),
    ("0000-0002-1825-0098", False),
    ("0000-0002-1694-2339", False),
    ("0000-0002-1825-009", False),
])
def test_checksum(orcid, ok):
    assert orcid_checksum_ok(orcid) is ok


def test_normalize():
    assert normalize_orcid("https://orcid.org/0000-0002-1825-0097") == ID
    assert normalize_orcid(" 0000000218250097 ") == ID
    assert normalize_orcid("0000-0002-1694-233x") == "0000-0002-1694-233X"
    assert normalize_orcid("1234-5678") is None


@pytest.mark.parametrize("url,login,match", [
    ("https://github.com/Dana", "dana", True),
    ("http://www.github.com/dana/", "Dana", True),
    ("  https://github.com/dana  ", "dana", True),
    ("https://github.com/dana/repo", "dana", False),
    ("https://gist.github.com/dana", "dana", False),
    ("https://github.com/danax", "dana", False),
    ("https://github.com/dana?tab=repositories", "dana", False),
    ("https://github.com.evil.example/dana", "dana", False),
])
def test_github_url_match(url, login, match):
    assert (github_url_for([url], login) is not None) is match


def urls_body(*urls):
    return json.dumps({"researcher-url": [{"url-name": "GitHub", "url": {"value": u}} for u in urls]}).encode()


def test_lookup_uses_the_client_token_and_caches_only_positive_answers(tmp_path):
    clock = [1000.0]
    http = FakeHttp({("POST", TOKEN): Response(200, b'{"access_token": "tok"}'),
                     URLS: Response(200, urls_body("https://github.com/dana")),
                     PERSON: Response(200, b'{"name": {"credit-name": {"value": "Dana Example"}}}')})
    client = OrcidClient(http, api_base=BASE, token_url=TOKEN, cache_dir=tmp_path, cache_hours=24,
                         client_id="APP-1", client_secret="s3cret", clock=lambda: clock[0])
    rec = client.lookup(ID)
    assert rec.status == "ok" and rec.urls == ["https://github.com/dana"] and rec.name == "Dana Example"
    gets = [c for c in http.calls if c[0] == "GET"]
    assert all(c[2]["Authorization"] == "Bearer tok" for c in gets)
    assert [c[0] for c in http.calls].count("POST") == 1 and b"scope=%2Fread-public" in http.calls[0][3]
    n = len(http.calls)
    assert client.lookup(ID).status == "ok" and len(http.calls) == n  # served from the cache
    clock[0] += 25 * 3600
    client.lookup(ID)
    assert len(http.calls) > n  # expired


def test_misses_are_never_cached(tmp_path):
    http = FakeHttp({URLS: Response(404, b"{}")})
    client = OrcidClient(http, api_base=BASE, token_url=TOKEN, cache_dir=tmp_path)
    assert client.lookup(ID).status == "not_found"
    http.routes[URLS] = Response(200, urls_body("https://github.com/dana"))
    assert client.lookup(ID).status == "ok"


def test_anonymous_reads_and_errors():
    http = FakeHttp({URLS: HttpError("timed out")})
    client = OrcidClient(http, api_base=BASE, token_url=TOKEN)
    rec = client.lookup(ID)
    assert rec.status == "error" and "timed out" in rec.error
    assert "Authorization" not in http.calls[0][2]
    http.routes[URLS] = Response(503, b"")
    assert client.lookup(ID).status == "error"

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from garleak_api.models import Account
from garleak_api.orcid import (
    OrcidExchangeError,
    OrcidIdentity,
    build_authorize_url,
    exchange_code,
    get_token_exchanger,
    is_valid_orcid_id,
)
from garleak_api.settings import Settings
from tests.conftest import TEST_CLIENT_ID, TEST_CLIENT_SECRET

# ORCID's own documentation examples; the check digits are valid.
EXAMPLE_ORCID = "0000-0002-1825-0097"


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("0000-0002-1825-0097", True),
        ("0000-0001-5109-3700", True),
        ("0000-0002-1694-233X", True),
        ("0000-0002-1825-0098", False),
        ("0000-0002-1825-009", False),
        ("https://orcid.org/0000-0002-1825-0097", False),
    ],
)
def test_orcid_checksum(value: str, ok: bool) -> None:
    assert is_valid_orcid_id(value) is ok


def test_authorize_url_targets_sandbox_by_default(settings: Settings) -> None:
    url = build_authorize_url(settings, state="abc123")
    parts = urlsplit(url)
    assert (
        f"{parts.scheme}://{parts.netloc}{parts.path}"
        == "https://sandbox.orcid.org/oauth/authorize"
    )
    q = parse_qs(parts.query)
    assert q == {
        "client_id": [TEST_CLIENT_ID],
        "response_type": ["code"],
        "scope": ["/authenticate"],
        "redirect_uri": ["http://testserver/auth/orcid/callback"],
        "state": ["abc123"],
    }


def test_authorize_url_never_carries_secret(settings: Settings) -> None:
    assert TEST_CLIENT_SECRET not in build_authorize_url(settings, state="s")


def test_login_redirects_with_state_stored_in_session(client: TestClient) -> None:
    resp = client.get("/auth/orcid/login", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("https://sandbox.orcid.org/oauth/authorize?")
    state = parse_qs(urlsplit(location).query)["state"][0]
    assert len(state) >= 32
    assert "garleak_session" in resp.cookies


def test_login_unconfigured_returns_503(settings: Settings) -> None:
    from garleak_api.main import create_app

    bare = settings.model_copy(update={"orcid_client_id": None, "orcid_client_secret": None})
    with TestClient(create_app(bare)) as c:
        assert c.get("/auth/orcid/login", follow_redirects=False).status_code == 503


def _login(client: TestClient, app: FastAPI, identity: OrcidIdentity) -> httpx.Response:
    seen_codes: list[str] = []

    def fake_exchange(_settings: Settings, code: str) -> OrcidIdentity:
        seen_codes.append(code)
        return identity

    app.dependency_overrides[get_token_exchanger] = lambda: fake_exchange
    login = client.get("/auth/orcid/login", follow_redirects=False)
    state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
    resp = client.get(
        "/auth/orcid/callback",
        params={"code": "auth-code-1", "state": state},
        follow_redirects=False,
    )
    assert seen_codes == ["auth-code-1"]
    return resp


def test_callback_creates_then_loads_account(client: TestClient, app: FastAPI) -> None:
    identity = OrcidIdentity(orcid_id=EXAMPLE_ORCID, name="Josiah Carberry")

    resp = _login(client, app, identity)
    assert resp.status_code == 303
    assert resp.headers["location"] == "http://localhost:3000"

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["orcid_id"] == EXAMPLE_ORCID
    first_id = me.json()["id"]

    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401

    _login(client, app, identity)
    assert client.get("/auth/me").json()["id"] == first_id

    with app.state.sessionmaker() as db:
        assert db.scalar(select(func.count()).select_from(Account)) == 1


def test_callback_rejects_bad_state(client: TestClient, app: FastAPI) -> None:
    app.dependency_overrides[get_token_exchanger] = lambda: pytest.fail  # must not be called
    client.get("/auth/orcid/login", follow_redirects=False)
    resp = client.get(
        "/auth/orcid/callback", params={"code": "x", "state": "forged"}, follow_redirects=False
    )
    assert resp.status_code == 400


def test_callback_without_prior_login_is_rejected(client: TestClient) -> None:
    resp = client.get("/auth/orcid/callback", params={"code": "x", "state": "y"})
    assert resp.status_code == 400


def test_exchange_code_posts_form_and_reads_orcid(settings: Settings) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["form"] = parse_qs(request.content.decode())
        return httpx.Response(
            200,
            json={
                "access_token": "tok",
                "token_type": "bearer",
                "scope": "/authenticate",
                "name": "Josiah Carberry",
                "orcid": EXAMPLE_ORCID,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        identity = exchange_code(settings, "the-code", client=http)

    assert identity == OrcidIdentity(orcid_id=EXAMPLE_ORCID, name="Josiah Carberry")
    assert captured["url"] == "https://sandbox.orcid.org/oauth/token"
    assert captured["form"] == {
        "client_id": [TEST_CLIENT_ID],
        "client_secret": [TEST_CLIENT_SECRET],
        "grant_type": ["authorization_code"],
        "code": ["the-code"],
        "redirect_uri": ["http://testserver/auth/orcid/callback"],
    }


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={"error": "invalid_client"}),
        httpx.Response(200, json={"access_token": "tok"}),
        httpx.Response(200, json={"orcid": "0000-0002-1825-0098"}),
    ],
)
def test_exchange_code_rejects_bad_responses(settings: Settings, response: httpx.Response) -> None:
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _r: response)) as http,
        pytest.raises(OrcidExchangeError),
    ):
        exchange_code(settings, "c", client=http)

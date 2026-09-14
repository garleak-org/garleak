"""ORCID OAuth, authorization-code flow.

Flow: /auth/orcid/login stores a random `state` in the signed session and redirects to
ORCID. ORCID redirects back to /auth/orcid/callback with `code` and `state`. We check the
state, exchange the code for a token response (which carries the ORCID iD and name for
the /authenticate scope), create or load the account keyed by that iD, and put the
account id in the session cookie. The ORCID access token is not stored; M0 only needs
identity.
"""

from __future__ import annotations

import re
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from garleak_api.db import get_db
from garleak_api.models import Account
from garleak_api.settings import Settings

ORCID_ID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
STATE_KEY = "orcid_oauth_state"
ACCOUNT_KEY = "account_id"


def is_valid_orcid_id(value: str) -> bool:
    """Format plus ISO 7064 MOD 11-2 check digit, as ORCID specifies."""
    if not ORCID_ID_RE.match(value):
        return False
    digits = value.replace("-", "")
    total = 0
    for ch in digits[:-1]:
        total = (total + int(ch)) * 2
    result = (12 - total % 11) % 11
    expected = "X" if result == 10 else str(result)
    return digits[-1] == expected


@dataclass(frozen=True)
class OrcidIdentity:
    orcid_id: str
    name: str | None


class OrcidExchangeError(Exception):
    pass


def build_authorize_url(settings: Settings, state: str) -> str:
    if not settings.orcid_client_id:
        raise OrcidExchangeError("ORCID client id is not configured")
    params = {
        "client_id": settings.orcid_client_id,
        "response_type": "code",
        "scope": settings.orcid_scope,
        "redirect_uri": settings.orcid_redirect_uri,
        "state": state,
    }
    return f"{settings.orcid_authorize_url}?{urlencode(params)}"


def exchange_code(
    settings: Settings, code: str, client: httpx.Client | None = None
) -> OrcidIdentity:
    """POST the authorization code to ORCID's token endpoint and read the iD."""
    if not settings.orcid_client_id or settings.orcid_client_secret is None:
        raise OrcidExchangeError("ORCID client credentials are not configured")
    data = {
        "client_id": settings.orcid_client_id,
        "client_secret": settings.orcid_client_secret.get_secret_value(),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.orcid_redirect_uri,
    }
    owns_client = client is None
    http = client or httpx.Client(timeout=10.0)
    try:
        resp = http.post(
            settings.orcid_token_url, data=data, headers={"Accept": "application/json"}
        )
    except httpx.HTTPError as exc:
        raise OrcidExchangeError(f"token request failed: {exc.__class__.__name__}") from exc
    finally:
        if owns_client:
            http.close()
    if resp.status_code != 200:
        raise OrcidExchangeError(f"token endpoint returned {resp.status_code}")
    payload = resp.json()
    orcid_id = payload.get("orcid")
    if not isinstance(orcid_id, str) or not is_valid_orcid_id(orcid_id):
        raise OrcidExchangeError("token response did not carry a valid ORCID iD")
    name = payload.get("name")
    return OrcidIdentity(orcid_id=orcid_id, name=name if isinstance(name, str) and name else None)


TokenExchanger = Callable[[Settings, str], OrcidIdentity]


def get_token_exchanger() -> TokenExchanger:
    """Dependency seam so tests can replace the network call."""
    return exchange_code


def get_settings_from_app(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings_from_app)]
ExchangerDep = Annotated[TokenExchanger, Depends(get_token_exchanger)]
DbDep = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/orcid/login")
def orcid_login(request: Request, settings: SettingsDep) -> RedirectResponse:
    if not settings.orcid_configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ORCID login is not configured")
    state = secrets.token_urlsafe(32)
    request.session[STATE_KEY] = state
    return RedirectResponse(build_authorize_url(settings, state), status_code=status.HTTP_302_FOUND)


@router.get("/orcid/callback")
def orcid_callback(
    request: Request,
    settings: SettingsDep,
    exchanger: ExchangerDep,
    db: DbDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    expected_state = request.session.pop(STATE_KEY, None)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"ORCID returned error: {error}")
    if (
        not code
        or not state
        or not expected_state
        or not secrets.compare_digest(state, expected_state)
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired login state")
    try:
        identity = exchanger(settings, code)
    except OrcidExchangeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"ORCID exchange failed: {exc}") from exc

    account = db.scalar(select(Account).where(Account.orcid_id == identity.orcid_id))
    if account is None:
        account = Account(orcid_id=identity.orcid_id, display_name=identity.name)
        db.add(account)
    elif identity.name and account.display_name != identity.name:
        account.display_name = identity.name
    db.commit()

    # Drop anything left from before login, then bind the session to the account.
    request.session.clear()
    request.session[ACCOUNT_KEY] = str(account.id)
    return RedirectResponse(settings.web_base_url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(request: Request, db: DbDep) -> dict[str, str | None]:
    raw = request.session.get(ACCOUNT_KEY)
    account = None
    if raw:
        try:
            account = db.get(Account, uuid.UUID(raw))
        except ValueError:
            account = None
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    return {
        "id": str(account.id),
        "orcid_id": account.orcid_id,
        "display_name": account.display_name,
    }

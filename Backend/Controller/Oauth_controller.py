import os
import logging
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError

from Backend.DBhelper.Oauth_db import (
    consume_oauth_state,
    create_oauth_state,
    disconnect_oauth_account,
    get_active_oauth_account,
    get_oauth_account_by_id,
    get_user_oauth_accounts,
    save_oauth_account,
)
from Backend.Middleware.auth_middleware import auth_middleware
from Backend.Utils.Crypto import decrypt, encrypt  # adjust path to your crypto module

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

PROVIDERS = {
    "google": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "revoke_url": "https://oauth2.googleapis.com/revoke",
        "scopes": [
            "openid",
            "email",
            "https://www.googleapis.com/auth/gmail.send",
        ],
        "extra_auth_params": {
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        },
    },
}


# ----------------------------------------------------------------- helpers --
def _provider(name: str) -> dict:
    cfg = PROVIDERS.get(name)
    if not cfg or not cfg["client_id"]:
        raise HTTPException(status_code=404, detail="Unknown or unconfigured provider")
    return cfg


def _redirect_uri(provider: str) -> str:
    return f"{BACKEND_URL}/oauth/{provider}/callback"


def _uid(user_id: str) -> UUID:
    try:
        return UUID(str(user_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid access token")


def _public_account(acc: dict) -> dict:
    """Allow-list: never leak the encrypted refresh token."""
    return {
        "id": str(acc["id"]),
        "provider": acc["provider"],
        "provider_email": acc["provider_email"],
        "scopes": (acc.get("scopes") or "").split(),
        "created_at": acc.get("created_at"),
        "updated_at": acc.get("updated_at"),
    }


def _frontend_redirect(**params) -> RedirectResponse:
    return RedirectResponse(f"{FRONTEND_URL}/settings/integrations?{urlencode(params)}")


# ------------------------------------------------------------------ routes --
async def oauth_connect(provider: str, user_id: str = Depends(auth_middleware)):
    """Returns the provider consent URL; the frontend navigates to it."""
    try:
        cfg = _provider(provider)
        state = await create_oauth_state(_uid(user_id))  # returns the raw state

        params = {
            "client_id": cfg["client_id"],
            "redirect_uri": _redirect_uri(provider),
            "response_type": "code",
            "scope": " ".join(cfg["scopes"]),
            "state": state,
            **cfg["extra_auth_params"],
        }
        return {"auth_url": f"{cfg['auth_url']}?{urlencode(params)}"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in oauth_connect for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")


async def oauth_callback(
    provider: str,
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
):
    """Hit by the browser after consent. No bearer token; the user comes from `state`."""
    try:
        cfg = _provider(provider)

        if error:
            return _frontend_redirect(oauth="error", reason="access_denied")
        if not code or not state:
            return _frontend_redirect(oauth="error", reason="invalid_request")

        uid = await consume_oauth_state(state)  # UUID or None
        if not uid:
            return _frontend_redirect(oauth="error", reason="invalid_state")

        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                cfg["token_url"],
                data={
                    "code": code,
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "redirect_uri": _redirect_uri(provider),
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code != 200:
                logger.warning("Token exchange failed: %s", token_resp.status_code)
                return _frontend_redirect(oauth="error", reason="token_exchange_failed")
            tokens = token_resp.json()

            info_resp = await client.get(
                cfg["userinfo_url"],
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            if info_resp.status_code != 200:
                return _frontend_redirect(oauth="error", reason="userinfo_failed")
            email = (info_resp.json().get("email") or "").lower()
            if not email:
                return _frontend_redirect(oauth="error", reason="no_email")
        refresh_token = tokens.get("refresh_token")
        encrypted_token = await encrypt(refresh_token) if refresh_token else None

        try:
            saved = await save_oauth_account(
                user_id=uid,
                provider=provider,
                provider_email=email,
                encrypted_refresh_token=encrypted_token,
                scopes=tokens.get("scope", " ".join(cfg["scopes"])),
            )
        except IntegrityError:
            return _frontend_redirect(oauth="error", reason="no_refresh_token")
        if not saved:
            return _frontend_redirect(oauth="error", reason="save_failed")

        return _frontend_redirect(oauth="success", provider=provider)
    except Exception:
        logger.exception("Unexpected error in oauth_callback")
        return _frontend_redirect(oauth="error", reason="internal_error")


async def list_accounts(
    provider: str = Query("google"),
    user_id: str = Depends(auth_middleware),
):
    try:
        accounts = await get_user_oauth_accounts(_uid(user_id), provider)
        return {"accounts": [_public_account(a) for a in accounts]}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in list_accounts for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")


async def disconnect_account(account_id: UUID, user_id: str = Depends(auth_middleware)):
    try:
        uid = _uid(user_id)
        acc = await get_oauth_account_by_id(uid, account_id)  # scoped to user: no IDOR
        if not acc or acc.get("revoked_at"):
            raise HTTPException(status_code=404, detail="Account not found")
        cfg = PROVIDERS.get(acc["provider"])
        if cfg and acc.get("refresh_token_encrypted"):
            try:
                token = await decrypt(acc["refresh_token_encrypted"])
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(cfg["revoke_url"], data={"token": token})
            except Exception:
                logger.warning("Provider-side revoke failed for account_id=%s", account_id)

        if not await disconnect_oauth_account(uid, account_id):
            raise HTTPException(status_code=404, detail="Account not found")
        return {"message": "Account disconnected"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in disconnect_account for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")



async def get_provider_access_token(user_id: UUID, provider: str = "google") -> tuple[str, str]:
    """Returns (access_token, provider_email) for use in Gmail send code."""
    cfg = _provider(provider)
    acc = await get_active_oauth_account(user_id, provider)
    if not acc:
        raise HTTPException(status_code=404, detail=f"No {provider} account connected")

    refresh_token = await decrypt(acc["refresh_token_encrypted"])

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            cfg["token_url"],
            data={
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

    if resp.status_code != 200:
        try:
            err = resp.json().get("error")
        except Exception:
            err = None
        if err == "invalid_grant":  # user revoked access on Google's side
            await disconnect_oauth_account(user_id, acc["id"])
            raise HTTPException(status_code=401, detail=f"{provider} access was revoked; reconnect")
        # transient failure: don't disconnect the user
        raise HTTPException(status_code=502, detail=f"Could not refresh {provider} token")

    return resp.json()["access_token"], acc["provider_email"]
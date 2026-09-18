import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Protocol

from fastapi import APIRouter, Cookie, Query, Response, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from starlette.types import ASGIApp, Receive, Scope, Send

from test_runner_service.oidc import OidcClient, OidcError, token_roles
from test_runner_service.settings import AuthMode, Settings

SESSION_COOKIE: Final = "test_runner_session"
OIDC_TRANSACTION_COOKIE: Final = "test_runner_oidc_transaction"
_PUBLIC_PATHS: Final = frozenset(
    {"/health", "/login", "/auth/status", "/auth/login", "/auth/callback", "/auth/logout"}
)


@dataclass(frozen=True)
class Principal:
    subject: str
    username: str | None
    roles: tuple[str, ...]
    method: str
    expires_at: int | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class Authenticator(Protocol):
    async def authenticate(self, scope: Scope) -> Principal | None: ...


class DisabledAuthenticator:
    async def authenticate(self, scope: Scope) -> Principal | None:
        del scope
        return Principal("anonymous", None, ("viewer", "operator"), "disabled")


class LocalAuthenticator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def authenticate(self, scope: Scope) -> Principal | None:
        headers = dict(scope["headers"])
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        if _valid_static_bearer_token(authorization, self._settings):
            return Principal("local-api-token", None, ("viewer", "operator"), "api_token")
        cookie = _cookie_value(headers.get(b"cookie", b"").decode("latin-1"), SESSION_COOKIE)
        return _decode_session(cookie, self._settings) if cookie is not None else None


class KeycloakAuthenticator:
    def __init__(self, settings: Settings, oidc: OidcClient) -> None:
        self._settings = settings
        self._oidc = oidc

    async def authenticate(self, scope: Scope) -> Principal | None:
        headers = dict(scope["headers"])
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        bearer = _bearer_value(authorization)
        if bearer is not None:
            try:
                claims = await self._oidc.verify_access_token(bearer)
            except OidcError:
                return None
            return _principal_from_claims(claims, self._settings, "oidc_bearer")
        cookie = _cookie_value(headers.get(b"cookie", b"").decode("latin-1"), SESSION_COOKIE)
        return _decode_session(cookie, self._settings) if cookie is not None else None


class AuthenticationMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        settings: Settings,
        authenticator: Authenticator,
    ) -> None:
        self._app = app
        self._settings = settings
        self._authenticator = authenticator

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in _PUBLIC_PATHS:
            await self._app(scope, receive, send)
            return
        principal = await self._authenticator.authenticate(scope)
        if principal is None:
            await self._unauthorized(scope)(scope, receive, send)
            return
        required_role = _required_role(scope)
        if required_role is not None and not _has_role(principal, required_role, self._settings):
            response = JSONResponse(
                {"detail": "insufficient permissions"},
                status_code=status.HTTP_403_FORBIDDEN,
            )
            await response(scope, receive, send)
            return
        scope["auth_principal"] = principal
        await self._app(scope, receive, send)

    @staticmethod
    def _unauthorized(scope: Scope) -> Response:
        if scope["path"] in {"/", "/artifact-runs"}:
            return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
        return JSONResponse(
            {"detail": "authentication required"},
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_authenticator(settings: Settings, oidc: OidcClient | None) -> Authenticator:
    if settings.auth_mode is AuthMode.DISABLED:
        return DisabledAuthenticator()
    if settings.auth_mode is AuthMode.LOCAL:
        return LocalAuthenticator(settings)
    if oidc is None:
        raise RuntimeError("Keycloak authentication requires an OIDC client")
    return KeycloakAuthenticator(settings, oidc)


def create_auth_router(settings: Settings, login_html: Path, oidc: OidcClient | None) -> APIRouter:
    router = APIRouter()

    @router.get("/auth/status", include_in_schema=False)
    async def auth_status() -> dict[str, object]:
        return {"enabled": settings.auth_mode is not AuthMode.DISABLED, "mode": settings.auth_mode}

    @router.get("/login", response_class=FileResponse, include_in_schema=False)
    async def login_page() -> Response:
        if settings.auth_mode is AuthMode.DISABLED:
            return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
        if settings.auth_mode is AuthMode.LOCAL:
            return FileResponse(login_html)
        if oidc is None:
            raise RuntimeError("Keycloak authentication requires an OIDC client")
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = _base64url(hashlib.sha256(verifier.encode()).digest())
        location = await oidc.authorization_url(state, nonce, challenge)
        response = RedirectResponse(location, status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            OIDC_TRANSACTION_COOKIE,
            _encode_signed({"state": state, "nonce": nonce, "verifier": verifier}, settings),
            max_age=600,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite="lax",
        )
        return response

    @router.post("/auth/login", include_in_schema=False)
    async def login(request: LoginRequest) -> JSONResponse:
        if settings.auth_mode is AuthMode.DISABLED:
            return JSONResponse({"status": "disabled"})
        if settings.auth_mode is not AuthMode.LOCAL:
            return JSONResponse(
                {"detail": "password login is not available"},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if not _credentials_match(request, settings):
            return JSONResponse(
                {"detail": "invalid username or password"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        principal = Principal(
            f"local:{request.username}", request.username, ("viewer", "operator"), "local"
        )
        response = JSONResponse({"status": "authenticated"})
        _set_session_cookie(response, principal, settings)
        return response

    @router.get("/auth/callback", include_in_schema=False)
    async def callback(
        code: str = Query(min_length=1),
        state: str = Query(min_length=1),
        transaction_cookie: str | None = Cookie(default=None, alias=OIDC_TRANSACTION_COOKIE),
    ) -> Response:
        if settings.auth_mode is not AuthMode.KEYCLOAK or oidc is None:
            return JSONResponse({"detail": "not found"}, status_code=status.HTTP_404_NOT_FOUND)
        transaction = _decode_signed(transaction_cookie, settings, max_age=600)
        if transaction is None or not hmac.compare_digest(str(transaction.get("state", "")), state):
            return JSONResponse(
                {"detail": "invalid authentication transaction"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            tokens = await oidc.exchange_code(code, str(transaction["verifier"]))
            claims = await oidc.verify_id_token(str(tokens["id_token"]), str(transaction["nonce"]))
            principal = _principal_from_claims(claims, settings, "oidc_session")
        except KeyError, OidcError:
            return JSONResponse(
                {"detail": "identity provider authentication failed"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        if not _has_role(principal, "viewer", settings):
            return JSONResponse(
                {"detail": "insufficient permissions"},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(OIDC_TRANSACTION_COOKIE)
        _set_session_cookie(response, principal, settings)
        return response

    @router.post("/auth/logout", include_in_schema=False)
    async def logout() -> JSONResponse:
        logout_url = "/login"
        if settings.auth_mode is AuthMode.KEYCLOAK and oidc is not None:
            public_url = settings.public_url
            if public_url is None:
                raise RuntimeError("Keycloak settings were not validated")
            logout_url = await oidc.logout_url(f"{str(public_url).rstrip('/')}/login")
        response = JSONResponse({"status": "logged_out", "logout_url": logout_url})
        response.delete_cookie(
            SESSION_COOKIE,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite="lax",
        )
        return response

    return router


def _credentials_match(request: LoginRequest, settings: Settings) -> bool:
    if settings.auth_username is None or settings.auth_password is None:
        raise RuntimeError("authentication settings were not validated")
    return hmac.compare_digest(request.username, settings.auth_username) and hmac.compare_digest(
        request.password.encode(), settings.auth_password.get_secret_value().encode()
    )


def _set_session_cookie(response: Response, principal: Principal, settings: Settings) -> None:
    max_age = settings.auth_session_ttl_seconds
    if principal.expires_at is not None:
        max_age = min(max_age, max(0, principal.expires_at - int(time.time())))
    response.set_cookie(
        SESSION_COOKIE,
        _encode_signed(asdict(principal), settings),
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )


def _decode_session(value: str, settings: Settings) -> Principal | None:
    payload = _decode_signed(value, settings, max_age=settings.auth_session_ttl_seconds)
    if payload is None:
        return None
    try:
        roles = payload["roles"]
        if not isinstance(roles, list):
            return None
        return Principal(
            subject=str(payload["subject"]),
            username=str(payload["username"]) if payload.get("username") is not None else None,
            roles=tuple(role for role in roles if isinstance(role, str)),
            method=str(payload["method"]),
            expires_at=_optional_int(payload.get("expires_at")),
        )
    except KeyError, TypeError, ValueError:
        return None


def _encode_signed(payload: dict[str, object], settings: Settings) -> str:
    body = {"iat": int(time.time()), **payload}
    encoded = _base64url(json.dumps(body, separators=(",", ":"), sort_keys=True).encode())
    return f"{encoded}.{_signature(encoded, settings)}"


def _decode_signed(
    value: str | None, settings: Settings, *, max_age: int
) -> dict[str, object] | None:
    if value is None:
        return None
    encoded, separator, signature = value.partition(".")
    if not separator or not hmac.compare_digest(signature, _signature(encoded, settings)):
        return None
    try:
        payload = json.loads(_base64url_decode(encoded))
        issued_at = int(payload["iat"])
    except KeyError, TypeError, ValueError, json.JSONDecodeError:
        return None
    age = int(time.time()) - issued_at
    if not isinstance(payload, dict) or not 0 <= age <= max_age:
        return None
    try:
        expires_at = _optional_int(payload.get("expires_at"))
        if expires_at is not None and int(time.time()) > expires_at:
            return None
    except ValueError:
        return None
    return payload


def _principal_from_claims(claims: dict[str, object], settings: Settings, method: str) -> Principal:
    client_id = settings.oidc_client_id
    if client_id is None:
        raise RuntimeError("Keycloak settings were not validated")
    username_value = claims.get("preferred_username")
    return Principal(
        subject=str(claims["sub"]),
        username=str(username_value) if username_value is not None else None,
        roles=tuple(sorted(token_roles(claims, client_id))),
        method=method,
        expires_at=_optional_int(claims.get("exp")),
    )


def _required_role(scope: Scope) -> str | None:
    if not scope["path"].startswith("/v1/"):
        return "viewer"
    return "operator" if scope["method"] in {"POST", "PUT", "PATCH", "DELETE"} else "viewer"


def _has_role(principal: Principal, role: str, settings: Settings) -> bool:
    if principal.method in {"disabled", "local", "api_token"}:
        return True
    viewer = settings.oidc_viewer_role
    operator = settings.oidc_operator_role
    if role == "operator":
        return operator in principal.roles
    return bool({viewer, operator} & set(principal.roles))


def _valid_static_bearer_token(authorization: str, settings: Settings) -> bool:
    configured_token = settings.auth_api_token
    token = _bearer_value(authorization)
    if configured_token is None or token is None:
        return False
    expected = configured_token.get_secret_value()
    return bool(expected) and hmac.compare_digest(token.encode(), expected.encode())


def _bearer_value(authorization: str) -> str | None:
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.casefold() != "bearer" or not token:
        return None
    return token


def _signature(payload: str, settings: Settings) -> str:
    if settings.auth_session_secret is None:
        raise RuntimeError("authentication settings were not validated")
    return hmac.new(
        settings.auth_session_secret.get_secret_value().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("expected an integer")
    return value


def _cookie_value(header: str, name: str) -> str | None:
    for item in header.split(";"):
        key, separator, value = item.strip().partition("=")
        if separator and key == name:
            return value
    return None

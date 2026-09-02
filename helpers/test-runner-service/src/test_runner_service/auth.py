import hashlib
import hmac
import time
from pathlib import Path
from typing import Final

from fastapi import APIRouter, Response, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from starlette.types import ASGIApp, Receive, Scope, Send

from test_runner_service.settings import Settings

SESSION_COOKIE: Final = "test_runner_session"
_PUBLIC_PATHS: Final = frozenset(
    {"/health", "/login", "/auth/status", "/auth/login", "/auth/logout"}
)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthenticationMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self._app = app
        self._settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._is_allowed(scope):
            await self._app(scope, receive, send)
            return

        response: Response
        if scope["path"] == "/":
            response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
        else:
            response = JSONResponse(
                {"detail": "authentication required"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        await response(scope, receive, send)

    def _is_allowed(self, scope: Scope) -> bool:
        if not self._settings.auth_enabled or scope["path"] in _PUBLIC_PATHS:
            return True
        headers = dict(scope["headers"])
        cookie = _cookie_value(headers.get(b"cookie", b"").decode("latin-1"), SESSION_COOKIE)
        return cookie is not None and _valid_session(cookie, self._settings)


def create_auth_router(settings: Settings, login_html: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/auth/status", include_in_schema=False)
    async def auth_status() -> dict[str, bool]:
        return {"enabled": settings.auth_enabled}

    @router.get("/login", response_class=FileResponse, include_in_schema=False)
    async def login_page() -> Response:
        if not settings.auth_enabled:
            return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
        return FileResponse(login_html)

    @router.post("/auth/login", include_in_schema=False)
    async def login(request: LoginRequest) -> JSONResponse:
        if not settings.auth_enabled:
            return JSONResponse({"status": "disabled"})
        if not _credentials_match(request, settings):
            return JSONResponse(
                {"detail": "invalid username or password"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        response = JSONResponse({"status": "authenticated"})
        response.set_cookie(
            SESSION_COOKIE,
            _new_session(settings),
            max_age=settings.auth_session_ttl_seconds,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite="strict",
        )
        return response

    @router.post("/auth/logout", include_in_schema=False)
    async def logout() -> JSONResponse:
        response = JSONResponse({"status": "logged_out"})
        response.delete_cookie(
            SESSION_COOKIE,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite="strict",
        )
        return response

    return router


def _credentials_match(request: LoginRequest, settings: Settings) -> bool:
    if settings.auth_username is None or settings.auth_password is None:
        raise RuntimeError("authentication settings were not validated")
    username_matches = hmac.compare_digest(request.username, settings.auth_username)
    password_matches = hmac.compare_digest(
        request.password.encode(), settings.auth_password.get_secret_value().encode()
    )
    return username_matches and password_matches


def _new_session(settings: Settings) -> str:
    issued_at = str(int(time.time()))
    return f"{issued_at}.{_signature(issued_at, settings)}"


def _valid_session(token: str, settings: Settings) -> bool:
    try:
        issued_at_text, signature = token.split(".", maxsplit=1)
        issued_at = int(issued_at_text)
    except ValueError:
        return False
    age = int(time.time()) - issued_at
    return 0 <= age <= settings.auth_session_ttl_seconds and hmac.compare_digest(
        signature, _signature(issued_at_text, settings)
    )


def _signature(payload: str, settings: Settings) -> str:
    if settings.auth_session_secret is None:
        raise RuntimeError("authentication settings were not validated")
    return hmac.new(
        settings.auth_session_secret.get_secret_value().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def _cookie_value(header: str, name: str) -> str | None:
    for item in header.split(";"):
        key, separator, value = item.strip().partition("=")
        if separator and key == name:
            return value
    return None

import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from test_runner_service.main import create_app
from test_runner_service.oidc import OidcClient, OidcError
from test_runner_service.settings import AuthMode, Settings
from tests.fakes import FakeProcessRunner


def test_authentication_can_be_disabled(settings: Settings) -> None:
    with TestClient(create_app(settings, FakeProcessRunner())) as client:
        response = client.get("/")
        auth_status = client.get("/auth/status")

    assert response.status_code == 200
    assert 'id="logout" type="button" hidden' in response.text
    assert auth_status.json() == {"enabled": False, "mode": "disabled"}


def test_authentication_requires_complete_configuration(settings: Settings) -> None:
    values = settings.model_dump()
    values["auth_mode"] = AuthMode.LOCAL
    with pytest.raises(ValidationError, match="TEST_RUNNER_AUTH_PASSWORD"):
        Settings.model_validate(values)


def test_authentication_rejects_invalid_credentials(settings: Settings) -> None:
    protected_settings = _protected_settings(settings)
    with TestClient(create_app(protected_settings, FakeProcessRunner())) as client:
        index = client.get("/", follow_redirects=False)
        login_page = client.get("/login")
        rejected = client.post(
            "/auth/login",
            json={"username": "operator", "password": "wrong"},
        )
        api = client.get("/v1/current")

    assert index.status_code == 303
    assert index.headers["location"] == "/login"
    assert login_page.status_code == 200
    assert "Sign in" in login_page.text
    assert rejected.status_code == 401
    assert api.status_code == 401


def test_signed_cookie_authenticates_subsequent_requests(settings: Settings) -> None:
    protected_settings = _protected_settings(settings)
    with TestClient(create_app(protected_settings, FakeProcessRunner())) as client:
        authenticated = client.post(
            "/auth/login",
            json={"username": "operator", "password": "secret-password"},
        )
        index = client.get("/")
        api = client.get("/v1/current")
        logged_out = client.post("/auth/logout")
        rejected = client.get("/v1/current")

    cookie = authenticated.cookies.get("test_runner_session")
    assert authenticated.status_code == 200
    assert cookie is not None
    assert "secret-password" not in cookie
    assert index.status_code == 200
    assert api.status_code == 200
    assert logged_out.json() == {"status": "logged_out", "logout_url": "/login"}
    assert rejected.status_code == 401


def test_bearer_token_authenticates_api_request(settings: Settings) -> None:
    protected_settings = _protected_settings(settings, api_token="ci-api-token")  # noqa: S106
    with TestClient(create_app(protected_settings, FakeProcessRunner())) as client:
        response = client.get(
            "/v1/current",
            headers={"Authorization": "Bearer ci-api-token"},
        )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer wrong-token",
        "Basic ci-api-token",
        "Bearer",
        "",
    ],
)
def test_bearer_token_rejects_invalid_authorization(
    settings: Settings,
    authorization: str,
) -> None:
    protected_settings = _protected_settings(settings, api_token="ci-api-token")  # noqa: S106
    headers = {"Authorization": authorization} if authorization else {}
    with TestClient(create_app(protected_settings, FakeProcessRunner())) as client:
        response = client.get("/v1/current", headers=headers)

    assert response.status_code == 401


def test_empty_bearer_token_setting_does_not_authenticate(settings: Settings) -> None:
    protected_settings = _protected_settings(settings, api_token="")
    with TestClient(create_app(protected_settings, FakeProcessRunner())) as client:
        response = client.get(
            "/v1/current",
            headers={"Authorization": "Bearer anything"},
        )

    assert response.status_code == 401


def test_health_remains_public_when_authentication_is_enabled(settings: Settings) -> None:
    protected_settings = _protected_settings(settings, api_token="ci-api-token")  # noqa: S106
    with TestClient(create_app(protected_settings, FakeProcessRunner())) as client:
        response = client.get("/health")
        auth_status = client.get("/auth/status")

    assert response.status_code == 200
    assert auth_status.json() == {"enabled": True, "mode": "local"}


def test_keycloak_configuration_requires_all_values_and_rejects_static_token(
    settings: Settings,
) -> None:
    values = settings.model_dump()
    values["auth_mode"] = AuthMode.KEYCLOAK
    with pytest.raises(ValidationError, match="TEST_RUNNER_PUBLIC_URL"):
        Settings.model_validate(values)

    values.update(_keycloak_values())
    values["auth_api_token"] = "legacy-token"  # noqa: S105
    with pytest.raises(ValidationError, match="only supported by local"):
        Settings.model_validate(values)


def test_keycloak_browser_flow_creates_session(settings: Settings) -> None:
    keycloak_settings = _keycloak_settings(settings)
    oidc = FakeOidcClient(role=keycloak_settings.oidc_viewer_role)
    with TestClient(create_app(keycloak_settings, FakeProcessRunner(), oidc)) as client:
        login = client.get("/login", follow_redirects=False)
        state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
        callback = client.get(
            "/auth/callback",
            params={"code": "authorization-code", "state": state},
            follow_redirects=False,
        )
        index = client.get("/")

    assert login.status_code == 303
    assert login.cookies.get("test_runner_oidc_transaction") is not None
    assert callback.status_code == 303
    assert callback.headers["location"] == "/"
    assert callback.cookies.get("test_runner_session") is not None
    assert index.status_code == 200


def test_keycloak_bearer_enforces_viewer_and_operator_roles(settings: Settings) -> None:
    keycloak_settings = _keycloak_settings(settings)
    viewer = FakeOidcClient(role=keycloak_settings.oidc_viewer_role)
    with TestClient(create_app(keycloak_settings, FakeProcessRunner(), viewer)) as client:
        readable = client.get("/v1/current", headers={"Authorization": "Bearer valid"})
        forbidden = client.post("/v1/current/cancel", headers={"Authorization": "Bearer valid"})

    operator = FakeOidcClient(role=keycloak_settings.oidc_operator_role)
    with TestClient(create_app(keycloak_settings, FakeProcessRunner(), operator)) as client:
        authorized = client.post("/v1/current/cancel", headers={"Authorization": "Bearer valid"})

    assert readable.status_code == 200
    assert forbidden.status_code == 403
    assert authorized.status_code == 409


def test_keycloak_rejects_invalid_bearer(settings: Settings) -> None:
    keycloak_settings = _keycloak_settings(settings)
    oidc = FakeOidcClient(role=keycloak_settings.oidc_viewer_role, reject_token=True)
    with TestClient(create_app(keycloak_settings, FakeProcessRunner(), oidc)) as client:
        response = client.get("/v1/current", headers={"Authorization": "Bearer invalid"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def _protected_settings(settings: Settings, api_token: str | None = None) -> Settings:
    values = settings.model_dump()
    values.update(
        auth_mode=AuthMode.LOCAL,
        auth_username="operator",
        auth_password="secret-password",  # noqa: S106
        auth_session_secret="long-random-session-secret",  # noqa: S106
        auth_api_token=api_token,
    )
    return Settings.model_validate(values)


def _keycloak_settings(settings: Settings) -> Settings:
    values = settings.model_dump()
    values.update(_keycloak_values())
    return Settings.model_validate(values)


def _keycloak_values() -> dict[str, object]:
    return {
        "auth_mode": AuthMode.KEYCLOAK,
        "public_url": "https://runner.example",
        "oidc_issuer": "https://sso.example/realms/engineering",
        "oidc_client_id": "hardware-test-runner",
        "oidc_client_secret": "client-secret",
        "oidc_audience": "hardware-test-runner",
        "auth_session_secret": "long-random-session-secret",
        "auth_cookie_secure": False,
    }


class FakeOidcClient(OidcClient):
    def __init__(self, role: str, *, reject_token: bool = False) -> None:
        self._role = role
        self._reject_token = reject_token

    async def authorization_url(self, state: str, nonce: str, challenge: str) -> str:
        del nonce, challenge
        return f"https://sso.example/authorize?state={state}"

    async def exchange_code(self, code: str, verifier: str) -> dict[str, Any]:
        assert code == "authorization-code"
        assert verifier
        return {"id_token": "fake-id-token"}

    async def verify_id_token(self, token: str, nonce: str) -> dict[str, Any]:
        assert token == "fake-id-token"  # noqa: S105
        assert nonce
        return self._claims()

    async def verify_access_token(self, token: str) -> dict[str, Any]:
        if self._reject_token or token != "valid":  # noqa: S105
            raise OidcError("invalid token")
        return self._claims()

    async def logout_url(self, post_logout_redirect_uri: str) -> str:
        return f"https://sso.example/logout?return={post_logout_redirect_uri}"

    def _claims(self) -> dict[str, Any]:
        return {
            "sub": "user-1",
            "exp": int(time.time()) + 300,
            "preferred_username": "operator",
            "resource_access": {"hardware-test-runner": {"roles": [self._role]}},
        }

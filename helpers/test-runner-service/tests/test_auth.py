import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from test_runner_service.main import create_app
from test_runner_service.settings import Settings
from tests.fakes import FakeProcessRunner


def test_authentication_can_be_disabled(settings: Settings) -> None:
    with TestClient(create_app(settings, FakeProcessRunner())) as client:
        response = client.get("/")
        auth_status = client.get("/auth/status")

    assert response.status_code == 200
    assert 'id="logout" type="button" hidden' in response.text
    assert auth_status.json() == {"enabled": False}


def test_authentication_requires_complete_configuration(settings: Settings) -> None:
    values = settings.model_dump()
    values["auth_enabled"] = True
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
    assert logged_out.status_code == 200
    assert rejected.status_code == 401


def test_health_remains_public_when_authentication_is_enabled(settings: Settings) -> None:
    with TestClient(create_app(_protected_settings(settings), FakeProcessRunner())) as client:
        response = client.get("/health")
        auth_status = client.get("/auth/status")

    assert response.status_code == 200
    assert auth_status.json() == {"enabled": True}


def _protected_settings(settings: Settings) -> Settings:
    values = settings.model_dump()
    values.update(
        auth_enabled=True,
        auth_username="operator",
        auth_password="secret-password",  # noqa: S106
        auth_session_secret="long-random-session-secret",  # noqa: S106
    )
    return Settings.model_validate(values)

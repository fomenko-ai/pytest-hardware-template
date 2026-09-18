import asyncio
import time
from collections.abc import Mapping
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from pydantic import SecretStr

from test_runner_service.oidc import OidcClient, OidcError, token_roles
from test_runner_service.settings import AuthMode, Settings


def test_access_token_is_verified_with_cached_discovery_and_jwks() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk.update({"kid": "signing-key", "alg": "RS256", "use": "sig"})
    http = FakeJsonHttpClient(jwk)
    client = OidcClient(_settings(), http)
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "ci-client",
            "iss": "https://sso.example/realms/engineering",
            "aud": "hardware-test-runner",
            "iat": now,
            "exp": now + 300,
            "resource_access": {
                "hardware-test-runner": {"roles": ["hardware-test-runner.operator"]}
            },
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "signing-key"},
    )

    first = asyncio.run(client.verify_access_token(token))
    second = asyncio.run(client.verify_access_token(token))

    assert first["sub"] == "ci-client"
    assert second["sub"] == "ci-client"
    assert http.discovery_requests == 1
    assert http.jwks_requests == 1


def test_access_token_rejects_wrong_audience() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk.update({"kid": "signing-key", "alg": "RS256", "use": "sig"})
    client = OidcClient(_settings(), FakeJsonHttpClient(jwk))
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "ci-client",
            "iss": "https://sso.example/realms/engineering",
            "aud": "another-service",
            "iat": now,
            "exp": now + 300,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "signing-key"},
    )

    with pytest.raises(OidcError, match="token is invalid"):
        asyncio.run(client.verify_access_token(token))


def test_token_roles_combines_realm_and_runner_client_roles() -> None:
    roles = token_roles(
        {
            "realm_access": {"roles": ["realm-viewer", 1]},
            "resource_access": {
                "hardware-test-runner": {"roles": ["runner-operator"]},
                "another-client": {"roles": ["ignored"]},
            },
        },
        "hardware-test-runner",
    )

    assert roles == frozenset({"realm-viewer", "runner-operator"})


class FakeJsonHttpClient:
    def __init__(self, jwk: dict[str, Any]) -> None:
        self._jwk = jwk
        self.discovery_requests = 0
        self.jwks_requests = 0

    async def get_json(self, url: str) -> dict[str, Any]:
        if url.endswith("/.well-known/openid-configuration"):
            self.discovery_requests += 1
            return {
                "issuer": "https://sso.example/realms/engineering",
                "authorization_endpoint": "https://sso.example/authorize",
                "token_endpoint": "https://sso.example/token",
                "jwks_uri": "https://sso.example/certs",
                "end_session_endpoint": "https://sso.example/logout",
            }
        assert url == "https://sso.example/certs"
        self.jwks_requests += 1
        return {"keys": [self._jwk]}

    async def post_form(self, url: str, data: Mapping[str, str]) -> dict[str, Any]:
        del url, data
        return {"id_token": "unused"}


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        auth_mode=AuthMode.KEYCLOAK,
        public_url="https://runner.example",
        oidc_issuer="https://sso.example/realms/engineering",
        oidc_client_id="hardware-test-runner",
        oidc_client_secret=SecretStr("client-secret"),
        oidc_audience="hardware-test-runner",
        auth_session_secret=SecretStr("session-secret"),
    )

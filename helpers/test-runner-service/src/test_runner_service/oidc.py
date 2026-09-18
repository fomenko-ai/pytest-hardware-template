import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import jwt

from test_runner_service.settings import Settings


class OidcError(Exception):
    """A safe, user-facing OIDC failure without tokens or provider response bodies."""


class JsonHttpClient(Protocol):
    async def get_json(self, url: str) -> dict[str, Any]: ...

    async def post_form(self, url: str, data: Mapping[str, str]) -> dict[str, Any]: ...


class UrlLibJsonHttpClient:
    async def get_json(self, url: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, url, None)

    async def post_form(self, url: str, data: Mapping[str, str]) -> dict[str, Any]:
        body = urllib.parse.urlencode(data).encode()
        return await asyncio.to_thread(self._request, url, body)

    @staticmethod
    def _request(url: str, body: bytes | None) -> dict[str, Any]:
        request = urllib.request.Request(url, data=body)  # noqa: S310 - validated HTTPS URL.
        if body is not None:
            request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                value = json.load(response)
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise OidcError("the identity provider is unavailable") from error
        if not isinstance(value, dict):
            raise OidcError("the identity provider returned an invalid response")
        return value


@dataclass(frozen=True)
class OidcEndpoints:
    authorization: str
    token: str
    jwks: str
    end_session: str | None


class OidcClient:
    def __init__(self, settings: Settings, http: JsonHttpClient | None = None) -> None:
        self._settings = settings
        self._http = http or UrlLibJsonHttpClient()
        self._endpoints: OidcEndpoints | None = None
        self._jwks: dict[str, Any] | None = None
        self._jwks_loaded_at = 0.0

    async def authorization_url(self, state: str, nonce: str, challenge: str) -> str:
        endpoints = await self._get_endpoints()
        return f"{endpoints.authorization}?{
            urllib.parse.urlencode(
                {
                    'client_id': self._client_id,
                    'redirect_uri': self._redirect_uri,
                    'response_type': 'code',
                    'scope': 'openid profile',
                    'state': state,
                    'nonce': nonce,
                    'code_challenge': challenge,
                    'code_challenge_method': 'S256',
                }
            )
        }"

    async def exchange_code(self, code: str, verifier: str) -> dict[str, Any]:
        endpoints = await self._get_endpoints()
        secret = self._settings.oidc_client_secret
        if secret is None:
            raise OidcError("OIDC settings were not validated")
        response = await self._http.post_form(
            endpoints.token,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._redirect_uri,
                "client_id": self._client_id,
                "client_secret": secret.get_secret_value(),
                "code_verifier": verifier,
            },
        )
        if not isinstance(response.get("id_token"), str):
            raise OidcError("the identity provider did not return an ID token")
        return response

    async def verify_id_token(self, token: str, nonce: str) -> dict[str, Any]:
        claims = await self._verify(token, self._client_id)
        if claims.get("nonce") != nonce:
            raise OidcError("the ID token nonce is invalid")
        return claims

    async def verify_access_token(self, token: str) -> dict[str, Any]:
        audience = self._settings.oidc_audience
        if audience is None:
            raise OidcError("OIDC settings were not validated")
        return await self._verify(token, audience)

    async def logout_url(self, post_logout_redirect_uri: str) -> str:
        endpoint = (await self._get_endpoints()).end_session
        if endpoint is None:
            return post_logout_redirect_uri
        return f"{endpoint}?{
            urllib.parse.urlencode(
                {
                    'client_id': self._client_id,
                    'post_logout_redirect_uri': post_logout_redirect_uri,
                }
            )
        }"

    async def _verify(self, token: str, audience: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise OidcError("the token header is invalid")
            key = await self._key(header["kid"])
            return jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=audience,
                issuer=self._issuer,
                leeway=self._settings.oidc_clock_skew_seconds,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except OidcError:
            raise
        except jwt.PyJWTError as error:
            raise OidcError("the token is invalid") from error

    async def _key(self, kid: str) -> jwt.PyJWK:
        jwks = await self._get_jwks()
        key = _find_key(jwks, kid)
        if key is None:
            jwks = await self._get_jwks(force=True)
            key = _find_key(jwks, kid)
        if key is None:
            raise OidcError("the token signing key is unknown")
        try:
            return jwt.PyJWK.from_dict(key, algorithm="RS256")
        except jwt.PyJWTError as error:
            raise OidcError("the token signing key is invalid") from error

    async def _get_endpoints(self) -> OidcEndpoints:
        if self._endpoints is None:
            document = await self._http.get_json(f"{self._issuer}/.well-known/openid-configuration")
            issuer = document.get("issuer")
            if issuer != self._issuer:
                raise OidcError("the discovery issuer does not match the configured issuer")
            self._endpoints = OidcEndpoints(
                authorization=_required_url(document, "authorization_endpoint"),
                token=_required_url(document, "token_endpoint"),
                jwks=_required_url(document, "jwks_uri"),
                end_session=_optional_url(document, "end_session_endpoint"),
            )
        return self._endpoints

    async def _get_jwks(self, *, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if (
            force
            or self._jwks is None
            or now - self._jwks_loaded_at >= self._settings.oidc_jwks_cache_seconds
        ):
            self._jwks = await self._http.get_json((await self._get_endpoints()).jwks)
            self._jwks_loaded_at = now
        return self._jwks

    @property
    def _issuer(self) -> str:
        issuer = self._settings.oidc_issuer
        if issuer is None:
            raise OidcError("OIDC settings were not validated")
        return str(issuer).rstrip("/")

    @property
    def _client_id(self) -> str:
        client_id = self._settings.oidc_client_id
        if client_id is None:
            raise OidcError("OIDC settings were not validated")
        return client_id

    @property
    def _redirect_uri(self) -> str:
        public_url = self._settings.public_url
        if public_url is None:
            raise OidcError("OIDC settings were not validated")
        return f"{str(public_url).rstrip('/')}/auth/callback"


def token_roles(claims: Mapping[str, Any], client_id: str) -> frozenset[str]:
    roles: set[str] = set()
    realm_access = claims.get("realm_access")
    if isinstance(realm_access, dict):
        roles.update(_string_items(realm_access.get("roles")))
    resource_access = claims.get("resource_access")
    if isinstance(resource_access, dict):
        client_access = resource_access.get(client_id)
        if isinstance(client_access, dict):
            roles.update(_string_items(client_access.get("roles")))
    return frozenset(roles)


def _find_key(jwks: Mapping[str, Any], kid: str) -> dict[str, Any] | None:
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        return None
    return next(
        (key for key in keys if isinstance(key, dict) and key.get("kid") == kid),
        None,
    )


def _string_items(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _required_url(document: Mapping[str, Any], name: str) -> str:
    value = _optional_url(document, name)
    if value is None:
        raise OidcError(f"OIDC discovery is missing {name}")
    return value


def _optional_url(document: Mapping[str, Any], name: str) -> str | None:
    value = document.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.startswith("https://"):
        raise OidcError(f"OIDC discovery contains an invalid {name}")
    return value

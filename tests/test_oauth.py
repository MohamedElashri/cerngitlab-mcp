"""Tests for the CERN SSO + OAuth implementation."""

import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit
import base64
import hashlib
import json
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from cerngitlab_mcp.config import Settings
from cerngitlab_mcp.transports.http import HttpTransport
from cerngitlab_mcp.auth.session_store import SessionStore
from cerngitlab_mcp.auth.oauth import OAuthService
from cerngitlab_mcp.exceptions import AuthenticationError


@pytest.fixture
def test_settings(tmp_path):
    """Provide test settings with a temporary session storage path."""
    return Settings(
        gitlab_url="https://gitlab.cern.ch",
        cern_client_id="test-client-id",
        gitlab_oauth_client_id="test-gitlab-client-id",
        gitlab_oauth_client_secret="test-gitlab-secret",
        server_base_url="http://localhost:8000",
        session_storage_path=str(tmp_path / "sessions"),
        log_level="DEBUG",
    )


@pytest.mark.asyncio
async def test_oauth_implementation(test_settings):
    """Test the OAuth implementation with minimal configuration."""
    # Create transport
    transport = HttpTransport(test_settings)

    # Test OAuth service initialization
    assert transport.oauth_service is not None

    # Test session store
    assert transport.session_store is not None

    # Test session storage directory creation
    session_path = Path(test_settings.session_storage_path)
    assert session_path.exists()

    # Test FastAPI app creation
    app = transport.app
    assert app is not None

    # Check routes
    routes = [route.path for route in app.routes]
    expected_routes = [
        "/",
        "/health",
        "/oauth/authorize",
        "/oauth/callback",
        "/tools",
        "/tools/{tool_name}",
        "/session",
        "/admin/sessions",
    ]

    for expected_route in expected_routes:
        assert any(expected_route in route for route in routes), (
            f"Missing route {expected_route}"
        )


@pytest.mark.asyncio
async def test_session_store(test_settings):
    """Test session store functionality."""
    store = SessionStore(test_settings)

    # Test storing a session
    await store.store_session("test_user", "test_oauth_token")

    # Test retrieving a session
    token = await store.get_session("test_user")
    assert token == "test_oauth_token"

    # Test listing sessions
    sessions = await store.list_active_sessions()
    assert len(sessions) > 0
    assert sessions[0]["username"] == "test_user"

    # Test session cleanup
    await store.revoke_session("test_user")
    token = await store.get_session("test_user")
    assert token is None


@pytest.mark.asyncio
async def test_oauth_pkce_and_single_use_state(test_settings, httpx_mock):
    service = OAuthService(test_settings)
    url = await service._generate_oauth_url("alice")
    params = parse_qs(urlsplit(url).query)
    state = params["state"][0]
    assert service._validate_state(state) == "alice"
    assert service._validate_state(state + "tampered") is None
    assert params["redirect_uri"] == ["http://localhost:8000/oauth/callback"]
    assert params["code_challenge_method"] == ["S256"]
    verifier = service._pending_states[state][2]
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert params["code_challenge"] == [expected]
    httpx_mock.add_response(
        method="POST",
        url="https://gitlab.cern.ch/oauth/token",
        json={"access_token": "gitlab-token"},
    )
    assert await service.exchange_oauth_code("code", state) == ("alice", "gitlab-token")
    assert parse_qs(httpx_mock.get_request().content.decode())["code_verifier"] == [
        verifier
    ]
    with pytest.raises(AuthenticationError, match="Invalid OAuth state"):
        await service.exchange_oauth_code("code", state)


def test_oauth_state_expires_and_forged_states_are_rejected(test_settings):
    service = OAuthService(test_settings)
    state = service._generate_secure_state("alice")
    service._pending_states[state] = (
        "alice",
        datetime.now(timezone.utc) - timedelta(seconds=1),
        "verifier",
    )
    assert service._validate_state(state) is None
    assert state not in service._pending_states
    forged = base64.urlsafe_b64encode(b"alice:9999999999:forged").decode()
    assert service._validate_state(forged) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("rotated", [False, True])
async def test_cern_jwt_uses_matching_signing_key(test_settings, rotated):
    service = OAuthService(test_settings)
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def jwk(key, kid):
        return {
            **json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())),
            "kid": kid,
        }

    keys = {"keys": [jwk(wrong_key, "old"), jwk(signing_key, "current")]}
    service._get_cern_jwks = AsyncMock(
        side_effect=[{"keys": [keys["keys"][0]]}, keys] if rotated else [keys]
    )
    token = jwt.encode(
        {
            "preferred_username": "alice",
            "iss": service.cern_auth_url,
            "aud": test_settings.cern_client_id,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        signing_key,
        algorithm="RS256",
        headers={"kid": "current"},
    )
    assert (await service._validate_cern_token(token))["preferred_username"] == "alice"
    assert service._get_cern_jwks.await_count == (2 if rotated else 1)

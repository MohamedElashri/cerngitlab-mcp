"""Tests for the CERN SSO + OAuth implementation."""

import pytest
from pathlib import Path

from cerngitlab_mcp.config import Settings
from cerngitlab_mcp.transports.http import HttpTransport
from cerngitlab_mcp.auth.session_store import SessionStore


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
        assert any(
            expected_route in route for route in routes
        ), f"Missing route {expected_route}"


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

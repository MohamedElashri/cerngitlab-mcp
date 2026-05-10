"""Unit tests for transport layer classes."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cerngitlab_mcp.config import Settings
from cerngitlab_mcp.core import McpServerCore
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.transports.stdio import StdioTransport
from cerngitlab_mcp.transports.http import UserSession


class TestStdioTransport:
    """Test cases for StdioTransport class."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            gitlab_url="https://gitlab.example.com",
            token="test-token",
            timeout=5.0,
            max_retries=1,
            rate_limit_per_minute=1000,
        )

    @pytest.fixture
    def stdio_transport(self, settings):
        """Create StdioTransport instance for testing."""
        return StdioTransport(settings)

    def test_initialization(self, stdio_transport, settings):
        """Test that StdioTransport initializes correctly."""
        assert stdio_transport.settings == settings
        assert stdio_transport.gitlab_client is None
        assert stdio_transport.core is None
        assert stdio_transport.server is not None

    def test_get_gitlab_client(self, stdio_transport):
        """Test GitLab client creation."""
        client = stdio_transport._get_gitlab_client()
        assert isinstance(client, GitLabClient)
        assert stdio_transport.gitlab_client is client

        # Second call should return same instance
        client2 = stdio_transport._get_gitlab_client()
        assert client2 is client

    def test_get_core(self, stdio_transport):
        """Test core creation."""
        core = stdio_transport._get_core()
        assert isinstance(core, McpServerCore)
        assert stdio_transport.core is core

        # Second call should return same instance
        core2 = stdio_transport._get_core()
        assert core2 is core

    @pytest.mark.asyncio
    @patch("cerngitlab_mcp.transports.stdio.stdio_server")
    @patch("cerngitlab_mcp.transports.stdio.setup_logging")
    async def test_run(self, mock_setup_logging, mock_stdio_server, stdio_transport):
        """Test stdio transport run method."""
        # Mock the stdio_server context manager
        mock_read_stream = MagicMock()
        mock_write_stream = MagicMock()
        mock_stdio_server.return_value.__aenter__.return_value = (
            mock_read_stream,
            mock_write_stream,
        )

        # Mock the server run method
        stdio_transport.server.run = AsyncMock()

        # Mock GitLab client
        mock_client = AsyncMock()
        mock_client.test_connection.return_value = {
            "status": "connected",
            "version": "16.0.0",
        }
        stdio_transport.gitlab_client = mock_client

        # Mock core
        mock_core = AsyncMock()
        stdio_transport.core = mock_core

        await stdio_transport.run()

        # Verify setup_logging was called
        mock_setup_logging.assert_called_once_with(stdio_transport.settings.log_level)

        # Verify GitLab connectivity check
        mock_client.test_connection.assert_called_once()

        # Verify server.run was called
        stdio_transport.server.run.assert_called_once()

        # Verify cleanup
        mock_core.close.assert_called_once()


class TestUserSession:
    """Test cases for UserSession class."""

    @pytest.fixture
    def base_settings(self):
        """Create base settings."""
        return Settings(
            gitlab_url="https://gitlab.example.com",
            timeout=5.0,
            max_retries=1,
        )

    @pytest.fixture
    def user_session(self, base_settings):
        """Create UserSession instance for testing."""
        return UserSession("test_user", "test-token", base_settings)

    def test_initialization(self, user_session, base_settings):
        """Test that UserSession initializes correctly."""
        assert user_session.user_id == "test_user"
        assert user_session.settings.token == "test-token"
        assert user_session.settings.gitlab_url == base_settings.gitlab_url
        assert isinstance(user_session.gitlab_client, GitLabClient)
        assert isinstance(user_session.core, McpServerCore)

    @pytest.mark.asyncio
    async def test_close(self, user_session):
        """Test session cleanup."""
        user_session.core.close = AsyncMock()
        await user_session.close()
        user_session.core.close.assert_called_once()

"""Unit tests for transport layer classes."""

from unittest.mock import AsyncMock, patch

import pytest

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
        assert isinstance(stdio_transport.gitlab_client, GitLabClient)
        assert stdio_transport.mcp is not None

    @pytest.mark.asyncio
    @patch("cerngitlab_mcp.transports.stdio.setup_logging")
    async def test_run(self, mock_setup_logging, stdio_transport):
        """Test stdio transport run method."""
        # Mock the GitLab connectivity check
        mock_client = AsyncMock()
        mock_client.test_connection.return_value = {
            "status": "connected",
            "version": "16.0.0",
        }
        stdio_transport.gitlab_client = mock_client

        with patch.object(stdio_transport, "mcp") as mock_mcp:
            mock_mcp.run_stdio_async = AsyncMock()
            await stdio_transport.run()

            # Verify setup_logging was called
            mock_setup_logging.assert_called_once_with(
                stdio_transport.settings.log_level
            )

            # Verify GitLab connectivity check
            mock_client.test_connection.assert_called_once()

            # Verify the MCP server was started over stdio
            mock_mcp.run_stdio_async.assert_called_once()

        # Verify cleanup
        mock_client.close.assert_called_once()


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
        assert user_session.mcp is not None
        assert user_session.mcp_asgi is not None

    @pytest.mark.asyncio
    async def test_close(self, user_session):
        """Test session cleanup."""
        user_session.core.close = AsyncMock()
        await user_session.close()
        user_session.core.close.assert_called_once()

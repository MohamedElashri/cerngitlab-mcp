"""Unit tests for McpServerCore class."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from cerngitlab_mcp.core import McpServerCore
from cerngitlab_mcp.config import Settings
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.exceptions import CERNGitLabError


class TestMcpServerCore:
    """Test cases for the McpServerCore class."""

    @pytest.fixture
    def mock_gitlab_client(self):
        """Create a mock GitLab client."""
        client = MagicMock(spec=GitLabClient)
        client.test_connection = AsyncMock()
        client.close = AsyncMock()
        return client

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
    def core(self, settings, mock_gitlab_client):
        """Create McpServerCore instance for testing."""
        return McpServerCore(settings, mock_gitlab_client)

    def test_initialization(self, core, settings, mock_gitlab_client):
        """Test that McpServerCore initializes correctly."""
        assert core.settings == settings
        assert core.gitlab_client == mock_gitlab_client
        assert len(core._tool_handlers) > 0
        assert "test_connectivity" in core._tool_handlers

    def test_get_tool_definitions(self, core):
        """Test that get_tool_definitions returns expected tools."""
        tools = core.get_tool_definitions()

        # Should have at least the test_connectivity tool plus all the imported tools
        assert len(tools) >= 14  # test_connectivity + 13 imported tools

        tool_names = [tool.name for tool in tools]
        expected_tools = [
            "test_connectivity",
            "search_projects",
            "get_project_info",
            "list_project_files",
            "get_file_content",
            "get_project_readme",
            "search_code",
            "search_lhcb_stack",
            "search_issues",
            "get_wiki_pages",
            "inspect_project",
            "list_releases",
            "get_release",
            "list_tags",
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names

    @pytest.mark.asyncio
    async def test_handle_tool_call_test_connectivity_success(
        self, core, mock_gitlab_client
    ):
        """Test successful test_connectivity tool call."""
        mock_gitlab_client.test_connection.return_value = {
            "status": "connected",
            "version": "16.0.0",
            "revision": "abc123",
        }

        result = await core.handle_tool_call("test_connectivity", {})

        assert result["success"] is True
        assert result["data"]["status"] == "connected"
        assert result["data"]["version"] == "16.0.0"
        mock_gitlab_client.test_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_tool_call_test_connectivity_error(
        self, core, mock_gitlab_client
    ):
        """Test test_connectivity tool call with GitLab error."""
        mock_gitlab_client.test_connection.side_effect = CERNGitLabError(
            "Connection failed"
        )

        result = await core.handle_tool_call("test_connectivity", {})

        assert result["success"] is False
        assert "Connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_tool_call_unknown_tool(self, core):
        """Test handling of unknown tool name."""
        result = await core.handle_tool_call("unknown_tool", {})

        assert result["success"] is False
        assert "Unknown tool: unknown_tool" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_tool_call_value_error(self, core, mock_gitlab_client):
        """Test handling of ValueError in tool execution."""
        # Mock a tool handler that raises ValueError
        mock_handler = AsyncMock()
        mock_handler.handle.side_effect = ValueError("Invalid arguments")
        core._tool_handlers["search_projects"] = mock_handler

        result = await core.handle_tool_call("search_projects", {"invalid": "args"})

        assert result["success"] is False
        assert "Invalid arguments" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_tool_call_unexpected_error(self, core, mock_gitlab_client):
        """Test handling of unexpected errors in tool execution."""
        # Mock a tool handler that raises unexpected error
        mock_handler = AsyncMock()
        mock_handler.handle.side_effect = RuntimeError("Unexpected error")
        core._tool_handlers["search_projects"] = mock_handler

        result = await core.handle_tool_call("search_projects", {})

        assert result["success"] is False
        assert "Internal error" in result["error"]

    def test_format_success_response(self, core):
        """Test formatting of successful responses."""
        data = {"test": "data", "number": 42}
        response = core.format_success_response(data)

        assert len(response) == 1
        assert response[0].type == "text"

        # Should be valid JSON
        parsed = json.loads(response[0].text)
        assert parsed == data

    def test_format_error_response(self, core):
        """Test formatting of error responses."""
        error_message = "Test error message"
        response = core.format_error_response(error_message)

        assert len(response) == 1
        assert response[0].type == "text"

        # Should be valid JSON with error field
        parsed = json.loads(response[0].text)
        assert parsed["error"] == error_message

    @pytest.mark.asyncio
    async def test_close(self, core, mock_gitlab_client):
        """Test cleanup of resources."""
        await core.close()
        mock_gitlab_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_with_none_client(self, settings):
        """Test cleanup when gitlab_client is None."""
        core = McpServerCore(settings, None)
        # Should not raise an exception
        await core.close()

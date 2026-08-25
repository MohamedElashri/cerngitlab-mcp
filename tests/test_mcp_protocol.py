"""Integration tests for the MCP protocol surface (mcp SDK v2).

Covers the high-level MCPServer built by ``build_mcp_server``:
tool discovery, tool annotations, structured output, JSON-RPC error
mapping, and the Streamable HTTP endpoint exposed by the HTTP transport.
"""

import httpx
import pytest

from mcp import Client
from mcp.types import ToolAnnotations

from cerngitlab_mcp.core import build_mcp_server


@pytest.fixture
def mcp_server(settings, client):
    """Build an MCPServer with a mocked GitLab client."""
    return build_mcp_server(settings, client)


class TestToolRegistration:
    """Tests for tool registration on the v2 MCPServer."""

    @pytest.mark.asyncio
    async def test_all_tools_registered(self, mcp_server):
        tools = await mcp_server.list_tools()
        names = {t.name for t in tools}
        assert names == {
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
            "list_branches",
            "list_releases",
            "get_release",
            "list_tags",
        }

    @pytest.mark.asyncio
    async def test_tools_have_read_only_annotations(self, mcp_server):
        tools = await mcp_server.list_tools()
        assert tools, "no tools registered"
        for tool in tools:
            assert isinstance(tool.annotations, ToolAnnotations)
            assert tool.annotations.read_only_hint is True

    @pytest.mark.asyncio
    async def test_tools_have_input_and_output_schemas(self, mcp_server):
        tools = await mcp_server.list_tools()
        for tool in tools:
            assert tool.input_schema.get("type") == "object"
            assert tool.output_schema is not None

    @pytest.mark.asyncio
    async def test_required_arguments_reflect_schema(self, mcp_server):
        tools = {t.name: t for t in await mcp_server.list_tools()}
        assert tools["get_project_info"].input_schema["required"] == ["project"]
        assert tools["get_release"].input_schema["required"] == [
            "project",
            "tag_name",
        ]
        # enum params are typed via Literal -> enum in schema
        sort_by = tools["search_projects"].input_schema["properties"]["sort_by"]
        assert set(sort_by["enum"]) == {
            "last_activity_at",
            "name",
            "created_at",
            "updated_at",
            "stars",
        }


class TestInMemoryToolCalls:
    """End-to-end tool calls through the in-memory MCP client."""

    @pytest.mark.asyncio
    async def test_search_projects_round_trip(self, settings, client, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url="https://gitlab.example.com/api/v4/projects?visibility=public&search=root&order_by=last_activity_at&sort=desc&per_page=20",
            json=[
                {
                    "id": 1,
                    "name": "root",
                    "path_with_namespace": "root/root",
                    "description": "CERN ROOT",
                    "web_url": "https://gitlab.example.com/root/root",
                    "default_branch": "master",
                    "topics": ["physics"],
                    "star_count": 5,
                    "forks_count": 2,
                    "last_activity_at": "2026-01-01T00:00:00Z",
                    "created_at": "2020-01-01T00:00:00Z",
                    "visibility": "public",
                }
            ],
        )

        server = build_mcp_server(settings, client)
        async with Client(server) as session:
            result = await session.call_tool("search_projects", {"query": "root"})

        assert not result.is_error
        assert result.structured_content == {
            "result": [
                {
                    "id": 1,
                    "name": "root",
                    "path_with_namespace": "root/root",
                    "description": "CERN ROOT",
                    "web_url": "https://gitlab.example.com/root/root",
                    "default_branch": "master",
                    "topics": ["physics"],
                    "star_count": 5,
                    "forks_count": 2,
                    "last_activity_at": "2026-01-01T00:00:00Z",
                    "created_at": "2020-01-01T00:00:00Z",
                    "visibility": "public",
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_invalid_arguments_surface_as_error_result(self, settings, client):
        server = build_mcp_server(settings, client)
        async with Client(server) as session:
            # per_page=200 violates the schema (le=100)
            result = await session.call_tool(
                "search_projects", {"query": "x", "per_page": 200}
            )
        assert result.is_error

    @pytest.mark.asyncio
    async def test_gitlab_errors_surface_as_jsonrpc_error(
        self, settings, client, httpx_mock
    ):
        httpx_mock.add_response(
            method="GET",
            json={"message": "404 Project Not Found"},
            status_code=404,
        )
        server = build_mcp_server(settings, client)
        async with Client(server) as session:
            with pytest.raises(Exception) as excinfo:
                await session.call_tool(
                    "get_project_info", {"project": "does/not/exist"}
                )
        assert "not found" in str(excinfo.value).lower() or "404" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error_result(self, settings, client):
        server = build_mcp_server(settings, client)
        async with Client(server) as session:
            result = await session.call_tool("nonexistent_tool", {})
        assert result.is_error


class TestMcpHttpEndpoint:
    """Tests for the /mcp Streamable HTTP endpoint of the HTTP transport."""

    @pytest.fixture
    def http_transport_app(self, settings):
        from cerngitlab_mcp.transports.http import HttpTransport

        transport = HttpTransport(settings)
        return transport.app

    @pytest.mark.asyncio
    async def test_mcp_endpoint_requires_auth(self, http_transport_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=http_transport_app),
            base_url="http://test",
        ) as ac:
            response = await ac.post("/mcp", json={"jsonrpc": "2.0", "id": 1})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_rest_metadata_reports_protocol_version(self, http_transport_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=http_transport_app),
            base_url="http://test",
        ) as ac:
            root = await ac.get("/")
            health = await ac.get("/health")
        assert root.json()["protocol_version"] == "2026-07-28"
        assert health.json()["status"] == "healthy"

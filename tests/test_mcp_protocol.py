"""Integration tests for the MCP protocol surface (mcp SDK v2).

Covers the high-level MCPServer built by ``build_mcp_server``:
tool discovery, tool annotations, structured output, actionable tool errors,
and the Streamable HTTP endpoint exposed by the HTTP transport.
"""

import asyncio
import sys
from unittest.mock import AsyncMock

import httpx
import pytest

from mcp import Client, StdioServerParameters
from mcp.types import ToolAnnotations

from cerngitlab_mcp import __version__
from cerngitlab_mcp.core import PROTOCOL_VERSION, SERVER_INSTRUCTIONS, build_mcp_server


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
            assert tool.annotations.destructive_hint is False
            assert tool.annotations.idempotent_hint is True
            assert tool.annotations.open_world_hint is True

    @pytest.mark.asyncio
    async def test_discovery_is_stable_and_cacheable(self, mcp_server):
        async with Client(mcp_server, cache=None) as session:
            first = await session.list_tools()
            second = await session.list_tools()
            assert first.model_dump() == second.model_dump()
            assert first.ttl_ms == 300_000
            assert first.cache_scope == "private"
            assert session.server_info.version == __version__
        assert "CERN GitLab" in SERVER_INSTRUCTIONS[:512]
        assert "untrusted data" in SERVER_INSTRUCTIONS[:512]

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
    async def test_gitlab_errors_surface_as_actionable_tool_results(
        self, settings, client, httpx_mock
    ):
        httpx_mock.add_response(
            method="GET",
            json={"message": "404 Project Not Found"},
            status_code=404,
        )
        server = build_mcp_server(settings, client)
        async with Client(server) as session:
            result = await session.call_tool(
                "get_project_info", {"project": "does/not/exist"}
            )
        assert result.is_error
        assert "not found" in result.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_business_validation_is_visible_to_agent(self, mcp_server):
        async with Client(mcp_server) as session:
            result = await session.call_tool("get_project_info", {"project": " "})
        assert result.is_error
        assert "required" in result.content[0].text

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
        assert "resource_metadata=" in response.headers["www-authenticate"]

    @pytest.mark.asyncio
    async def test_public_resource_metadata(self, http_transport_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=http_transport_app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/.well-known/oauth-protected-resource/mcp")
        assert response.status_code == 200
        assert response.json()["resource"] == "http://localhost:8000/mcp"
        assert response.json()["bearer_methods_supported"] == ["header"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("protocol", [PROTOCOL_VERSION, "2025-11-25"])
    async def test_authenticated_wire_discovery_and_cleanup(
        self, settings, tmp_path, protocol
    ):
        from cerngitlab_mcp.transports.http import HttpTransport

        settings.session_storage_path = str(tmp_path)
        transport = HttpTransport(settings)
        transport.oauth_service.authenticate_user = AsyncMock(
            return_value=("alice", "gitlab-token")
        )
        transport.session_store.store_session = AsyncMock()
        headers = {
            "Authorization": "Bearer cern-token",
            "Accept": "application/json, text/event-stream",
        }
        async with transport.app.router.lifespan_context(transport.app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=transport.app),
                base_url="http://localhost:8000",
            ) as ac:
                if protocol == "2025-11-25":
                    response = await ac.post(
                        "/mcp",
                        headers=headers,
                        json={
                            "jsonrpc": "2.0",
                            "id": 0,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": protocol,
                                "capabilities": {},
                                "clientInfo": {"name": "test", "version": "1"},
                            },
                        },
                    )
                    assert response.status_code == 200, response.text
                    assert (
                        response.json()["result"]["serverInfo"]["version"]
                        == __version__
                    )
                headers["MCP-Protocol-Version"] = protocol
                headers["Mcp-Method"] = "tools/list"
                params = (
                    {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": protocol,
                            "io.modelcontextprotocol/clientCapabilities": {},
                        }
                    }
                    if protocol == PROTOCOL_VERSION
                    else {}
                )
                for request_id in (1, 2):
                    response = await ac.post(
                        "/mcp",
                        headers=headers,
                        json={
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "method": "tools/list",
                            "params": params,
                        },
                    )
                    assert response.status_code == 200, response.text
                    assert "mcp-session-id" not in response.headers
                    result = response.json()["result"]
                    assert len(result["tools"]) == 15
                    if protocol == PROTOCOL_VERSION:
                        assert result["resultType"] == "complete"
                        assert result["ttlMs"] == 300_000
                        assert result["cacheScope"] == "private"
        assert not transport.user_sessions

    @pytest.mark.asyncio
    async def test_authorization_required_is_not_accepted_as_a_protocol_response(
        self, settings, tmp_path
    ):
        from cerngitlab_mcp.exceptions import AuthorizationRequiredError
        from cerngitlab_mcp.transports.http import HttpTransport

        settings.session_storage_path = str(tmp_path)
        transport = HttpTransport(settings)
        transport.oauth_service.authenticate_user = AsyncMock(
            side_effect=AuthorizationRequiredError(
                "alice", "https://gitlab.example.com/oauth/authorize"
            )
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=transport.app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/mcp",
                headers={"Authorization": "Bearer token"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            )
        assert response.status_code == 403
        assert response.json()["error"] == "authorization_required"

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


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_stdio_subprocess_discovery_without_network(mode):
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cerngitlab_mcp.server", "--mode", "stdio"],
        env={"CERNGITLAB_GITLAB_URL": "http://127.0.0.1:1", "CERNGITLAB_TOKEN": ""},
    )

    async def discover():
        async with Client(parameters, mode=mode) as session:
            assert session.server_info.version == __version__
            assert len((await session.list_tools()).tools) == 15

    await asyncio.wait_for(discover(), timeout=15)

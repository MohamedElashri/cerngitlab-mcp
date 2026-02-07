"""MCP server entry point for the CERN GitLab MCP server."""

import asyncio
import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from cerngitlab_mcp.config import get_settings
from cerngitlab_mcp.exceptions import CERNGitLabError
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.logging import setup_logging
from cerngitlab_mcp.tools import (
    analyze_dependencies,
    get_build_config,
    get_ci_config,
    get_file_content,
    get_release,
    get_repository_info,
    get_repository_readme,
    get_wiki_pages,
    list_releases,
    list_repository_files,
    list_tags,
    search_code,
    search_repositories,
)


logger = logging.getLogger("cerngitlab_mcp")

# Global instances
_settings = get_settings()
_gitlab_client: GitLabClient | None = None
_server = Server("cerngitlab-mcp")


def get_gitlab_client() -> GitLabClient:
    """Get or create the global GitLab client instance."""
    global _gitlab_client
    if _gitlab_client is None:
        _gitlab_client = GitLabClient(_settings)
    return _gitlab_client


def _error_response(message: str) -> list[TextContent]:
    """Create an error response for MCP tool calls."""
    return [TextContent(type="text", text=json.dumps({"error": message}))]


def _success_response(data: dict | list) -> list[TextContent]:
    """Create a success response for MCP tool calls."""
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


# ---------------------------------------------------------------------------
# Tool definitions — test_connectivity is inline, others from tools/ modules
# ---------------------------------------------------------------------------

_TEST_CONNECTIVITY_TOOL = Tool(
    name="test_connectivity",
    description=(
        "Test connectivity to the CERN GitLab instance. "
        "Returns the GitLab version, authentication status, and connection health."
    ),
    inputSchema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)


@_server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of available tools."""
    return [
        _TEST_CONNECTIVITY_TOOL,
        search_repositories.TOOL_DEFINITION,
        get_repository_info.TOOL_DEFINITION,
        list_repository_files.TOOL_DEFINITION,
        get_file_content.TOOL_DEFINITION,
        get_repository_readme.TOOL_DEFINITION,
        search_code.TOOL_DEFINITION,
        get_wiki_pages.TOOL_DEFINITION,
        analyze_dependencies.TOOL_DEFINITION,
        get_ci_config.TOOL_DEFINITION,
        get_build_config.TOOL_DEFINITION,
        list_releases.TOOL_DEFINITION,
        get_release.TOOL_DEFINITION,
        list_tags.TOOL_DEFINITION,
    ]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

_TOOL_HANDLERS = {
    "test_connectivity": "_handle_test_connectivity",
    "search_repositories": search_repositories,
    "get_repository_info": get_repository_info,
    "list_repository_files": list_repository_files,
    "get_file_content": get_file_content,
    "get_repository_readme": get_repository_readme,
    "search_code": search_code,
    "get_wiki_pages": get_wiki_pages,
    "analyze_dependencies": analyze_dependencies,
    "get_ci_config": get_ci_config,
    "get_build_config": get_build_config,
    "list_releases": list_releases,
    "get_release": get_release,
    "list_tags": list_tags,
}


@_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch MCP tool calls."""
    try:
        client = get_gitlab_client()

        if name == "test_connectivity":
            result = await client.test_connection()
            return _success_response(result)

        handler_module = _TOOL_HANDLERS.get(name)
        if handler_module and handler_module != "_handle_test_connectivity":
            result = await handler_module.handle(client, arguments)
            return _success_response(result)

        return _error_response(f"Unknown tool: {name}")
    except CERNGitLabError as exc:
        logger.error("Tool %s failed: %s", name, exc.message)
        return _error_response(exc.message)
    except ValueError as exc:
        logger.warning("Tool %s bad input: %s", name, exc)
        return _error_response(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in tool %s", name)
        return _error_response(f"Internal error: {exc}")


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

async def run_server() -> None:
    """Run the MCP server over stdio."""
    setup_logging(_settings.log_level)
    logger.info("Starting CERN GitLab MCP server")
    logger.info("GitLab URL: %s", _settings.gitlab_url)
    logger.info("Authenticated: %s", bool(_settings.token))

    # Non-blocking connectivity check — log result but never fail startup
    client = get_gitlab_client()
    try:
        conn_info = await client.test_connection()
        if conn_info["status"] == "connected":
            logger.info(
                "Connected to GitLab %s (revision: %s)",
                conn_info.get("version", "?"),
                conn_info.get("revision", "?"),
            )
        else:
            logger.warning(
                "GitLab connectivity check: %s — server will start anyway",
                conn_info.get("error", "unknown"),
            )
    except Exception as exc:
        logger.warning("GitLab connectivity check failed: %s — server will start anyway", exc)

    async with stdio_server() as (read_stream, write_stream):
        await _server.run(
            read_stream,
            write_stream,
            _server.create_initialization_options(),
        )

    # Cleanup
    await client.close()


def main() -> None:
    """Entry point for the cerngitlab-mcp command."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()

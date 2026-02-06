"""MCP server entry point for the CERN GitLab MCP server."""

import asyncio
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server

from cerngitlab_mcp.config import get_settings
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.logging import setup_logging


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


# --- MCP Tool Handlers (to be implemented in subsequent phases) ---
# Tools will be registered here using @_server.tool() decorator


async def run_server() -> None:
    """Run the MCP server over stdio."""
    setup_logging(_settings.log_level)
    logger.info("Starting CERN GitLab MCP server")
    logger.info("GitLab URL: %s", _settings.gitlab_url)
    logger.info("Authenticated: %s", bool(_settings.token))

    client = get_gitlab_client()
    conn_info = await client.test_connection()
    if conn_info["status"] == "connected":
        logger.info(
            "Connected to GitLab %s (revision: %s)",
            conn_info.get("version", "?"),
            conn_info.get("revision", "?"),
        )
    else:
        logger.warning("GitLab connection issue: %s", conn_info.get("error", "unknown"))

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

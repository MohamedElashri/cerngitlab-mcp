"""Stdio transport for single-user MCP server mode."""

import asyncio
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from cerngitlab_mcp.core import McpServerCore
from cerngitlab_mcp.config import Settings, get_settings
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.logging import setup_logging


logger = logging.getLogger("cerngitlab_mcp")


class StdioTransport:
    """Stdio transport adapter for single-user mode.

    This maintains the original stdio behavior while using the new core abstraction.
    Provides full backward compatibility with existing stdio-based deployments.
    """

    def __init__(self, settings: Settings | None = None):
        """Initialize stdio transport.

        Args:
            settings: Optional settings override. If None, uses global settings.
        """
        self.settings = settings or get_settings()
        self.gitlab_client: GitLabClient | None = None
        self.core: McpServerCore | None = None
        self.server = Server("cerngitlab-mcp")
        self._setup_handlers()

    def _get_gitlab_client(self) -> GitLabClient:
        """Get or create the GitLab client instance."""
        if self.gitlab_client is None:
            self.gitlab_client = GitLabClient(self.settings)
        return self.gitlab_client

    def _get_core(self) -> McpServerCore:
        """Get or create the server core instance."""
        if self.core is None:
            client = self._get_gitlab_client()
            self.core = McpServerCore(self.settings, client)
        return self.core

    def _setup_handlers(self) -> None:
        """Set up MCP server handlers using the core abstraction."""

        @self.server.list_tools()
        async def list_tools():
            """Return the list of available tools."""
            core = self._get_core()
            return core.get_tool_definitions()

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Dispatch MCP tool calls through the core."""
            core = self._get_core()
            result = await core.handle_tool_call(name, arguments)

            if result["success"]:
                return core.format_success_response(result["data"])
            else:
                return core.format_error_response(result["error"])

    async def run(self) -> None:
        """Run the MCP server over stdio.

        This method maintains the exact same behavior as the original server
        implementation for full backward compatibility.
        """
        setup_logging(self.settings.log_level)
        logger.info("Starting CERN GitLab MCP server (stdio mode)")
        logger.info("GitLab URL: %s", self.settings.gitlab_url)
        logger.info("Authenticated: %s", bool(self.settings.token))

        # Non-blocking connectivity check — log result but never fail startup
        client = self._get_gitlab_client()
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
            logger.warning(
                "GitLab connectivity check failed: %s — server will start anyway", exc
            )

        # Run the stdio server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )

        # Cleanup
        if self.core:
            await self.core.close()


async def run_stdio_server(settings: Settings | None = None) -> None:
    """Run the MCP server in stdio mode.

    Args:
        settings: Optional settings override. If None, uses global settings.
    """
    transport = StdioTransport(settings)
    await transport.run()


def main_stdio() -> None:
    """Entry point for stdio mode."""
    asyncio.run(run_stdio_server())

"""Stdio transport for single-user MCP server mode."""

import asyncio
import logging

from cerngitlab_mcp.config import Settings, get_settings
from cerngitlab_mcp.core import build_mcp_server
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.logging import setup_logging


logger = logging.getLogger("cerngitlab_mcp")


class StdioTransport:
    """Stdio transport adapter for single-user mode.

    Builds an ``mcp.server.MCPServer`` (protocol 2026-07-28) over the
    standard stdio transport. Older MCP clients are still served through
    the SDK's legacy handshake compatibility.
    """

    def __init__(self, settings: Settings | None = None):
        """Initialize stdio transport.

        Args:
            settings: Optional settings override. If None, uses global settings.
        """
        self.settings = settings or get_settings()
        self.gitlab_client = GitLabClient(self.settings)
        self.mcp = build_mcp_server(self.settings, self.gitlab_client)

    async def run(self) -> None:
        """Run the MCP server over stdio."""
        setup_logging(self.settings.log_level)
        logger.info("Starting CERN GitLab MCP server (stdio mode)")
        logger.info("GitLab URL: %s", self.settings.gitlab_url)
        logger.info("Authenticated: %s", bool(self.settings.token))

        # Non-blocking connectivity check — log result but never fail startup
        try:
            conn_info = await self.gitlab_client.test_connection()
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

        try:
            await self.mcp.run_stdio_async()
        finally:
            await self.gitlab_client.close()


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

"""MCP server entry point for the CERN GitLab MCP server.

Supports dual-mode operation:
- stdio: Single-user mode using stdin/stdout (default, backward compatible)
- http: Multi-user mode using HTTP API
"""

import asyncio
import os
import logging

import click

from cerngitlab_mcp.config import get_settings
from cerngitlab_mcp.transports import run_stdio_server, run_http_server


logger = logging.getLogger("cerngitlab_mcp")


def detect_mode() -> str:
    """Auto-detect server mode based on environment variables.

    Returns:
        'http' if HTTP mode is detected, 'stdio' otherwise
    """
    # Check for explicit HTTP mode flag
    if os.getenv("CERNGITLAB_HTTP_MODE"):
        return "http"

    # Check for HTTP-specific configuration
    if os.getenv("CERNGITLAB_HOST") or os.getenv("CERNGITLAB_PORT"):
        return "http"

    # Default to stdio for backward compatibility
    return "stdio"


@click.command()
@click.option(
    "--mode",
    type=click.Choice(["stdio", "http", "auto"]),
    default="auto",
    help="Server mode: stdio (single-user), http (multi-user), or auto-detect",
)
@click.option(
    "--host",
    default="localhost",
    help="HTTP mode: host to bind to (default: localhost)",
)
@click.option(
    "--port", type=int, default=8000, help="HTTP mode: port to bind to (default: 8000)"
)
def main(mode: str, host: str, port: int) -> None:
    """Run the CERN GitLab MCP server in the specified mode.

    Modes:
    - stdio: Single-user mode using stdin/stdout (original behavior)
    - http: Multi-user mode using HTTP API
    - auto: Auto-detect mode based on environment variables
    """
    settings = get_settings()

    # Resolve mode
    if mode == "auto":
        mode = detect_mode()

    logger.info("Starting CERN GitLab MCP server in %s mode", mode)

    if mode == "stdio":
        asyncio.run(run_stdio_server(settings))
    elif mode == "http":
        # Override host/port from environment if set
        env_host = os.getenv("CERNGITLAB_HOST")
        env_port = os.getenv("CERNGITLAB_PORT")

        if env_host:
            host = env_host
        if env_port:
            port = int(env_port)

        asyncio.run(run_http_server(settings, host, port))
    else:
        raise ValueError(f"Unknown mode: {mode}")


def main_stdio() -> None:
    """Entry point for stdio mode only."""
    settings = get_settings()
    asyncio.run(run_stdio_server(settings))


def main_http() -> None:
    """Entry point for HTTP mode only."""
    settings = get_settings()
    host = os.getenv("CERNGITLAB_HOST", "localhost")
    port = int(os.getenv("CERNGITLAB_PORT", "8000"))
    asyncio.run(run_http_server(settings, host, port))


if __name__ == "__main__":
    main()

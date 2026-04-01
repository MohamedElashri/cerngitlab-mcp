"""HTTP transport for multi-user MCP server mode."""

import asyncio
import logging
import os
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from cerngitlab_mcp.core import McpServerCore
from cerngitlab_mcp.config import Settings
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.logging import setup_logging


logger = logging.getLogger("cerngitlab_mcp")


class McpRequest(BaseModel):
    """MCP tool call request model."""

    name: str
    arguments: dict = {}


class McpResponse(BaseModel):
    """MCP tool call response model."""

    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class UserSession:
    """Represents a user session with isolated GitLab client and core."""

    def __init__(self, user_id: str, gitlab_token: str, base_settings: Settings):
        """Initialize user session.

        Args:
            user_id: Unique user identifier
            gitlab_token: User's GitLab personal access token
            base_settings: Base server settings to inherit from
        """
        self.user_id = user_id

        # Create user-specific settings with their token
        self.settings = Settings(
            gitlab_url=base_settings.gitlab_url,
            token=gitlab_token,
            timeout=base_settings.timeout,
            max_retries=base_settings.max_retries,
            rate_limit_per_minute=base_settings.rate_limit_per_minute,
            default_per_page=base_settings.default_per_page,
            max_per_page=base_settings.max_per_page,
            log_level=base_settings.log_level,
            default_ref=base_settings.default_ref,
        )

        self.gitlab_client = GitLabClient(self.settings)
        self.core = McpServerCore(self.settings, self.gitlab_client)

    async def close(self):
        """Clean up session resources."""
        await self.core.close()


class AuthService:
    """Simple authentication service for demo purposes.

    In production, this should be replaced with proper authentication
    (OAuth, JWT, database-backed user management, etc.)
    """

    def __init__(self):
        # Simple in-memory user store for demo
        # Format: api_key -> (user_id, gitlab_token)
        self.users: Dict[str, tuple[str, str]] = {}

        # Load from environment for demo purposes
        self._load_demo_users()

    def _load_demo_users(self):
        """Load demo users from environment variables."""
        # Example: CERNGITLAB_DEMO_USER_alice=glpat-xxxx
        for key, value in os.environ.items():
            if key.startswith("CERNGITLAB_DEMO_USER_"):
                user_id = key.replace("CERNGITLAB_DEMO_USER_", "")
                api_key = f"demo-{user_id}"
                gitlab_token = value
                self.users[api_key] = (user_id, gitlab_token)
                logger.info("Loaded demo user: %s", user_id)

    def authenticate(self, api_key: str) -> Optional[tuple[str, str]]:
        """Authenticate user by API key.

        Args:
            api_key: User's API key

        Returns:
            Tuple of (user_id, gitlab_token) if valid, None otherwise
        """
        return self.users.get(api_key)


class HttpTransport:
    """HTTP transport for multi-user MCP server mode."""

    def __init__(self, settings: Settings):
        """Initialize HTTP transport.

        Args:
            settings: Base server settings
        """
        self.settings = settings
        self.auth_service = AuthService()
        self.user_sessions: Dict[str, UserSession] = {}
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """Create FastAPI application with all routes and middleware."""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Application lifespan manager."""
            setup_logging(self.settings.log_level)
            logger.info("Starting CERN GitLab MCP server (HTTP mode)")
            logger.info("GitLab URL: %s", self.settings.gitlab_url)
            yield
            # Cleanup all user sessions
            for session in self.user_sessions.values():
                await session.close()
            logger.info("HTTP server shutdown complete")

        app = FastAPI(
            title="CERN GitLab MCP Server",
            description="Multi-user HTTP API for CERN GitLab MCP tools",
            version="0.1.7",
            lifespan=lifespan,
        )

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        return app

    async def get_user_session(self, api_key: str) -> UserSession:
        """Get or create user session.

        Args:
            api_key: User's API key

        Returns:
            User session instance

        Raises:
            HTTPException: If authentication fails
        """
        auth_result = self.auth_service.authenticate(api_key)
        if not auth_result:
            raise HTTPException(status_code=401, detail="Invalid API key")

        user_id, gitlab_token = auth_result

        # Get existing session or create new one
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = UserSession(
                user_id, gitlab_token, self.settings
            )
            logger.info("Created new session for user: %s", user_id)

        return self.user_sessions[user_id]

    def setup_routes(self):
        """Set up FastAPI routes."""

        @self.app.get("/")
        async def root():
            """Root endpoint with server information."""
            return {
                "name": "CERN GitLab MCP Server",
                "version": "0.1.7",
                "mode": "http",
                "gitlab_url": self.settings.gitlab_url,
            }

        @self.app.get("/health")
        async def health():
            """Health check endpoint."""
            return {"status": "healthy", "mode": "http"}

        @self.app.get("/tools")
        async def list_tools(
            authorization: str = Header(..., description="Bearer <api_key>"),
        ):
            """List available MCP tools for authenticated user."""
            api_key = authorization.replace("Bearer ", "")
            session = await self.get_user_session(api_key)
            tools = session.core.get_tool_definitions()
            return {"tools": [tool.model_dump() for tool in tools]}

        @self.app.post("/tools/{tool_name}", response_model=McpResponse)
        async def call_tool(
            tool_name: str,
            request: McpRequest,
            authorization: str = Header(..., description="Bearer <api_key>"),
        ):
            """Execute an MCP tool for authenticated user."""
            api_key = authorization.replace("Bearer ", "")
            session = await self.get_user_session(api_key)

            # Execute tool through core
            result = await session.core.handle_tool_call(tool_name, request.arguments)

            return McpResponse(
                success=result["success"],
                data=result.get("data"),
                error=result.get("error"),
            )

        @self.app.post("/mcp", response_model=McpResponse)
        async def mcp_endpoint(
            request: McpRequest,
            authorization: str = Header(..., description="Bearer <api_key>"),
        ):
            """Generic MCP endpoint (alternative to /tools/{tool_name})."""
            api_key = authorization.replace("Bearer ", "")
            session = await self.get_user_session(api_key)

            result = await session.core.handle_tool_call(
                request.name, request.arguments
            )

            return McpResponse(
                success=result["success"],
                data=result.get("data"),
                error=result.get("error"),
            )

    async def run(self, host: str = "localhost", port: int = 8000):
        """Run the HTTP server.

        Args:
            host: Host to bind to
            port: Port to bind to
        """
        self.setup_routes()

        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            log_level=self.settings.log_level.lower(),
            access_log=True,
        )

        server = uvicorn.Server(config)
        await server.serve()


async def run_http_server(
    settings: Settings, host: str = "localhost", port: int = 8000
) -> None:
    """Run the MCP server in HTTP mode.

    Args:
        settings: Server settings
        host: Host to bind to
        port: Port to bind to
    """
    transport = HttpTransport(settings)
    await transport.run(host, port)


def main_http(host: str = "localhost", port: int = 8000) -> None:
    """Entry point for HTTP mode.

    Args:
        host: Host to bind to
        port: Port to bind to
    """
    from cerngitlab_mcp.config import get_settings

    settings = get_settings()
    asyncio.run(run_http_server(settings, host, port))

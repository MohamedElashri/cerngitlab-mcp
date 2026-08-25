"""HTTP transport with CERN SSO + OAuth authentication.

Exposes two surfaces:

- ``/mcp``: a real MCP endpoint speaking Streamable HTTP under the
  2026-07-28 protocol revision (stateless mode), so any standard MCP
  client can connect. Legacy clients using the ``initialize`` handshake
  are still served through the SDK's compatibility layer.
- REST endpoints (``/tools``, ``/oauth/*``, ...): the pre-existing
  JSON API retained for backward compatibility.
"""

import asyncio
import json as jsonlib
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.routing import Route
import uvicorn

from ..config import Settings
from ..core import SERVER_VERSION, McpServerCore, build_mcp_server
from ..gitlab_client import GitLabClient
from ..logging import setup_logging
from ..models import McpRequest, McpResponse
from ..auth.oauth import OAuthService
from ..auth.session_store import SessionStore
from ..exceptions import AuthenticationError, AuthorizationRequiredError

logger = logging.getLogger(__name__)


class UserSession:
    """Represents a user session with isolated GitLab client and MCP server."""

    def __init__(self, user_id: str, gitlab_token: str, base_settings: Settings):
        """Initialize user session.

        Args:
            user_id: Unique user identifier
            gitlab_token: User's GitLab OAuth token
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

        # MCP protocol surface (Streamable HTTP, stateless)
        self.mcp = build_mcp_server(self.settings, self.gitlab_client)
        # Creating the app wires up the underlying StreamableHTTPSessionManager;
        # requests are dispatched straight into its ASGI entry point.
        self.mcp.streamable_http_app(stateless_http=True)
        self._session_manager = self.mcp.session_manager
        self.mcp_asgi = self._session_manager.asgi_app

    @property
    def core(self) -> McpServerCore:
        if getattr(self, "_core", None) is None:
            self._core = McpServerCore(self.settings, self.gitlab_client)
        return self._core

    async def close(self):
        """Clean up session resources."""
        await self.core.close()


class McpHttpDispatcher:
    """ASGI app that authenticates requests then dispatches to the
    requesting user's per-user MCP server over Streamable HTTP."""

    def __init__(self, transport: "HttpTransport"):
        self.transport = transport

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            return

        auth_header = ""
        for key, value in scope.get("headers", []):
            if key == b"authorization":
                auth_header = value.decode("latin-1")
                break

        try:
            cern_token = self.transport._extract_token(auth_header)
        except HTTPException as exc:
            await self._send_json(send, exc.status_code, {"error": exc.detail})
            return

        try:
            (
                username,
                oauth_token,
            ) = await self.transport.oauth_service.authenticate_user(cern_token)
            await self.transport.session_store.store_session(username, oauth_token)
            session = await self.transport.get_user_session(username, oauth_token)
        except AuthorizationRequiredError as e:
            await self._send_json(
                send,
                202,
                {
                    "error": "authorization_required",
                    "username": e.username,
                    "authorization_url": e.authorization_url,
                    "message": "GitLab authorization required",
                },
            )
            return
        except AuthenticationError:
            await self._send_json(send, 401, {"error": "Authentication failed"})
            return
        except Exception as exc:
            logger.exception("MCP dispatch failed")
            await self._send_json(send, 500, {"error": f"Internal error: {exc}"})
            return

        await session.mcp_asgi(scope, receive, send)

    @staticmethod
    async def _send_json(send: Any, status: int, payload: Dict[str, Any]) -> None:
        body = jsonlib.dumps(payload).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class HttpTransport:
    """CERN SSO-enabled HTTP transport serving MCP over Streamable HTTP."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.oauth_service = OAuthService(settings)
        self.session_store = SessionStore(settings)
        self.user_sessions: Dict[str, UserSession] = {}
        self._session_exit_stacks: Dict[str, Any] = {}

        # Link services
        self.oauth_service.set_session_store(self.session_store)

        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """Create FastAPI application."""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            setup_logging(self.settings.log_level)
            logger.info("Starting CERN GitLab MCP server (CERN SSO mode)")
            logger.info("GitLab URL: %s", self.settings.gitlab_url)
            logger.info(
                "MCP endpoint: /mcp (Streamable HTTP, protocol %s)", SERVER_VERSION
            )

            # Start periodic cleanup task
            cleanup_task = asyncio.create_task(self._periodic_cleanup())

            yield

            # Cleanup
            cleanup_task.cancel()
            for username in list(self.user_sessions):
                await self.close_session(username)
            logger.info("HTTP server shutdown complete")

        app = FastAPI(
            title="CERN GitLab MCP Server",
            description="CERN SSO-enabled multi-user MCP server for GitLab tools",
            version=SERVER_VERSION,
            lifespan=lifespan,
        )

        # CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["*"],
        )

        # MCP protocol endpoint (Streamable HTTP, protocol 2026-07-28)
        app.router.routes.append(
            Route(
                "/mcp",
                McpHttpDispatcher(self),
                methods=["GET", "POST", "DELETE"],
            )
        )

        self._setup_routes(app)
        return app

    async def get_user_session(self, username: str, oauth_token: str) -> UserSession:
        """Get or create an authenticated user session with a running
        MCP Streamable HTTP session manager."""
        if username not in self.user_sessions:
            session = UserSession(username, oauth_token, self.settings)
            stack = AsyncExitStack()
            await stack.enter_async_context(session._session_manager.run())
            self._session_exit_stacks[username] = stack
            self.user_sessions[username] = session
            logger.info("Created session for user: %s", username)
        return self.user_sessions[username]

    async def close_session(self, username: str) -> None:
        """Tear down a user session and its MCP session manager."""
        stack = self._session_exit_stacks.pop(username, None)
        session = self.user_sessions.pop(username, None)
        if stack is not None:
            await stack.aclose()
        if session is not None:
            await session.close()

    def _setup_routes(self, app: FastAPI):
        """Set up simple OAuth routes."""

        @app.get("/")
        async def root():
            return {
                "name": "CERN GitLab MCP Server",
                "version": SERVER_VERSION,
                "auth_mode": "cern_sso_oauth",
                "gitlab_url": self.settings.gitlab_url,
                "protocol_version": "2026-07-28",
                "description": (
                    "Uses your existing GitLab permissions. Connect MCP clients to /mcp"
                ),
            }

        @app.get("/health")
        async def health():
            return {"status": "healthy", "auth_mode": "cern_sso_oauth"}

        @app.get("/oauth/authorize")
        async def start_oauth_flow(authorization: str = Header(...)):
            """Start OAuth authorization flow."""
            cern_token = self._extract_token(authorization)

            try:
                # This will raise AuthorizationRequiredError if needed
                await self.oauth_service.authenticate_user(cern_token)
                return {"status": "already_authorized"}

            except AuthorizationRequiredError as e:
                return {
                    "authorization_required": True,
                    "username": e.username,
                    "authorization_url": e.authorization_url,
                    "message": "Please authorize GitLab access",
                }
            except AuthenticationError:
                raise HTTPException(status_code=401, detail="Invalid CERN SSO token")

        @app.get("/oauth/callback")
        async def oauth_callback(code: str, state: str):
            """Handle OAuth callback."""
            try:
                username, oauth_token = await self.oauth_service.exchange_oauth_code(
                    code, state
                )
                await self.session_store.store_session(username, oauth_token)

                return HTMLResponse("""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Authorization Successful</title>
                    <style>
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            text-align: center; margin: 50px; background: #f5f5f5;
                        }
                        .container {
                            background: white; padding: 40px; border-radius: 8px;
                            box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 500px;
                            margin: 0 auto;
                        }
                        .success { color: #28a745; font-size: 24px; margin-bottom: 20px; }
                        .info { color: #666; line-height: 1.6; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2 class="success">✓ Authorization Successful!</h2>
                        <p class="info">You can now access GitLab through the MCP server with your existing permissions.</p>
                        <p class="info">You can close this window and return to using the MCP server.</p>
                    </div>
                    <script>
                        setTimeout(() => window.close(), 3000);
                    </script>
                </body>
                </html>
                """)

            except Exception as e:
                logger.error(f"OAuth callback error: {e}")
                return HTMLResponse(
                    f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Authorization Failed</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            text-align: center; margin: 50px; background: #f5f5f5;
                        }}
                        .container {{
                            background: white; padding: 40px; border-radius: 8px;
                            box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 500px;
                            margin: 0 auto;
                        }}
                        .error {{ color: #dc3545; font-size: 24px; margin-bottom: 20px; }}
                        .info {{ color: #666; line-height: 1.6; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2 class="error">✗ Authorization Failed</h2>
                        <p class="info">Error: {str(e)}</p>
                        <p class="info">Please try again or contact support.</p>
                    </div>
                </body>
                </html>
                """,
                    status_code=400,
                )

        @app.get("/tools")
        async def list_tools(authorization: str = Header(...)):
            """List available tools."""
            session = await self._get_user_session(authorization)
            tools = session.core.get_tool_definitions()
            return {"tools": [tool.model_dump(by_alias=True) for tool in tools]}

        @app.post("/tools/{tool_name}")
        async def call_tool(
            tool_name: str,
            request: McpRequest,
            authorization: str = Header(...),
        ):
            """Execute tool - GitLab will handle permission checks."""
            session = await self._get_user_session(authorization)

            # No additional access control - let GitLab handle it
            result = await session.core.handle_tool_call(tool_name, request.arguments)

            return McpResponse(
                success=result["success"],
                data=result.get("data"),
                error=result.get("error"),
            )

        @app.delete("/session")
        async def revoke_session(authorization: str = Header(...)):
            """Revoke user session."""
            cern_token = self._extract_token(authorization)

            try:
                user_info = await self.oauth_service._validate_cern_token(cern_token)
                if not user_info:
                    raise HTTPException(status_code=401, detail="Invalid CERN token")

                username = user_info["preferred_username"]
                await self.session_store.revoke_session(username)

                # Remove from active sessions
                if username in self.user_sessions:
                    await self.close_session(username)

                return {"status": "session_revoked", "username": username}

            except Exception:
                raise HTTPException(status_code=401, detail="Invalid CERN token")

        @app.get("/admin/sessions")
        async def list_active_sessions():
            """Admin endpoint to list active sessions."""
            sessions = await self.session_store.list_active_sessions()
            return {"sessions": sessions, "count": len(sessions)}

    async def _get_user_session(self, authorization: str) -> UserSession:
        """Get user session with simple OAuth."""
        cern_token = self._extract_token(authorization)

        try:
            username, oauth_token = await self.oauth_service.authenticate_user(
                cern_token
            )

            # Store session
            await self.session_store.store_session(username, oauth_token)
            return await self.get_user_session(username, oauth_token)

        except AuthorizationRequiredError as e:
            raise HTTPException(
                status_code=202,
                detail={
                    "error": "authorization_required",
                    "username": e.username,
                    "authorization_url": e.authorization_url,
                    "message": "GitLab authorization required",
                },
            )
        except AuthenticationError:
            raise HTTPException(status_code=401, detail="Authentication failed")

    def _extract_token(self, authorization: str) -> str:
        """Extract token from Authorization header."""
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        return authorization[7:]

    async def _periodic_cleanup(self):
        """Periodic cleanup of expired sessions."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self.session_store.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error during periodic cleanup: {e}")

    async def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the HTTP server."""
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

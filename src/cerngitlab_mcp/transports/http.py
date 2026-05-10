"""Simple HTTP transport with CERN SSO + OAuth authentication."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

from ..config import Settings
from ..core import McpServerCore
from ..gitlab_client import GitLabClient
from ..logging import setup_logging
from ..models import McpRequest, McpResponse
from ..auth.oauth import OAuthService
from ..auth.session_store import SessionStore
from ..exceptions import AuthenticationError, AuthorizationRequiredError

logger = logging.getLogger(__name__)


class UserSession:
    """Represents a user session with isolated GitLab client and core."""

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
        self.core = McpServerCore(self.settings, self.gitlab_client)

    async def close(self):
        """Clean up session resources."""
        await self.core.close()


class HttpTransport:
    """Simple HTTP transport that relies on GitLab's permission system."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.oauth_service = OAuthService(settings)
        self.session_store = SessionStore(settings)
        self.user_sessions: Dict[str, UserSession] = {}

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

            # Start periodic cleanup task
            cleanup_task = asyncio.create_task(self._periodic_cleanup())

            yield

            # Cleanup
            cleanup_task.cancel()
            for session in self.user_sessions.values():
                await session.close()
            logger.info("HTTP server shutdown complete")

        app = FastAPI(
            title="CERN GitLab MCP Server",
            description="CERN SSO-enabled multi-user HTTP API for GitLab MCP tools",
            version="0.2.0",
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

        self._setup_routes(app)
        return app

    def _setup_routes(self, app: FastAPI):
        """Set up simple OAuth routes."""

        @app.get("/")
        async def root():
            return {
                "name": "CERN GitLab MCP Server",
                "version": "0.2.0",
                "auth_mode": "cern_sso_oauth",
                "gitlab_url": self.settings.gitlab_url,
                "description": "Uses your existing GitLab permissions",
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
            return {"tools": [tool.model_dump() for tool in tools]}

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
                    await self.user_sessions[username].close()
                    del self.user_sessions[username]

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

            # Get or create user session
            if username not in self.user_sessions:
                self.user_sessions[username] = UserSession(
                    username, oauth_token, self.settings
                )
                logger.info(f"Created session for user: {username}")

            return self.user_sessions[username]

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
        import asyncio

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

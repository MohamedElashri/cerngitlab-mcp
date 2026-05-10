"""Configuration management for the CERN GitLab MCP server."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Server configuration loaded from environment variables.

    Environment variables are prefixed with CERNGITLAB_ by default.
    Example: CERNGITLAB_GITLAB_URL=https://gitlab.cern.ch
    """

    model_config = {"env_prefix": "CERNGITLAB_"}

    # GitLab settings
    gitlab_url: str = Field(
        default="https://gitlab.cern.ch",
        description="Base URL of the CERN GitLab instance",
    )
    token: str = Field(
        default="",
        description="GitLab personal access token. Empty string means public-only access (legacy mode).",
    )
    timeout: float = Field(
        default=30.0,
        description="HTTP request timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries for failed requests",
    )
    rate_limit_per_minute: int = Field(
        default=300,
        description="Maximum API requests per minute",
    )
    default_per_page: int = Field(
        default=20,
        description="Default number of results per page for paginated endpoints",
    )
    max_per_page: int = Field(
        default=100,
        description="Maximum number of results per page",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    default_ref: str = Field(
        default="",
        description="Default Git branch or tag to search within. Empty means search all branches.",
    )

    # CERN SSO settings
    cern_client_id: str = Field(
        default="",
        description="CERN SSO OAuth client ID",
    )

    # GitLab OAuth settings
    gitlab_oauth_client_id: str = Field(
        default="",
        description="GitLab OAuth application client ID",
    )
    gitlab_oauth_client_secret: str = Field(
        default="",
        description="GitLab OAuth application client secret",
    )

    # Server settings
    server_base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL of this MCP server (for OAuth callbacks)",
    )
    session_storage_path: str = Field(
        default="/tmp/cerngitlab/sessions",
        description="Directory for OAuth sessions",
    )

    # HTTP server settings
    host: str = Field(
        default="0.0.0.0",
        description="HTTP server host",
    )
    port: int = Field(
        default=8000,
        description="HTTP server port",
    )


def get_settings() -> Settings:
    """Create and return a Settings instance from environment variables."""
    return Settings()

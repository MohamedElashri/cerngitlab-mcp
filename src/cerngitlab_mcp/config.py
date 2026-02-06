"""Configuration management for the CERN GitLab MCP server."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Server configuration loaded from environment variables.

    Environment variables are prefixed with CERNGITLAB_ by default.
    Example: CERNGITLAB_TOKEN=glpat-xxxx
    """

    model_config = {"env_prefix": "CERNGITLAB_"}

    gitlab_url: str = Field(
        default="https://gitlab.cern.ch",
        description="Base URL of the CERN GitLab instance",
    )
    token: str = Field(
        default="",
        description="GitLab personal access token. Empty string means public-only access.",
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
        description="Maximum API requests per minute (GitLab default for authenticated users)",
    )
    default_per_page: int = Field(
        default=20,
        description="Default number of results per page for paginated endpoints",
    )
    max_per_page: int = Field(
        default=100,
        description="Maximum number of results per page (GitLab hard limit)",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )


def get_settings() -> Settings:
    """Create and return a Settings instance from environment variables."""
    return Settings()

"""Custom exceptions for the CERN GitLab MCP server."""


class CERNGitLabError(Exception):
    """Base exception for all CERN GitLab MCP errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(CERNGitLabError):
    """Raised when authentication fails or token is invalid."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, status_code=401)


class NotFoundError(CERNGitLabError):
    """Raised when a requested resource is not found."""

    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(f"{resource} not found", status_code=404)


class RateLimitError(CERNGitLabError):
    """Raised when the GitLab API rate limit is exceeded."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "Rate limit exceeded"
        if retry_after is not None:
            msg += f", retry after {retry_after:.1f}s"
        super().__init__(msg, status_code=429)


class GitLabAPIError(CERNGitLabError):
    """Raised for unexpected GitLab API errors."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(f"GitLab API error ({status_code}): {message}", status_code=status_code)

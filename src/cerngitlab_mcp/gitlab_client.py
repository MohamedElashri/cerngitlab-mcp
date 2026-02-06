"""GitLab API client with rate limiting and error handling."""

import asyncio
import logging
import time
from typing import Any

import httpx

from cerngitlab_mcp.config import Settings
from cerngitlab_mcp.exceptions import (
    AuthenticationError,
    GitLabAPIError,
    NotFoundError,
    RateLimitError,
)


logger = logging.getLogger("cerngitlab_mcp")


class RateLimiter:
    """Simple sliding-window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        now = time.monotonic()
        # Remove timestamps outside the window
        self._timestamps = [t for t in self._timestamps if now - t < self.window_seconds]

        if len(self._timestamps) >= self.max_requests:
            # Wait until the oldest request exits the window
            sleep_time = self._timestamps[0] + self.window_seconds - now
            if sleep_time > 0:
                logger.debug("Rate limit reached, sleeping %.2fs", sleep_time)
                await asyncio.sleep(sleep_time)

        self._timestamps.append(time.monotonic())


class GitLabClient:
    """Async HTTP client for the CERN GitLab API.

    Handles authentication, rate limiting, retries, and error mapping.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.gitlab_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/v4"
        self._rate_limiter = RateLimiter(
            max_requests=settings.rate_limit_per_minute,
            window_seconds=60.0,
        )
        self._client: httpx.AsyncClient | None = None

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers, including auth token if available."""
        headers = {
            "Accept": "application/json",
            "User-Agent": "cerngitlab-mcp/0.1.0",
        }
        if self.settings.token:
            headers["PRIVATE-TOKEN"] = self.settings.token
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers=self._build_headers(),
                timeout=httpx.Timeout(self.settings.timeout),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Make an API request with rate limiting and retries.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path relative to /api/v4 (e.g., "/projects").
            params: Query parameters.
            json_body: JSON request body.

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: On 401 responses.
            NotFoundError: On 404 responses.
            RateLimitError: On 429 responses after retries exhausted.
            GitLabAPIError: On other error responses.
        """
        response = await self.request_raw(method, path, params=params, json_body=json_body)
        return response.json()

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """Convenience method for GET requests."""
        return await self.request("GET", path, params=params)

    async def request_raw(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an API request and return the raw httpx.Response.

        Same retry/rate-limit logic as request(), but returns the full
        response object so callers can inspect headers (e.g. pagination).
        """
        client = await self._get_client()
        last_exception: Exception | None = None

        for attempt in range(1, self.settings.max_retries + 1):
            await self._rate_limiter.acquire()

            try:
                response = await client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                )
            except httpx.TimeoutException as exc:
                last_exception = exc
                logger.warning(
                    "Request timeout (attempt %d/%d): %s %s",
                    attempt, self.settings.max_retries, method, path,
                )
                if attempt < self.settings.max_retries:
                    await asyncio.sleep(2 ** attempt)
                continue
            except httpx.HTTPError as exc:
                last_exception = exc
                logger.warning(
                    "HTTP error (attempt %d/%d): %s %s - %s",
                    attempt, self.settings.max_retries, method, path, exc,
                )
                if attempt < self.settings.max_retries:
                    await asyncio.sleep(2 ** attempt)
                continue

            if response.status_code == 200:
                return response

            if response.status_code == 401:
                raise AuthenticationError()

            if response.status_code == 404:
                raise NotFoundError(path)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else 2 ** attempt
                if attempt < self.settings.max_retries:
                    logger.warning("Rate limited, retrying in %.1fs", wait)
                    await asyncio.sleep(wait)
                    continue
                raise RateLimitError(retry_after=wait)

            try:
                error_body = response.json()
                error_msg = error_body.get("message", error_body.get("error", str(error_body)))
            except Exception:
                error_msg = response.text[:500]

            if response.status_code >= 500 and attempt < self.settings.max_retries:
                logger.warning(
                    "Server error %d (attempt %d/%d): %s",
                    response.status_code, attempt, self.settings.max_retries, error_msg,
                )
                await asyncio.sleep(2 ** attempt)
                continue

            raise GitLabAPIError(str(error_msg), response.status_code)

        if last_exception:
            raise GitLabAPIError(
                f"Request failed after {self.settings.max_retries} retries: {last_exception}",
                status_code=0,
            )
        raise GitLabAPIError("Request failed with unknown error", status_code=0)

    async def get_paginated(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        max_pages: int = 5,
    ) -> list[Any]:
        """Fetch multiple pages of results.

        Uses GitLab pagination headers (x-next-page, x-total-pages) to
        iterate through result pages. All requests go through the full
        retry/rate-limit/error-handling pipeline.

        Args:
            path: API path.
            params: Query parameters (page/per_page will be managed).
            max_pages: Maximum number of pages to fetch.

        Returns:
            Combined list of results from all pages.
        """
        params = dict(params or {})
        params.setdefault("per_page", self.settings.default_per_page)
        params.setdefault("page", 1)

        all_results: list[Any] = []

        for page_num in range(max_pages):
            response = await self.request_raw("GET", path, params=params)
            data = response.json()

            if isinstance(data, list):
                all_results.extend(data)
                if not data:
                    break
                next_page = response.headers.get("x-next-page", "")
                if not next_page:
                    break
                params["page"] = int(next_page)
            else:
                all_results.append(data)
                break

            logger.debug(
                "Paginated fetch %s page %d, got %d items (total so far: %d)",
                path, page_num + 1, len(data), len(all_results),
            )

        return all_results

    async def test_connection(self) -> dict[str, Any]:
        """Test connectivity to the GitLab instance.

        Uses two probes:
        1. GET /projects?per_page=1&visibility=public — works without auth
        2. GET /version — requires authentication on most instances

        Returns:
            Dict with connection status and metadata.
        """
        authenticated = bool(self.settings.token)
        result: dict[str, Any] = {
            "status": "error",
            "gitlab_url": self.base_url,
            "authenticated": authenticated,
        }

        # Probe 1: public projects endpoint (no auth needed)
        try:
            projects = await self.get(
                "/projects",
                params={"per_page": 1, "visibility": "public"},
            )
            result["status"] = "connected"
            result["public_access"] = True
        except Exception as exc:
            result["error"] = f"Cannot reach GitLab: {exc}"
            return result

        # Probe 2: /version (requires auth on CERN GitLab)
        if authenticated:
            try:
                version_info = await self.get("/version")
                result["version"] = version_info.get("version", "unknown")
                result["revision"] = version_info.get("revision", "unknown")
            except AuthenticationError:
                result["auth_valid"] = False
                result["warning"] = "Token provided but rejected — falling back to public access"
            except Exception:
                pass  # version endpoint may simply require auth; not critical
        else:
            result["note"] = "No token provided — public access only"

        return result

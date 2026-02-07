"""Shared test fixtures for the CERN GitLab MCP server tests."""

import base64

import pytest

from cerngitlab_mcp.config import Settings
from cerngitlab_mcp.gitlab_client import GitLabClient


@pytest.fixture
def settings():
    """Create test settings pointing to a fake GitLab instance."""
    return Settings(
        gitlab_url="https://gitlab.example.com",
        token="test-token",
        timeout=5.0,
        max_retries=1,
        rate_limit_per_minute=1000,
    )


@pytest.fixture
def client(settings):
    """Create a GitLabClient with test settings."""
    return GitLabClient(settings)


def make_file_response(content: str, file_name: str = "test.py", ref: str = "main") -> dict:
    """Create a mock GitLab file API response."""
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    return {
        "file_name": file_name,
        "file_path": file_name,
        "size": len(content),
        "encoding": "base64",
        "content": encoded,
        "ref": ref,
        "last_commit_id": "abc123",
        "content_sha256": "deadbeef",
    }

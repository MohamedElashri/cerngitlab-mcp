"""Shared utilities for tool modules."""

import base64

from urllib.parse import quote

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.exceptions import NotFoundError


def encode_project(project: str) -> str:
    """Encode a project path for use in GitLab API URLs.

    Numeric IDs are passed through as-is. Path strings are URL-encoded.
    """
    if project.isdigit():
        return project
    return quote(project, safe="")


async def resolve_ref(client: GitLabClient, encoded_project: str, ref: str) -> str:
    """Resolve a ref, falling back to the project's default branch if empty.

    CERN GitLab's file API requires an explicit ref parameter.
    """
    if ref:
        return ref
    project_data = await client.get(f"/projects/{encoded_project}", params={"statistics": "false"})
    return project_data.get("default_branch", "main")


async def fetch_file(client: GitLabClient, encoded_project: str, file_path: str, ref: str) -> str | None:
    """Fetch and decode a file from a GitLab repository.

    Returns the file content as a string, or None if the file is not found.
    """
    encoded_path = quote(file_path, safe="")
    try:
        data = await client.get(
            f"/projects/{encoded_project}/repository/files/{encoded_path}",
            params={"ref": ref},
        )
        content_encoded = data.get("content", "")
        encoding = data.get("encoding", "base64")
        if encoding == "base64" and content_encoded:
            return base64.b64decode(content_encoded).decode("utf-8")
        return content_encoded
    except NotFoundError:
        return None
    except Exception:
        return None

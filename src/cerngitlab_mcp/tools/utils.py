"""Shared utilities for tool modules."""

from urllib.parse import quote

from cerngitlab_mcp.gitlab_client import GitLabClient


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

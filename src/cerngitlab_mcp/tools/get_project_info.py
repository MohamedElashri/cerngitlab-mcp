"""MCP tool: get_repository_info — get detailed information about a CERN GitLab repository."""

from typing import Any
from urllib.parse import quote

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient


TOOL_DEFINITION = Tool(
    name="get_project_info",
    description=(
        "Get detailed information about a specific CERN GitLab project "
        "(metadata, statistics, description). Accepts either a numeric project ID "
        "or a full project path (e.g. 'atlas/athena')."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": (
                    "Project identifier — either a numeric ID (e.g. '12345') "
                    "or a URL-encoded path (e.g. 'atlas/athena')"
                ),
            },
        },
        "required": ["project"],
    },
)


def _encode_project(project: str) -> str:
    """Encode a project path for use in GitLab API URLs.

    Numeric IDs are passed through as-is. Path strings are URL-encoded.
    """
    if project.isdigit():
        return project
    return quote(project, safe="")


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the get_repository_info tool.

    Returns:
        Dict with detailed project information.
    """
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    encoded = _encode_project(project)

    # Fetch project details and languages in parallel-ish (sequential for simplicity,
    # but both go through the rate-limited client)
    project_data = await client.get(f"/projects/{encoded}", params={"statistics": "true"})

    # Fetch languages breakdown
    try:
        languages = await client.get(f"/projects/{encoded}/languages")
    except Exception:
        languages = {}

    result: dict[str, Any] = {
        "id": project_data.get("id"),
        "name": project_data.get("name"),
        "path_with_namespace": project_data.get("path_with_namespace"),
        "description": project_data.get("description") or "",
        "web_url": project_data.get("web_url"),
        "default_branch": project_data.get("default_branch"),
        "visibility": project_data.get("visibility"),
        "topics": project_data.get("topics", []),
        "star_count": project_data.get("star_count", 0),
        "forks_count": project_data.get("forks_count", 0),
        "open_issues_count": project_data.get("open_issues_count", 0),
        "created_at": project_data.get("created_at"),
        "last_activity_at": project_data.get("last_activity_at"),
        "languages": languages,
        "readme_url": project_data.get("readme_url"),
        "license": (project_data.get("license") or {}).get("name"),
        "namespace": {
            "name": (project_data.get("namespace") or {}).get("name"),
            "path": (project_data.get("namespace") or {}).get("full_path"),
        },
    }

    # Include statistics if available
    stats = project_data.get("statistics")
    if stats:
        result["statistics"] = {
            "commit_count": stats.get("commit_count", 0),
            "repository_size": stats.get("repository_size", 0),
            "storage_size": stats.get("storage_size", 0),
        }

    return result

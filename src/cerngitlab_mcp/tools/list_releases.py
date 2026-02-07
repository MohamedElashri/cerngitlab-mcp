"""MCP tool: list_releases — list releases from a CERN GitLab repository."""

from typing import Any

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.exceptions import NotFoundError
from cerngitlab_mcp.tools.utils import encode_project


TOOL_DEFINITION = Tool(
    name="list_releases",
    description=(
        "List releases from a CERN GitLab repository. "
        "Returns release tags, dates, and descriptions. "
        "Useful for tracking software versions and finding changelogs."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": (
                    "Project identifier — either a numeric ID (e.g. '12345') "
                    "or a path (e.g. 'atlas/athena')"
                ),
            },
            "per_page": {
                "type": "integer",
                "description": "Number of releases to return (default: 20, max: 100)",
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["project"],
    },
)


def _format_release(release: dict[str, Any]) -> dict[str, Any]:
    """Format a single release entry."""
    return {
        "tag_name": release.get("tag_name"),
        "name": release.get("name"),
        "description": release.get("description", ""),
        "created_at": release.get("created_at"),
        "released_at": release.get("released_at"),
        "author": (release.get("author") or {}).get("username"),
        "commit_path": (release.get("commit") or {}).get("short_id"),
        "assets_count": len((release.get("assets") or {}).get("links", [])),
        "sources_count": len((release.get("assets") or {}).get("sources", [])),
    }


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the list_releases tool."""
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    encoded_project = encode_project(project)

    per_page = arguments.get("per_page", 20)
    per_page = max(1, min(per_page, 100))

    try:
        releases = await client.get(
            f"/projects/{encoded_project}/releases",
            params={"per_page": per_page},
        )
    except NotFoundError:
        return {
            "project": project,
            "total_releases": 0,
            "releases": [],
            "note": "Project not found",
        }

    if not isinstance(releases, list):
        releases = []

    return {
        "project": project,
        "total_releases": len(releases),
        "releases": [_format_release(r) for r in releases],
    }

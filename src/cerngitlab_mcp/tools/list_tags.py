"""MCP tool: list_tags — list repository tags from a CERN GitLab repository."""

from typing import Any

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.exceptions import NotFoundError
from cerngitlab_mcp.tools.utils import encode_project


TOOL_DEFINITION = Tool(
    name="list_tags",
    description=(
        "List tags from a CERN GitLab repository. "
        "Returns tag names with their associated commit references. "
        "Useful for finding version history and release points."
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
            "search": {
                "type": "string",
                "description": "Optional: filter tags by name (e.g. 'v1' to find all v1.x tags)",
            },
            "sort": {
                "type": "string",
                "enum": ["asc", "desc"],
                "description": "Sort order by tag name (default: desc — newest first)",
            },
            "per_page": {
                "type": "integer",
                "description": "Number of tags to return (default: 20, max: 100)",
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["project"],
    },
)


def _format_tag(tag: dict[str, Any]) -> dict[str, Any]:
    """Format a single tag entry."""
    commit = tag.get("commit") or {}
    return {
        "name": tag.get("name"),
        "message": tag.get("message", ""),
        "target": tag.get("target"),
        "commit": {
            "id": commit.get("id"),
            "short_id": commit.get("short_id"),
            "title": commit.get("title"),
            "created_at": commit.get("created_at"),
            "author_name": commit.get("author_name"),
        },
        "protected": tag.get("protected", False),
    }


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the list_tags tool."""
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    encoded_project = encode_project(project)

    params: dict[str, Any] = {}

    search = arguments.get("search", "").strip()
    if search:
        params["search"] = search

    sort = arguments.get("sort", "").strip()
    if sort in ("asc", "desc"):
        params["sort"] = sort

    per_page = arguments.get("per_page", 20)
    per_page = max(1, min(per_page, 100))
    params["per_page"] = per_page

    try:
        tags = await client.get(
            f"/projects/{encoded_project}/repository/tags",
            params=params,
        )
    except NotFoundError:
        return {
            "project": project,
            "total_tags": 0,
            "tags": [],
            "note": "Project not found",
        }

    if not isinstance(tags, list):
        tags = []

    return {
        "project": project,
        "total_tags": len(tags),
        "tags": [_format_tag(t) for t in tags],
    }

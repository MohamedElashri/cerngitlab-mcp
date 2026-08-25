"""MCP tool: list_branches — list or search branches in a CERN GitLab repository."""

from typing import Any

from mcp.types import Tool

from cerngitlab_mcp.exceptions import NotFoundError
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.tools.utils import encode_project


TOOL_DEFINITION = Tool(
    name="list_branches",
    description=(
        "List or search branches in a CERN GitLab repository. "
        "Returns branch names and commit metadata so a branch can be selected and "
        "passed as the 'ref' argument to repository content and code-search tools."
    ),
    input_schema={
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
                "description": (
                    "Optional branch-name filter. GitLab supports partial matches "
                    "and anchors such as '^main$' for an exact match."
                ),
            },
            "page": {
                "type": "integer",
                "description": "Page number to retrieve (default: 1)",
                "minimum": 1,
            },
            "per_page": {
                "type": "integer",
                "description": "Number of branches to return (default: 20, max: 100)",
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["project"],
    },
)


def _format_branch(branch: dict[str, Any]) -> dict[str, Any]:
    """Format a single branch entry."""
    commit = branch.get("commit") or {}
    return {
        "name": branch.get("name"),
        "default": branch.get("default", False),
        "merged": branch.get("merged", False),
        "protected": branch.get("protected", False),
        "can_push": branch.get("can_push", False),
        "web_url": branch.get("web_url"),
        "commit": {
            "id": commit.get("id"),
            "short_id": commit.get("short_id"),
            "title": commit.get("title"),
            "author_name": commit.get("author_name"),
            "created_at": commit.get("created_at"),
            "committed_date": commit.get("committed_date"),
            "web_url": commit.get("web_url"),
        },
    }


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the list_branches tool."""
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    encoded_project = encode_project(project)

    page = max(1, arguments.get("page", 1))
    per_page = max(1, min(arguments.get("per_page", 20), 100))
    params: dict[str, Any] = {"page": page, "per_page": per_page}

    search = arguments.get("search", "").strip()
    if search:
        params["search"] = search

    try:
        branches = await client.get(
            f"/projects/{encoded_project}/repository/branches",
            params=params,
        )
    except NotFoundError:
        return {
            "project": project,
            "search": search or None,
            "page": page,
            "per_page": per_page,
            "total_branches": 0,
            "branches": [],
            "note": "Project not found",
        }

    if not isinstance(branches, list):
        branches = []

    return {
        "project": project,
        "search": search or None,
        "page": page,
        "per_page": per_page,
        "total_branches": len(branches),
        "branches": [_format_branch(branch) for branch in branches],
    }

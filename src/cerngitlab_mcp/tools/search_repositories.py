"""MCP tool: search_repositories — search public CERN GitLab repositories."""

from typing import Any

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient


TOOL_DEFINITION = Tool(
    name="search_repositories",
    description=(
        "Search for public repositories on CERN GitLab by keywords, topics, "
        "or programming language. Useful for discovering HEP code, analysis "
        "frameworks, and physics tools."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string (matches project name, description, etc.)",
            },
            "language": {
                "type": "string",
                "description": "Filter by primary programming language (e.g. 'python', 'c++', 'java')",
            },
            "topic": {
                "type": "string",
                "description": "Filter by project topic/tag (e.g. 'physics', 'root', 'atlas')",
            },
            "sort_by": {
                "type": "string",
                "enum": ["last_activity_at", "name", "created_at", "updated_at", "stars"],
                "description": "Sort results by this field (default: last_activity_at)",
            },
            "order": {
                "type": "string",
                "enum": ["desc", "asc"],
                "description": "Sort order (default: desc)",
            },
            "per_page": {
                "type": "integer",
                "description": "Number of results to return (default: 20, max: 100)",
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": [],
    },
)


def _format_project(project: dict[str, Any]) -> dict[str, Any]:
    """Extract the most useful fields from a GitLab project response."""
    return {
        "id": project.get("id"),
        "name": project.get("name"),
        "path_with_namespace": project.get("path_with_namespace"),
        "description": project.get("description") or "",
        "web_url": project.get("web_url"),
        "default_branch": project.get("default_branch"),
        "topics": project.get("topics", []),
        "star_count": project.get("star_count", 0),
        "forks_count": project.get("forks_count", 0),
        "last_activity_at": project.get("last_activity_at"),
        "created_at": project.get("created_at"),
        "visibility": project.get("visibility"),
    }


async def handle(client: GitLabClient, arguments: dict) -> list[dict[str, Any]]:
    """Execute the search_repositories tool.

    Returns:
        List of formatted project dicts.
    """
    params: dict[str, Any] = {
        "visibility": "public",
    }

    query = arguments.get("query", "").strip()
    if query:
        params["search"] = query

    language = arguments.get("language", "").strip()
    if language:
        params["with_programming_language"] = language

    topic = arguments.get("topic", "").strip()
    if topic:
        params["topic"] = topic

    sort_by = arguments.get("sort_by", "last_activity_at")
    # GitLab uses "stars" internally as "star_count" but the API param is just the field name
    if sort_by == "stars":
        sort_by = "star_count"
    params["order_by"] = sort_by
    params["sort"] = arguments.get("order", "desc")

    per_page = arguments.get("per_page", 20)
    per_page = max(1, min(per_page, 100))
    params["per_page"] = per_page

    projects = await client.get("/projects", params=params)

    if not isinstance(projects, list):
        return []

    return [_format_project(p) for p in projects]

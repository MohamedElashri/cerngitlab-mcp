"""MCP tool: search_issues — search for issues in CERN GitLab projects."""

from typing import Any
from urllib.parse import quote

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.exceptions import AuthenticationError

TOOL_DEFINITION = Tool(
    name="search_issues",
    description=(
        "Search for issues and discussions in CERN GitLab projects. "
        "Useful for understanding how a library is used, finding solution to common errors, "
        "or checking if a feature is supported."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "search_term": {
                "type": "string",
                "description": "Keywords to search for in issue titles and descriptions",
            },
            "project": {
                "type": "string",
                "description": (
                    "Optional: limit search to a specific project. "
                    "If omitted, searches across all projects you have access to."
                ),
            },
            "state": {
                "type": "string",
                "enum": ["opened", "closed", "all"],
                "description": "Filter by issue state (default: all)",
            },
            "per_page": {
                "type": "integer",
                "description": "Number of results to return (default: 10, max: 100)",
            },
        },
        "required": ["search_term"],
    },
)


def _encode_project(project: str) -> str:
    if project.isdigit():
        return project
    return quote(project, safe="")


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the search_issues tool."""
    search_term = arguments.get("search_term", "").strip()
    if not search_term:
        raise ValueError("'search_term' parameter is required")

    project = arguments.get("project", "").strip()
    state = arguments.get("state", "all")
    per_page = arguments.get("per_page", 10)

    params = {
        "search": search_term,
        "scope": "all",
        "state": state,
        "per_page": per_page,
    }

    try:
        if project:
            encoded_project = _encode_project(project)
            results = await client.get(f"/projects/{encoded_project}/issues", params=params)
            scope_desc = f"project '{project}'"
        else:
            # Global issue search
            results = await client.get("/issues", params=params)
            scope_desc = "all projects"
    except AuthenticationError:
        return {
            "error": "Issue search requires authentication. Please configure CERNGITLAB_TOKEN.",
            "results": [],
        }

    if not isinstance(results, list):
        results = []

    formatted_results = []
    for issue in results:
        formatted_results.append({
            "title": issue.get("title"),
            "description_snippet": (issue.get("description") or "")[:200],
            "state": issue.get("state"),
            "web_url": issue.get("web_url"),
            "author": issue.get("author", {}).get("name"),
            "created_at": issue.get("created_at"),
        })

    return {
        "search_term": search_term,
        "scope": scope_desc,
        "count": len(formatted_results),
        "issues": formatted_results,
    }

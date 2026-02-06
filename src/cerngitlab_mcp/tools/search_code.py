"""MCP tool: search_code — search for code across CERN GitLab repositories."""

from typing import Any
from urllib.parse import quote

from mcp.types import TextContent, Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.exceptions import AuthenticationError


TOOL_DEFINITION = Tool(
    name="search_code",
    description=(
        "Search for code snippets across CERN GitLab repositories. "
        "Can search globally across all public projects or within a specific project. "
        "Returns matching files with line-level context. "
        "Useful for finding usage examples of specific libraries, functions, or patterns."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "search_term": {
                "type": "string",
                "description": "The code or text to search for",
            },
            "project": {
                "type": "string",
                "description": (
                    "Optional: limit search to a specific project. "
                    "Either a numeric ID or path (e.g. 'atlas/athena'). "
                    "If omitted, searches across all public projects."
                ),
            },
            "scope": {
                "type": "string",
                "enum": ["blobs", "filenames"],
                "description": (
                    "Search scope: 'blobs' searches file content (default), "
                    "'filenames' searches only file names"
                ),
            },
            "per_page": {
                "type": "integer",
                "description": "Number of results to return (default: 20, max: 100)",
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["search_term"],
    },
)


def _encode_project(project: str) -> str:
    """Encode a project path for use in GitLab API URLs."""
    if project.isdigit():
        return project
    return quote(project, safe="")


def _format_blob_result(item: dict[str, Any]) -> dict[str, Any]:
    """Format a single code search (blob) result."""
    return {
        "file_name": item.get("filename"),
        "file_path": item.get("path"),
        "project_id": item.get("project_id"),
        "data": item.get("data", ""),
        "ref": item.get("ref"),
        "startline": item.get("startline"),
    }


def _format_filename_result(item: dict[str, Any]) -> dict[str, Any]:
    """Format a single filename search result."""
    return {
        "file_name": item.get("filename"),
        "file_path": item.get("path"),
        "project_id": item.get("project_id"),
        "ref": item.get("ref"),
    }


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the search_code tool.

    Returns:
        Dict with search results and metadata.
    """
    search_term = arguments.get("search_term", "").strip()
    if not search_term:
        raise ValueError("'search_term' parameter is required")

    scope = arguments.get("scope", "blobs")
    if scope not in ("blobs", "filenames"):
        scope = "blobs"

    per_page = arguments.get("per_page", 20)
    per_page = max(1, min(per_page, 100))

    project = arguments.get("project", "").strip()

    params: dict[str, Any] = {
        "search": search_term,
        "scope": scope,
        "per_page": per_page,
    }

    if project:
        # Project-scoped search
        encoded_project = _encode_project(project)
        path = f"/projects/{encoded_project}/search"
    else:
        # Global search across all public projects
        path = "/search"

    try:
        results = await client.get(path, params=params)
    except AuthenticationError:
        return {
            "search_term": search_term,
            "scope": scope,
            "project": project or "(global)",
            "total_results": 0,
            "results": [],
            "error": (
                "Search API requires authentication on CERN GitLab. "
                "Set the CERNGITLAB_TOKEN environment variable with a personal access token "
                "that has the 'read_api' scope."
            ),
        }

    if not isinstance(results, list):
        results = []

    if scope == "blobs":
        formatted = [_format_blob_result(r) for r in results]
    else:
        formatted = [_format_filename_result(r) for r in results]

    return {
        "search_term": search_term,
        "scope": scope,
        "project": project or "(global)",
        "total_results": len(formatted),
        "results": formatted,
    }

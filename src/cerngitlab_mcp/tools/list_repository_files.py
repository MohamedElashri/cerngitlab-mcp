"""MCP tool: list_repository_files — browse the file tree of a CERN GitLab repository."""

from typing import Any
from urllib.parse import quote

from mcp.types import TextContent, Tool

from cerngitlab_mcp.gitlab_client import GitLabClient


TOOL_DEFINITION = Tool(
    name="list_repository_files",
    description=(
        "List files and directories in a CERN GitLab repository. "
        "Can browse from the root or a specific subdirectory. "
        "Useful for understanding project structure before fetching specific files."
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
            "path": {
                "type": "string",
                "description": "Directory path within the repository (default: root '/')",
            },
            "ref": {
                "type": "string",
                "description": "Branch name, tag, or commit SHA (default: project's default branch)",
            },
            "recursive": {
                "type": "boolean",
                "description": "If true, list files recursively (default: false)",
            },
            "per_page": {
                "type": "integer",
                "description": "Number of entries to return (default: 100, max: 100)",
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["project"],
    },
)


def _encode_project(project: str) -> str:
    """Encode a project path for use in GitLab API URLs."""
    if project.isdigit():
        return project
    return quote(project, safe="")


def _format_tree_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Format a single repository tree entry."""
    return {
        "name": entry.get("name"),
        "type": entry.get("type"),  # "blob" (file) or "tree" (directory)
        "path": entry.get("path"),
        "mode": entry.get("mode"),
    }


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the list_repository_files tool.

    Returns:
        Dict with the tree listing and metadata.
    """
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    encoded = _encode_project(project)

    params: dict[str, Any] = {}

    path = arguments.get("path", "").strip()
    if path:
        params["path"] = path

    ref = arguments.get("ref", "").strip()
    if ref:
        params["ref"] = ref

    if arguments.get("recursive", False):
        params["recursive"] = "true"

    per_page = arguments.get("per_page", 100)
    per_page = max(1, min(per_page, 100))
    params["per_page"] = per_page

    tree = await client.get(f"/projects/{encoded}/repository/tree", params=params)

    if not isinstance(tree, list):
        tree = []

    entries = [_format_tree_entry(e) for e in tree]

    # Separate directories and files for cleaner output
    directories = [e for e in entries if e["type"] == "tree"]
    files = [e for e in entries if e["type"] == "blob"]

    return {
        "project": project,
        "path": path or "/",
        "ref": ref or "(default branch)",
        "total_entries": len(entries),
        "directories": directories,
        "files": files,
    }

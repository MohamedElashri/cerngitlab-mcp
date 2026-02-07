"""MCP tool: get_release — get details of a specific release from a CERN GitLab repository."""

from typing import Any

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.exceptions import NotFoundError
from cerngitlab_mcp.tools.utils import encode_project


TOOL_DEFINITION = Tool(
    name="get_release",
    description=(
        "Get detailed information about a specific release from a CERN GitLab repository. "
        "Returns release notes, assets, commit info, and download links. "
        "Requires the tag name of the release."
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
            "tag_name": {
                "type": "string",
                "description": "The tag name of the release (e.g. 'v1.0.0')",
            },
        },
        "required": ["project", "tag_name"],
    },
)


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the get_release tool."""
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    tag_name = arguments.get("tag_name", "").strip()
    if not tag_name:
        raise ValueError("'tag_name' parameter is required")

    encoded_project = encode_project(project)

    try:
        data = await client.get(
            f"/projects/{encoded_project}/releases/{tag_name}",
        )
    except NotFoundError:
        return {
            "project": project,
            "tag_name": tag_name,
            "found": False,
            "error": f"Release '{tag_name}' not found",
        }

    # Format assets
    assets_data = data.get("assets") or {}
    links = [
        {"name": link.get("name"), "url": link.get("url"), "link_type": link.get("link_type")}
        for link in assets_data.get("links", [])
    ]
    sources = [
        {"format": s.get("format"), "url": s.get("url")}
        for s in assets_data.get("sources", [])
    ]

    # Commit info
    commit = data.get("commit") or {}

    return {
        "project": project,
        "found": True,
        "tag_name": data.get("tag_name"),
        "name": data.get("name"),
        "description": data.get("description", ""),
        "created_at": data.get("created_at"),
        "released_at": data.get("released_at"),
        "author": (data.get("author") or {}).get("username"),
        "commit": {
            "id": commit.get("id"),
            "short_id": commit.get("short_id"),
            "title": commit.get("title"),
            "created_at": commit.get("created_at"),
            "author_name": commit.get("author_name"),
        },
        "assets": {
            "links": links,
            "sources": sources,
        },
        "evidences": [
            {"sha": e.get("sha"), "collected_at": e.get("collected_at")}
            for e in (data.get("evidences") or [])
        ],
    }

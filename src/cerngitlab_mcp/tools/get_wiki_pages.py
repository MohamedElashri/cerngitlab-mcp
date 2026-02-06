"""MCP tool: get_wiki_pages — access repository wiki pages from CERN GitLab."""

from typing import Any
from urllib.parse import quote

from mcp.types import TextContent, Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.exceptions import NotFoundError, GitLabAPIError


TOOL_DEFINITION = Tool(
    name="get_wiki_pages",
    description=(
        "Access wiki pages from a CERN GitLab repository. "
        "Can list all wiki pages or retrieve the content of a specific page. "
        "Useful for accessing project documentation that lives in the wiki."
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
            "page_slug": {
                "type": "string",
                "description": (
                    "Optional: slug of a specific wiki page to retrieve. "
                    "If omitted, lists all wiki pages."
                ),
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


def _format_page_summary(page: dict[str, Any]) -> dict[str, Any]:
    """Format a wiki page summary (from list endpoint)."""
    return {
        "title": page.get("title"),
        "slug": page.get("slug"),
        "format": page.get("format"),
    }


def _format_page_detail(page: dict[str, Any]) -> dict[str, Any]:
    """Format a full wiki page (from detail endpoint)."""
    return {
        "title": page.get("title"),
        "slug": page.get("slug"),
        "format": page.get("format"),
        "content": page.get("content", ""),
        "encoding": page.get("encoding"),
    }


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the get_wiki_pages tool.

    Returns:
        Dict with wiki page(s) and metadata.
    """
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    encoded_project = _encode_project(project)
    page_slug = arguments.get("page_slug", "").strip()

    try:
        if page_slug:
            # Fetch a specific wiki page
            encoded_slug = quote(page_slug, safe="")
            data = await client.get(
                f"/projects/{encoded_project}/wikis/{encoded_slug}",
            )
            return {
                "project": project,
                "mode": "detail",
                "page": _format_page_detail(data),
            }
        else:
            # List all wiki pages
            data = await client.get(
                f"/projects/{encoded_project}/wikis",
                params={"with_content": "false"},
            )

            if not isinstance(data, list):
                data = []

            return {
                "project": project,
                "mode": "list",
                "total_pages": len(data),
                "pages": [_format_page_summary(p) for p in data],
            }

    except NotFoundError:
        return {
            "project": project,
            "error": "Wiki not found or not enabled for this project",
            "pages": [],
        }
    except GitLabAPIError as exc:
        if exc.status_code == 403:
            return {
                "project": project,
                "error": "Wiki access denied — may require authentication",
                "pages": [],
            }
        raise

"""MCP tool: get_repository_readme — retrieve README content from a CERN GitLab repository."""

import base64
from typing import Any
from urllib.parse import quote

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.exceptions import NotFoundError
from cerngitlab_mcp.tools.utils import encode_project, resolve_ref


# Common README filenames in order of preference
_README_CANDIDATES = [
    "README.md",
    "README.rst",
    "README.txt",
    "README",
    "readme.md",
    "readme.rst",
    "readme.txt",
    "Readme.md",
]


TOOL_DEFINITION = Tool(
    name="get_project_readme",
    description=(
        "Get the README file content for a CERN GitLab project. "
        "Automatically detects standard README filenames (README.md, README.rst, etc.). "
        "Returns the raw content — useful for understanding what a project does."
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
            "ref": {
                "type": "string",
                "description": "Branch name, tag, or commit SHA (default: project's default branch)",
            },
        },
        "required": ["project"],
    },
)


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the get_repository_readme tool.

    Tries multiple README filename candidates until one is found.

    Returns:
        Dict with README content and metadata.
    """
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    encoded_project = encode_project(project)

    ref = arguments.get("ref", "").strip()
    ref = await resolve_ref(client, encoded_project, ref)

    # Try each README candidate
    for readme_name in _README_CANDIDATES:
        encoded_path = quote(readme_name, safe="")
        try:
            data = await client.get(
                f"/projects/{encoded_project}/repository/files/{encoded_path}",
                params={"ref": ref},
            )

            content_encoded = data.get("content", "")
            encoding = data.get("encoding", "base64")

            if encoding == "base64" and content_encoded:
                try:
                    content = base64.b64decode(content_encoded).decode("utf-8")
                except (UnicodeDecodeError, ValueError):
                    content = content_encoded
            else:
                content = content_encoded

            return {
                "file_name": data.get("file_name", readme_name),
                "file_path": data.get("file_path", readme_name),
                "ref": data.get("ref", ref or "(default branch)"),
                "size": data.get("size", 0),
                "content": content,
                "format": _detect_format(readme_name),
            }

        except NotFoundError:
            continue

    # None found
    return {
        "error": "No README file found",
        "tried": _README_CANDIDATES,
        "content": None,
    }


def _detect_format(filename: str) -> str:
    """Detect the markup format of a README file."""
    lower = filename.lower()
    if lower.endswith(".md"):
        return "markdown"
    if lower.endswith(".rst"):
        return "restructuredtext"
    if lower.endswith(".txt"):
        return "plaintext"
    return "plaintext"

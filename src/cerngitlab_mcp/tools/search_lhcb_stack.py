"""MCP tool: search_lhcb_stack — search for code across LHCb stack projects."""

from typing import Any

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.stack_resolver import resolve_stack
from cerngitlab_mcp.tools import search_code


TOOL_DEFINITION = Tool(
    name="search_lhcb_stack",
    description=(
        "Search for code snippets within a specific LHCb software stack (e.g., 'sim11'). "
        "Automatically resolves the correct Git references for projects in that stack."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "search_term": {
                "type": "string",
                "description": "The code or text to search for",
            },
            "stack": {
                "type": "string",
                "description": "Name of the software stack (e.g., 'sim11')",
            },
            "project": {
                "type": "string",
                "description": (
                    "Optional: limit search to a specific project. "
                    "Either a numeric ID or path (e.g. 'lhcb/Boole'). "
                    "If omitted, searches across all public projects using default refs."
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
            "ref": {
                "type": "string",
                "description": (
                    "Optional: Override the Git branch or tag to search within. "
                    "If omitted, automatically uses the branch matching the stack if applicable."
                ),
            },
            "per_page": {
                "type": "integer",
                "description": "Number of results to return (default: 20, max: 100)",
                "minimum": 1,
                "maximum": 100,
            },
            "page": {
                "type": "integer",
                "description": "Page number to retrieve (default: 1)",
                "minimum": 1,
            },
        },
        "required": ["search_term", "stack"],
    },
)


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the search_lhcb_stack tool.

    Delegates to the search_code tool with correctly resolved refs.
    """
    stack = arguments.get("stack", "").strip()
    if not stack:
        raise ValueError("'stack' parameter is required")

    resolved_stack_map = await resolve_stack(stack)
    project = arguments.get("project", "").strip()
    explicit_ref = arguments.get("ref", "").strip()

    # Determine the ref
    ref = explicit_ref
    if not ref and project:
        project_name = project.split("/")[-1] if "/" in project else project
        if resolved_stack_map and project_name in resolved_stack_map:
            ref = resolved_stack_map[project_name]

    # Prepare arguments for search_code
    search_args = {**arguments}
    search_args.pop("stack", None)  # remove stack before passing to generic tool

    if ref:
        search_args["ref"] = ref

    return await search_code.handle(client, search_args)

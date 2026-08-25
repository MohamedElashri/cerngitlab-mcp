"""Transport-agnostic MCP server core containing all business logic.

Two surfaces are provided:

- ``build_mcp_server``: builds an ``mcp.server.MCPServer`` (the SDK's
  high-level server, MCP protocol 2026-07-28) with every tool registered
  through the decorator API. Tool schemas are generated from type hints,
  and tools carry annotations (read-only hints) per the 2025-11-25+ spec.
- ``McpServerCore``: transport-agnostic dispatch retained for the legacy
  REST endpoints exposed by the HTTP transport.
"""

import json
import logging
from typing import Annotated, Any, List, Literal

from pydantic import Field

from mcp import MCPError
from mcp.server import MCPServer
from mcp.types import TextContent, Tool, ToolAnnotations

from cerngitlab_mcp.tools import (
    get_file_content,
    get_release,
    get_project_info,
    get_project_readme,
    get_wiki_pages,
    inspect_project,
    list_branches,
    list_releases,
    list_project_files,
    list_tags,
    search_code,
    search_lhcb_stack,
    search_issues,
    search_projects,
)
from cerngitlab_mcp.config import Settings
from cerngitlab_mcp.exceptions import CERNGitLabError
from cerngitlab_mcp.gitlab_client import GitLabClient


logger = logging.getLogger("cerngitlab_mcp")

SERVER_VERSION = "1.0.0"

# All tools in this server only read from GitLab.
_READ_ONLY_ANNOTATIONS = ToolAnnotations(read_only_hint=True)
_OPEN_WORLD_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    open_world_hint=True,
)

ProjectId = Annotated[
    str,
    Field(
        description=(
            "Project identifier — either a numeric ID (e.g. '12345') or a "
            "URL-encoded path (e.g. 'atlas/athena')"
        )
    ),
]
OptionalRef = Annotated[
    str,
    Field(
        description="Branch name, tag, or commit SHA (default: project's default branch)"
    ),
]


def _raise_tool_error(exc: Exception) -> None:
    """Convert known tool errors into MCPError (JSON-RPC error responses)."""
    if isinstance(exc, ValueError):
        raise MCPError(code=-32602, message=str(exc)) from exc
    if isinstance(exc, CERNGitLabError):
        raise MCPError(code=-32000, message=exc.message) from exc
    raise exc


async def _dispatch(tool_module: Any, client: GitLabClient, arguments: dict) -> Any:
    try:
        return await tool_module.handle(client, arguments)
    except (ValueError, CERNGitLabError) as exc:
        _raise_tool_error(exc)


def build_mcp_server(settings: Settings, gitlab_client: GitLabClient) -> MCPServer:
    """Build an MCPServer instance with all GitLab tools registered.

    Args:
        settings: Server configuration settings
        gitlab_client: GitLab API client used by all tools

    Returns:
        A configured MCPServer speaking protocol revision 2026-07-28
        (with backward compatibility for older clients).
    """
    mcp = MCPServer(
        "cerngitlab-mcp",
        title="CERN GitLab MCP Server",
        description=(
            "Code discovery, documentation access, and usage examples "
            "for CERN HEP projects"
        ),
        version=SERVER_VERSION,
        instructions=(
            "Use these tools to discover and inspect CERN GitLab projects: "
            "search for projects, read files, READMEs, wikis, releases, and "
            "search code and issues. All tools are read-only."
        ),
    )

    @mcp.tool(
        name="test_connectivity",
        description=(
            "Test connectivity to the CERN GitLab instance. Returns the "
            "GitLab version, authentication status, and connection health."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    async def test_connectivity() -> dict[str, Any]:
        return await gitlab_client.test_connection()

    @mcp.tool(
        name="search_projects",
        description=search_projects.TOOL_DEFINITION.description,
        annotations=_OPEN_WORLD_ANNOTATIONS,
    )
    async def search_projects_fn(
        query: Annotated[
            str,
            Field(
                description="Search query string (matches project name, description, etc.)"
            ),
        ] = "",
        language: Annotated[
            str,
            Field(
                description="Filter by primary programming language (e.g. 'python', 'c++', 'java')"
            ),
        ] = "",
        topic: Annotated[
            str,
            Field(
                description="Filter by project topic/tag (e.g. 'physics', 'root', 'atlas')"
            ),
        ] = "",
        sort_by: Annotated[
            Literal["last_activity_at", "name", "created_at", "updated_at", "stars"],
            Field(description="Sort results by this field"),
        ] = "last_activity_at",
        order: Annotated[
            Literal["desc", "asc"],
            Field(description="Sort order"),
        ] = "desc",
        per_page: Annotated[
            int, Field(ge=1, le=100, description="Number of results to return")
        ] = 20,
    ) -> list[dict[str, Any]]:
        return await _dispatch(
            search_projects,
            gitlab_client,
            {
                "query": query,
                "language": language,
                "topic": topic,
                "sort_by": sort_by,
                "order": order,
                "per_page": per_page,
            },
        )

    @mcp.tool(
        name="get_project_info",
        description=get_project_info.TOOL_DEFINITION.description,
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    async def get_project_info_fn(project: ProjectId) -> dict[str, Any]:
        return await _dispatch(get_project_info, gitlab_client, {"project": project})

    @mcp.tool(
        name="list_project_files",
        description=list_project_files.TOOL_DEFINITION.description,
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    async def list_project_files_fn(
        project: ProjectId,
        path: Annotated[
            str,
            Field(
                description="Directory path within the repository (default: root '/')"
            ),
        ] = "",
        ref: OptionalRef = "",
        recursive: Annotated[
            bool, Field(description="If true, list files recursively")
        ] = False,
        per_page: Annotated[
            int, Field(ge=1, le=100, description="Number of entries to return")
        ] = 100,
    ) -> dict[str, Any]:
        return await _dispatch(
            list_project_files,
            gitlab_client,
            {
                "project": project,
                "path": path,
                "ref": ref,
                "recursive": recursive,
                "per_page": per_page,
            },
        )

    @mcp.tool(
        name="get_file_content",
        description=get_file_content.TOOL_DEFINITION.description,
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    async def get_file_content_fn(
        project: ProjectId,
        file_path: Annotated[
            str,
            Field(
                description="Path to the file within the repository (e.g. 'src/main.py')"
            ),
        ],
        ref: OptionalRef = "",
    ) -> dict[str, Any]:
        return await _dispatch(
            get_file_content,
            gitlab_client,
            {"project": project, "file_path": file_path, "ref": ref},
        )

    @mcp.tool(
        name="get_project_readme",
        description=get_project_readme.TOOL_DEFINITION.description,
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    async def get_project_readme_fn(
        project: ProjectId, ref: OptionalRef = ""
    ) -> dict[str, Any]:
        return await _dispatch(
            get_project_readme,
            gitlab_client,
            {"project": project, "ref": ref},
        )

    @mcp.tool(
        name="search_code",
        description=search_code.TOOL_DEFINITION.description,
        annotations=_OPEN_WORLD_ANNOTATIONS,
    )
    async def search_code_fn(
        search_term: Annotated[
            str, Field(description="The code or text to search for")
        ],
        project: Annotated[
            str,
            Field(
                description="Optional: limit search to a specific project (ID or path). If omitted, searches across all public projects."
            ),
        ] = "",
        scope: Annotated[
            Literal["blobs", "filenames"],
            Field(
                description="'blobs' searches file content (default), 'filenames' searches only file names"
            ),
        ] = "blobs",
        ref: Annotated[
            str,
            Field(description="Optional: Git branch or tag to search within"),
        ] = "",
        per_page: Annotated[
            int, Field(ge=1, le=100, description="Number of results to return")
        ] = 20,
        page: Annotated[int, Field(ge=1, description="Page number to retrieve")] = 1,
    ) -> dict[str, Any]:
        return await _dispatch(
            search_code,
            gitlab_client,
            {
                "search_term": search_term,
                "project": project,
                "scope": scope,
                "ref": ref,
                "per_page": per_page,
                "page": page,
            },
        )

    @mcp.tool(
        name="search_lhcb_stack",
        description=search_lhcb_stack.TOOL_DEFINITION.description,
        annotations=_OPEN_WORLD_ANNOTATIONS,
    )
    async def search_lhcb_stack_fn(
        search_term: Annotated[
            str, Field(description="The code or text to search for")
        ],
        stack: Annotated[
            str, Field(description="Name of the software stack (e.g. 'sim11')")
        ],
        project: Annotated[
            str,
            Field(
                description="Optional: limit search to a specific project (ID or path). If omitted, searches across all public projects using default refs."
            ),
        ] = "",
        scope: Annotated[
            Literal["blobs", "filenames"],
            Field(
                description="'blobs' searches file content (default), 'filenames' searches only file names"
            ),
        ] = "blobs",
        ref: Annotated[
            str,
            Field(
                description="Optional: Override the Git branch or tag to search within. If omitted, uses the branch matching the stack."
            ),
        ] = "",
        per_page: Annotated[
            int, Field(ge=1, le=100, description="Number of results to return")
        ] = 20,
        page: Annotated[int, Field(ge=1, description="Page number to retrieve")] = 1,
    ) -> dict[str, Any]:
        return await _dispatch(
            search_lhcb_stack,
            gitlab_client,
            {
                "search_term": search_term,
                "stack": stack,
                "project": project,
                "scope": scope,
                "ref": ref,
                "per_page": per_page,
                "page": page,
            },
        )

    @mcp.tool(
        name="search_issues",
        description=search_issues.TOOL_DEFINITION.description,
        annotations=_OPEN_WORLD_ANNOTATIONS,
    )
    async def search_issues_fn(
        search_term: Annotated[
            str,
            Field(
                description="Keywords to search for in issue titles and descriptions"
            ),
        ],
        project: Annotated[
            str,
            Field(
                description="Optional: limit search to a specific project. If omitted, searches across all projects you have access to."
            ),
        ] = "",
        state: Annotated[
            Literal["opened", "closed", "all"],
            Field(description="Filter by issue state"),
        ] = "all",
        per_page: Annotated[
            int, Field(ge=1, le=100, description="Number of results to return")
        ] = 10,
    ) -> dict[str, Any]:
        return await _dispatch(
            search_issues,
            gitlab_client,
            {
                "search_term": search_term,
                "project": project,
                "state": state,
                "per_page": per_page,
            },
        )

    @mcp.tool(
        name="get_wiki_pages",
        description=get_wiki_pages.TOOL_DEFINITION.description,
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    async def get_wiki_pages_fn(
        project: ProjectId,
        page_slug: Annotated[
            str,
            Field(
                description="Optional: slug of a specific wiki page to retrieve. If omitted, lists all wiki pages."
            ),
        ] = "",
    ) -> dict[str, Any]:
        return await _dispatch(
            get_wiki_pages,
            gitlab_client,
            {"project": project, "page_slug": page_slug},
        )

    @mcp.tool(
        name="inspect_project",
        description=inspect_project.TOOL_DEFINITION.description,
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    async def inspect_project_fn(
        project: ProjectId, ref: OptionalRef = ""
    ) -> dict[str, Any]:
        return await _dispatch(
            inspect_project,
            gitlab_client,
            {"project": project, "ref": ref},
        )

    @mcp.tool(
        name="list_branches",
        description=list_branches.TOOL_DEFINITION.description,
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    async def list_branches_fn(
        project: ProjectId,
        search: Annotated[
            str,
            Field(
                description="Optional branch-name filter. GitLab supports partial matches and anchors such as '^main$' for an exact match."
            ),
        ] = "",
        page: Annotated[int, Field(ge=1, description="Page number to retrieve")] = 1,
        per_page: Annotated[
            int, Field(ge=1, le=100, description="Number of branches to return")
        ] = 20,
    ) -> dict[str, Any]:
        return await _dispatch(
            list_branches,
            gitlab_client,
            {
                "project": project,
                "search": search,
                "page": page,
                "per_page": per_page,
            },
        )

    @mcp.tool(
        name="list_releases",
        description=list_releases.TOOL_DEFINITION.description,
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    async def list_releases_fn(
        project: ProjectId,
        per_page: Annotated[
            int, Field(ge=1, le=100, description="Number of releases to return")
        ] = 20,
    ) -> dict[str, Any]:
        return await _dispatch(
            list_releases,
            gitlab_client,
            {"project": project, "per_page": per_page},
        )

    @mcp.tool(
        name="get_release",
        description=get_release.TOOL_DEFINITION.description,
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    async def get_release_fn(
        project: ProjectId,
        tag_name: Annotated[
            str, Field(description="The tag name of the release (e.g. 'v1.0.0')")
        ],
    ) -> dict[str, Any]:
        return await _dispatch(
            get_release,
            gitlab_client,
            {"project": project, "tag_name": tag_name},
        )

    @mcp.tool(
        name="list_tags",
        description=list_tags.TOOL_DEFINITION.description,
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    async def list_tags_fn(
        project: ProjectId,
        search: Annotated[
            str,
            Field(
                description="Optional: filter tags by name (e.g. 'v1' to find all v1.x tags)"
            ),
        ] = "",
        sort: Annotated[
            Literal["asc", "desc"],
            Field(description="Sort order by tag name (default: desc — newest first)"),
        ] = "desc",
        per_page: Annotated[
            int, Field(ge=1, le=100, description="Number of tags to return")
        ] = 20,
    ) -> dict[str, Any]:
        return await _dispatch(
            list_tags,
            gitlab_client,
            {
                "project": project,
                "search": search,
                "sort": sort,
                "per_page": per_page,
            },
        )

    return mcp


class McpServerCore:
    """Transport-agnostic dispatch retained for the legacy REST endpoints.

    The MCP-protocol surface lives in :func:`build_mcp_server`; this class
    only backs the plain HTTP JSON API in ``transports/http.py``.
    """

    def __init__(self, settings: Settings, gitlab_client: GitLabClient):
        """Initialize the MCP server core.

        Args:
            settings: Server configuration settings
            gitlab_client: GitLab API client instance
        """
        self.settings = settings
        self.gitlab_client = gitlab_client
        self._tool_handlers = self._setup_tool_handlers()

    def _setup_tool_handlers(self) -> dict[str, Any]:
        """Set up the mapping of tool names to their handlers."""
        return {
            "test_connectivity": "_handle_test_connectivity",
            "search_projects": search_projects,
            "get_project_info": get_project_info,
            "list_project_files": list_project_files,
            "get_file_content": get_file_content,
            "get_project_readme": get_project_readme,
            "search_code": search_code,
            "search_lhcb_stack": search_lhcb_stack,
            "search_issues": search_issues,
            "get_wiki_pages": get_wiki_pages,
            "inspect_project": inspect_project,
            "list_branches": list_branches,
            "list_releases": list_releases,
            "get_release": get_release,
            "list_tags": list_tags,
        }

    def get_tool_definitions(self) -> List[Tool]:
        """Return the list of available tools."""
        test_connectivity_tool = Tool(
            name="test_connectivity",
            description=(
                "Test connectivity to the CERN GitLab instance. "
                "Returns the GitLab version, authentication status, and connection health."
            ),
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

        return [
            test_connectivity_tool,
            search_projects.TOOL_DEFINITION,
            get_project_info.TOOL_DEFINITION,
            list_project_files.TOOL_DEFINITION,
            get_file_content.TOOL_DEFINITION,
            get_project_readme.TOOL_DEFINITION,
            search_code.TOOL_DEFINITION,
            search_lhcb_stack.TOOL_DEFINITION,
            search_issues.TOOL_DEFINITION,
            get_wiki_pages.TOOL_DEFINITION,
            inspect_project.TOOL_DEFINITION,
            list_branches.TOOL_DEFINITION,
            list_releases.TOOL_DEFINITION,
            get_release.TOOL_DEFINITION,
            list_tags.TOOL_DEFINITION,
        ]

    async def handle_tool_call(self, name: str, arguments: dict) -> dict:
        """Handle MCP tool calls in a transport-agnostic way.

        Args:
            name: Name of the tool to call
            arguments: Tool arguments dictionary

        Returns:
            Dictionary containing the tool result or error information
        """
        try:
            if name == "test_connectivity":
                result = await self.gitlab_client.test_connection()
                return {"success": True, "data": result}

            handler_module = self._tool_handlers.get(name)
            if handler_module and handler_module != "_handle_test_connectivity":
                if hasattr(handler_module, "handle"):
                    result = await handler_module.handle(self.gitlab_client, arguments)
                else:
                    return {
                        "success": False,
                        "error": f"Invalid handler for tool: {name}",
                    }
                return {"success": True, "data": result}

            return {"success": False, "error": f"Unknown tool: {name}"}

        except CERNGitLabError as exc:
            logger.error("Tool %s failed: %s", name, exc.message)
            return {"success": False, "error": exc.message}
        except ValueError as exc:
            logger.warning("Tool %s bad input: %s", name, exc)
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.exception("Unexpected error in tool %s", name)
            return {"success": False, "error": f"Internal error: {exc}"}

    def format_success_response(self, data: dict | list) -> List[TextContent]:
        """Format a successful tool response for MCP transport."""
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    def format_error_response(self, message: str) -> List[TextContent]:
        """Format an error response for MCP transport."""
        return [TextContent(type="text", text=json.dumps({"error": message}))]

    async def close(self) -> None:
        """Clean up resources."""
        if self.gitlab_client:
            await self.gitlab_client.close()

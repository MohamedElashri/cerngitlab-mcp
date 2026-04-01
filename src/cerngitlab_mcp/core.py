"""Transport-agnostic MCP server core containing all business logic."""

import json
import logging
from typing import Dict, List

from mcp.types import TextContent, Tool

from cerngitlab_mcp.config import Settings
from cerngitlab_mcp.exceptions import CERNGitLabError
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.tools import (
    get_file_content,
    get_release,
    get_project_info,
    get_project_readme,
    get_wiki_pages,
    inspect_project,
    list_releases,
    list_project_files,
    list_tags,
    search_code,
    search_lhcb_stack,
    search_issues,
    search_projects,
)


logger = logging.getLogger("cerngitlab_mcp")


class McpServerCore:
    """Transport-agnostic MCP server core containing all business logic.
    
    This class handles all MCP tool operations independent of the transport layer
    (stdio, HTTP, etc.). It manages a GitLab client instance and provides methods
    for tool discovery and execution.
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

    def _setup_tool_handlers(self) -> Dict[str, any]:
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
            inputSchema={
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
            
        Raises:
            CERNGitLabError: For GitLab-specific errors
            ValueError: For invalid tool arguments
            Exception: For unexpected errors
        """
        try:
            if name == "test_connectivity":
                result = await self.gitlab_client.test_connection()
                return {"success": True, "data": result}

            handler_module = self._tool_handlers.get(name)
            if handler_module and handler_module != "_handle_test_connectivity":
                result = await handler_module.handle(self.gitlab_client, arguments)
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

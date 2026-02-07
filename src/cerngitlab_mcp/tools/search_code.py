"""MCP tool: search_code — search for code across CERN GitLab repositories."""

import base64
import re
from typing import Any
from urllib.parse import quote

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.exceptions import AuthenticationError, GitLabAPIError, NotFoundError


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


_TEXT_EXTENSIONS = {
    ".py", ".pyx", ".pxd", ".cpp", ".cxx", ".cc", ".c", ".h", ".hpp", ".hxx",
    ".f", ".f90", ".f95", ".f03", ".for",
    ".cmake", ".txt", ".md", ".rst", ".cfg", ".ini", ".toml", ".yaml", ".yml",
    ".json", ".xml", ".sh", ".bash", ".zsh",
    ".java", ".go", ".rs", ".js", ".ts", ".rb", ".pl",
    ".dockerfile", ".makefile",
}

_TEXT_FILENAMES = {
    "CMakeLists.txt", "Makefile", "Dockerfile", "SConstruct", "SConscript",
    "Jenkinsfile", "Rakefile", "Gemfile", "wscript",
    ".gitlab-ci.yml", ".gitignore", ".gitattributes",
}


def _is_searchable(path: str) -> bool:
    """Check if a file is likely a text file worth searching."""
    name = path.rsplit("/", 1)[-1] if "/" in path else path
    if name in _TEXT_FILENAMES:
        return True
    dot = name.rfind(".")
    if dot >= 0:
        return name[dot:].lower() in _TEXT_EXTENSIONS
    return False


async def _fallback_project_search(
    client: GitLabClient,
    encoded_project: str,
    search_term: str,
    per_page: int,
    project_display: str,
) -> dict[str, Any]:
    """Search within a project by listing files and grepping content.

    Used as a fallback when the GitLab instance does not support
    advanced search (scope=blobs returns 400).
    """
    # Get the recursive file tree (limit to 500 files to avoid huge repos)
    try:
        tree = await client.get(
            f"/projects/{encoded_project}/repository/tree",
            params={"recursive": "true", "per_page": 500},
        )
    except Exception:
        return {
            "search_term": search_term,
            "scope": "blobs",
            "project": project_display,
            "total_results": 0,
            "results": [],
            "error": "Could not list repository files for fallback search.",
        }

    if not isinstance(tree, list):
        tree = []

    # Filter to searchable text files
    files = [e["path"] for e in tree if e.get("type") == "blob" and _is_searchable(e["path"])]

    results: list[dict[str, Any]] = []
    pattern = re.compile(re.escape(search_term), re.IGNORECASE)

    for file_path in files:
        if len(results) >= per_page:
            break
        encoded_path = quote(file_path, safe="")
        try:
            data = await client.get(
                f"/projects/{encoded_project}/repository/files/{encoded_path}",
                params={"ref": "HEAD"},
            )
        except (NotFoundError, GitLabAPIError):
            continue

        content_b64 = data.get("content", "")
        encoding = data.get("encoding", "base64")
        try:
            if encoding == "base64" and content_b64:
                content = base64.b64decode(content_b64).decode("utf-8")
            else:
                content = content_b64
        except (UnicodeDecodeError, Exception):
            continue

        # Find matching lines
        for i, line in enumerate(content.splitlines(), 1):
            if pattern.search(line):
                # Extract a small context window around the match
                start = max(1, i - 2)
                end = i + 2
                snippet_lines = content.splitlines()[start - 1 : end]
                snippet = "\n".join(snippet_lines)
                results.append({
                    "file_name": file_path.rsplit("/", 1)[-1],
                    "file_path": file_path,
                    "project_id": None,
                    "data": snippet,
                    "ref": data.get("ref", "HEAD"),
                    "startline": start,
                })
                break  # One match per file

        if len(results) >= per_page:
            break

    return {
        "search_term": search_term,
        "scope": "blobs",
        "project": project_display,
        "total_results": len(results),
        "results": results,
        "note": (
            f"Fallback search (advanced search not available). "
            f"Scanned {len(files)} text files."
        ),
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
    except GitLabAPIError as exc:
        if exc.status_code == 400 and "scope" in str(exc).lower():
            # GitLab instance does not have advanced search enabled.
            # Project-scoped blob search requires it on some instances.
            if project:
                return await _fallback_project_search(
                    client, encoded_project, search_term, per_page, project,
                )
            return {
                "search_term": search_term,
                "scope": scope,
                "project": "(global)",
                "total_results": 0,
                "results": [],
                "error": (
                    "Global code search requires advanced search (Elasticsearch) "
                    "which is not enabled on this GitLab instance. "
                    "Use the 'project' parameter to search within a specific project instead."
                ),
            }
        raise

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

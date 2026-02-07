"""MCP tool: get_build_config — retrieve build configuration files from a CERN GitLab repository."""

from typing import Any

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.tools.utils import encode_project, resolve_ref, fetch_file


# Build config files to look for, in priority order
_BUILD_FILES: list[dict[str, str]] = [
    {"file": "CMakeLists.txt", "build_system": "cmake", "language": "cmake"},
    {"file": "Makefile", "build_system": "make", "language": "makefile"},
    {"file": "setup.py", "build_system": "setuptools", "language": "python"},
    {"file": "setup.cfg", "build_system": "setuptools", "language": "ini"},
    {"file": "pyproject.toml", "build_system": "python-build", "language": "toml"},
    {"file": "SConstruct", "build_system": "scons", "language": "python"},
    {"file": "SConscript", "build_system": "scons", "language": "python"},
    {"file": "wscript", "build_system": "waf", "language": "python"},
    {"file": "Dockerfile", "build_system": "docker", "language": "dockerfile"},
]


TOOL_DEFINITION = Tool(
    name="get_build_config",
    description=(
        "Retrieve build configuration files from a CERN GitLab repository. "
        "Searches for common build system files: CMakeLists.txt, Makefile, "
        "setup.py, pyproject.toml, meson.build, Dockerfile, etc. "
        "Returns the content of all found build files with metadata about "
        "the detected build system."
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
    """Execute the get_build_config tool.

    Returns:
        Dict with found build configuration files and their contents.
    """
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    encoded_project = encode_project(project)
    ref = arguments.get("ref", "").strip()
    ref = await resolve_ref(client, encoded_project, ref)

    found_files: list[dict[str, Any]] = []
    build_systems: list[str] = []

    for entry in _BUILD_FILES:
        content = await fetch_file(client, encoded_project, entry["file"], ref)
        if content is None:
            continue

        build_systems.append(entry["build_system"])
        found_files.append({
            "file": entry["file"],
            "build_system": entry["build_system"],
            "language": entry["language"],
            "size": len(content),
            "content": content,
        })

    return {
        "project": project,
        "ref": ref,
        "build_systems_detected": list(dict.fromkeys(build_systems)),
        "files_found": len(found_files),
        "build_files": found_files,
    }

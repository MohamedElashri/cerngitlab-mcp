"""MCP tool: analyze_dependencies — parse dependency files from a CERN GitLab repository."""

import re
from typing import Any

from mcp.types import TextContent, Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.tools.utils import encode_project, resolve_ref, fetch_file


# Dependency files to look for, grouped by ecosystem
_DEPENDENCY_FILES: dict[str, list[str]] = {
    "python": [
        "requirements.txt",
        "requirements-dev.txt",
        "requirements_dev.txt",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "conda.yaml",
        "environment.yml",
    ],
    "cpp": [
        "CMakeLists.txt",
        "conanfile.txt",
        "conanfile.py",
        "vcpkg.json",
    ],
    "fortran": [
        "CMakeLists.txt",
    ],
}


TOOL_DEFINITION = Tool(
    name="analyze_dependencies",
    description=(
        "Analyze dependency files from a CERN GitLab repository. "
        "Automatically detects and parses common dependency formats: "
        "requirements.txt, pyproject.toml, setup.py, CMakeLists.txt, "
        "and more. Focused on HEP-relevant ecosystems (Python, C++, Fortran). "
        "Returns a structured list of dependencies per file found."
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


def _parse_requirements_txt(content: str) -> list[dict[str, str]]:
    """Parse a requirements.txt file."""
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle inline comments
        line = line.split("#")[0].strip()
        if not line:
            continue
        # Parse name and version spec
        match = re.match(r"^([a-zA-Z0-9_.-]+)\s*(.*)?$", line)
        if match:
            name = match.group(1)
            version = match.group(2).strip() if match.group(2) else ""
            deps.append({"name": name, "version_spec": version})
    return deps


def _parse_pyproject_toml(content: str) -> list[dict[str, str]]:
    """Parse dependencies from pyproject.toml (basic parser, no toml lib needed)."""
    deps = []
    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        # Detect [project] dependencies = [...] or [tool.poetry.dependencies]
        if re.match(r"^dependencies\s*=\s*\[", stripped) or re.match(r"^\[tool\.poetry\.dependencies\]", stripped):
            in_deps = True
            # Handle inline list
            inline = re.search(r"\[(.+)\]", stripped)
            if inline:
                for item in inline.group(1).split(","):
                    item = item.strip().strip('"').strip("'")
                    if item:
                        match = re.match(r"^([a-zA-Z0-9_.-]+)(.*)?$", item)
                        if match:
                            deps.append({"name": match.group(1), "version_spec": (match.group(2) or "").strip()})
                in_deps = False
            continue
        if in_deps:
            if stripped == "]":
                in_deps = False
                continue
            if stripped.startswith("#"):
                continue
            item = stripped.strip(",").strip('"').strip("'")
            if item:
                match = re.match(r"^([a-zA-Z0-9_.-]+)(.*)?$", item)
                if match:
                    deps.append({"name": match.group(1), "version_spec": (match.group(2) or "").strip()})
    return deps


def _parse_cmake_find_package(content: str) -> list[dict[str, str]]:
    """Extract find_package() calls from CMakeLists.txt."""
    deps = []
    for match in re.finditer(r"find_package\s*\(\s*([a-zA-Z0-9_]+)(?:\s+([0-9][^\s)]*))?\s*", content):
        name = match.group(1)
        version = match.group(2) or ""
        deps.append({"name": name, "version_spec": version})
    return deps


_PARSERS: dict[str, Any] = {
    "requirements.txt": _parse_requirements_txt,
    "requirements-dev.txt": _parse_requirements_txt,
    "requirements_dev.txt": _parse_requirements_txt,
    "pyproject.toml": _parse_pyproject_toml,
    "CMakeLists.txt": _parse_cmake_find_package,
}


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the analyze_dependencies tool.

    Returns:
        Dict with discovered dependency files and parsed dependencies.
    """
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    encoded_project = encode_project(project)
    ref = arguments.get("ref", "").strip()
    ref = await resolve_ref(client, encoded_project, ref)

    results: list[dict[str, Any]] = []
    ecosystems_found: list[str] = []

    for ecosystem, files in _DEPENDENCY_FILES.items():
        for file_path in files:
            content = await fetch_file(client, encoded_project, file_path, ref)
            if content is None:
                continue

            ecosystems_found.append(ecosystem)
            parser = _PARSERS.get(file_path)
            if parser:
                parsed_deps = parser(content)
            else:
                parsed_deps = []

            results.append({
                "file": file_path,
                "ecosystem": ecosystem,
                "dependencies_count": len(parsed_deps),
                "dependencies": parsed_deps,
                "raw_content_preview": content[:500] if not parsed_deps else None,
            })

    return {
        "project": project,
        "ref": ref,
        "ecosystems_detected": list(set(ecosystems_found)),
        "files_found": len(results),
        "dependency_files": results,
    }

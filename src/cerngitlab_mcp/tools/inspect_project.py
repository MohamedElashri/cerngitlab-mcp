"""MCP tool: inspect_project — unified analysis of a CERN GitLab repository."""

import asyncio
import logging
import re
from typing import Any

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.tools.utils import encode_project, resolve_ref, fetch_file


logger = logging.getLogger("cerngitlab_mcp")


TOOL_DEFINITION = Tool(
    name="inspect_project",
    description=(
        "Analyze a CERN GitLab repository to understand its structure, build system, "
        "and dependencies. Combines functionality of dependency analysis, build config "
        "detection, and CI/CD inspection into a single tool. "
        "Returns a comprehensive summary of the project's technical stack."
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


# ---------------------------------------------------------------------------
# Dependency Analysis Logic
# ---------------------------------------------------------------------------

_DEPENDENCY_FILES: dict[str, list[str]] = {
    "python": [
        "requirements.txt", "requirements-dev.txt", "pyproject.toml",
        "setup.py", "Pipfile", "conda.yaml", "environment.yml",
    ],
    "cpp": ["CMakeLists.txt", "conanfile.txt", "vcpkg.json"],
    "fortran": ["CMakeLists.txt"],
}

def _parse_requirements_txt(content: str) -> list[dict[str, str]]:
    """Parse a requirements.txt file."""
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        line = line.split("#")[0].strip()
        if not line:
            continue
        match = re.match(r"^([a-zA-Z0-9_.-]+)\s*(.*)?$", line)
        if match:
            deps.append({"name": match.group(1), "version_spec": (match.group(2) or "").strip()})
    return deps

def _parse_pyproject_toml(content: str) -> list[dict[str, str]]:
    """Parse dependencies from pyproject.toml."""
    deps = []
    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        if re.match(r"^dependencies\s*=\s*\[", stripped) or re.match(r"^\[tool\.poetry\.dependencies\]", stripped):
            in_deps = True
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

_DEP_PARSERS: dict[str, Any] = {
    "requirements.txt": _parse_requirements_txt,
    "requirements-dev.txt": _parse_requirements_txt,
    "pyproject.toml": _parse_pyproject_toml,
    "CMakeLists.txt": _parse_cmake_find_package,
}


# ---------------------------------------------------------------------------
# Build Config Logic
# ---------------------------------------------------------------------------

_BUILD_FILES: list[dict[str, str]] = [
    {"file": "CMakeLists.txt", "build_system": "cmake", "language": "cmake"},
    {"file": "Makefile", "build_system": "make", "language": "makefile"},
    {"file": "setup.py", "build_system": "setuptools", "language": "python"},
    {"file": "pyproject.toml", "build_system": "python-build", "language": "toml"},
    {"file": "Dockerfile", "build_system": "docker", "language": "dockerfile"},
]


# ---------------------------------------------------------------------------
# CI Logic
# ---------------------------------------------------------------------------

def _analyze_ci_yaml(content: str) -> dict[str, Any]:
    """Extract structural information from a .gitlab-ci.yml file."""
    analysis: dict[str, Any] = {}
    
    stages_match = re.search(r"^stages:\s*\n((?:\s+-\s+.+\n?)+)", content, re.MULTILINE)
    if stages_match:
        stages = re.findall(r"-\s+(\S+)", stages_match.group(1))
        analysis["stages"] = stages

    reserved = {
        "stages", "variables", "default", "include", "image", "services",
        "before_script", "after_script", "cache", "workflow",
    }
    jobs = []
    for match in re.finditer(r"^([a-zA-Z_][a-zA-Z0-9_.-]*):\s*$", content, re.MULTILINE):
        key = match.group(1)
        if key not in reserved and not key.startswith("."):
            jobs.append(key)
    analysis["jobs"] = jobs
    
    # Extract image
    image_match = re.search(r"^image:\s+(.+)$", content, re.MULTILINE)
    if image_match:
        analysis["image"] = image_match.group(1).strip().strip("'\"")

    return analysis


# ---------------------------------------------------------------------------
# Main Handle
# ---------------------------------------------------------------------------

async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the inspect_project tool."""
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    encoded_project = encode_project(project)
    ref = arguments.get("ref", "").strip()
    ref = await resolve_ref(client, encoded_project, ref)

    results: dict[str, Any] = {
        "project": project,
        "ref": ref,
        "ecosystems": [],
        "build_systems": [],
        "dependencies": [],
        "ci_config": None,
        "files_analyzed": 0,
    }

    # 1. Gather all file paths we want to check (deduplicated)
    files_to_check = set()
    file_metadata = {} # path -> type (dep/build)

    for eco, files in _DEPENDENCY_FILES.items():
        for f in files:
            files_to_check.add(f)
            file_metadata.setdefault(f, {"types": []})
            file_metadata[f]["types"].append(("dependency", eco))

    for entry in _BUILD_FILES:
        files_to_check.add(entry["file"])
        file_metadata.setdefault(entry["file"], {"types": []})
        file_metadata[entry["file"]]["types"].append(("build", entry["build_system"]))
    
    files_to_check.add(".gitlab-ci.yml")

    # 2. Fetch all files concurrently
    # TODO: Use bulk fetch if available and think of a way to not fetch files that don't exist (e.g. via tree listing)
    # Let's parallelize the fetching
    async def _fetch_and_process(path: str):
        content = await fetch_file(client, encoded_project, path, ref)
        return path, content

    tasks = [_fetch_and_process(p) for p in files_to_check]
    fetched = await asyncio.gather(*tasks)
    
    discovered_ecosystems = set()
    discovered_build_systems = set()

    for path, content in fetched:
        if content is None:
            continue
            
        results["files_analyzed"] += 1
        
        # Analyze CI
        if path == ".gitlab-ci.yml":
            results["ci_config"] = {
                "found": True,
                "analysis": _analyze_ci_yaml(content),
                "raw_preview": content[:200]
            }
            continue

        meta = file_metadata.get(path, {})
        types = meta.get("types", [])

        # Process build/dep metadata
        for type_name, value in types:
            if type_name == "dependency":
                discovered_ecosystems.add(value)
                parser = _DEP_PARSERS.get(path)
                if parser:
                    deps = parser(content)
                    if deps:
                        results["dependencies"].append({
                            "source_file": path,
                            "ecosystem": value,
                            "count": len(deps),
                            "items": deps[:10]  # Limit output
                        })
            elif type_name == "build":
                discovered_build_systems.add(value)

    results["ecosystems"] = list(discovered_ecosystems)
    results["build_systems"] = list(discovered_build_systems)

    return results

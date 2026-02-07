"""MCP tool: get_ci_config — retrieve CI/CD configuration from a CERN GitLab repository."""

import base64
import re
from typing import Any
from urllib.parse import quote

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.exceptions import NotFoundError
from cerngitlab_mcp.tools.utils import encode_project, resolve_ref


TOOL_DEFINITION = Tool(
    name="get_ci_config",
    description=(
        "Retrieve the CI/CD configuration (.gitlab-ci.yml) from a CERN GitLab repository. "
        "Returns the raw YAML content along with a basic structural analysis: "
        "detected stages, jobs, and included templates."
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

# TODO: Add proper YAML parsing for better analysis
def _analyze_ci_yaml(content: str) -> dict[str, Any]:
    """Extract structural information from a .gitlab-ci.yml file.

    This is a lightweight regex-based analysis (no YAML parser dependency).
    """
    analysis: dict[str, Any] = {}

    # Extract stages
    stages_match = re.search(r"^stages:\s*\n((?:\s+-\s+.+\n?)+)", content, re.MULTILINE)
    if stages_match:
        stages_block = stages_match.group(1)
        stages = re.findall(r"-\s+(\S+)", stages_block)
        analysis["stages"] = stages

    # Extract top-level keys that look like job names
    # Jobs are top-level keys that are not reserved keywords
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

    # Extract hidden jobs (templates starting with .)
    hidden_jobs = []
    for match in re.finditer(r"^(\.[a-zA-Z_][a-zA-Z0-9_.-]*):\s*$", content, re.MULTILINE):
        hidden_jobs.append(match.group(1))
    if hidden_jobs:
        analysis["hidden_jobs_templates"] = hidden_jobs

    # Extract includes
    includes = []
    for match in re.finditer(r"(?:local|remote|template|project|file):\s*['\"]?([^'\"#\n]+)", content):
        includes.append(match.group(1).strip())
    if includes:
        analysis["includes"] = includes

    # Extract image
    image_match = re.search(r"^image:\s+(.+)$", content, re.MULTILINE)
    if image_match:
        analysis["image"] = image_match.group(1).strip().strip("'\"")

    # Extract variables
    variables = {}
    in_vars = False
    for line in content.splitlines():
        stripped = line.strip()
        if re.match(r"^variables:\s*$", line):
            in_vars = True
            continue
        if in_vars:
            if line and not line[0].isspace():
                in_vars = False
                continue
            var_match = re.match(r"\s+([A-Z_][A-Z0-9_]*):\s*(.+)", line)
            if var_match:
                variables[var_match.group(1)] = var_match.group(2).strip().strip("'\"")
    if variables:
        analysis["variables"] = variables

    return analysis


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the get_ci_config tool.

    Returns:
        Dict with CI config content and structural analysis.
    """
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    encoded_project = encode_project(project)
    ref = arguments.get("ref", "").strip()
    ref = await resolve_ref(client, encoded_project, ref)

    encoded_path = quote(".gitlab-ci.yml", safe="")
    try:
        data = await client.get(
            f"/projects/{encoded_project}/repository/files/{encoded_path}",
            params={"ref": ref},
        )
    except NotFoundError:
        return {
            "project": project,
            "ref": ref,
            "found": False,
            "error": "No .gitlab-ci.yml found in this repository",
        }

    content_encoded = data.get("content", "")
    encoding = data.get("encoding", "base64")

    if encoding == "base64" and content_encoded:
        try:
            content = base64.b64decode(content_encoded).decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            content = content_encoded
    else:
        content = content_encoded

    analysis = _analyze_ci_yaml(content)

    return {
        "project": project,
        "ref": ref,
        "found": True,
        "size": data.get("size", 0),
        "content": content,
        "analysis": analysis,
    }

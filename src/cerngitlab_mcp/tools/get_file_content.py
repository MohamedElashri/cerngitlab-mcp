"""MCP tool: get_file_content — retrieve file content from a CERN GitLab repository."""

import base64
from typing import Any
from urllib.parse import quote

from mcp.types import Tool

from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.tools.utils import encode_project, resolve_ref


# Common binary file extensions that should not be decoded as text
_BINARY_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".webp",
        ".svg",
        ".pdf",
        ".zip",
        ".gz",
        ".tar",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".o",
        ".a",
        ".pyc",
        ".pyo",
        ".class",
        ".wasm",
        ".root",  # ROOT files (HEP-specific)
        ".pkl",
        ".pickle",
        ".npy",
        ".npz",
        ".h5",
        ".hdf5",
        ".pt",
        ".pth",
        ".bin",
        ".onnx",
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".mp3",
        ".mp4",
        ".wav",
        ".avi",
        ".mov",
    }
)

# Map file extensions to language hints for syntax highlighting
_LANGUAGE_HINTS: dict[str, str] = {
    ".py": "python",
    ".pyx": "python",
    ".pyi": "python",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".C": "cpp",
    ".c": "c",
    ".h": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".cu": "cuda",
    ".cuh": "cuda",
    ".cuda": "cuda",
    ".java": "java",
    ".js": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".rb": "ruby",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".xml": "xml",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".sql": "sql",
    ".md": "markdown",
    ".markdown": "markdown",
    ".tex": "latex",
    ".cmake": "cmake",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".r": "r",
    ".R": "r",
    ".jl": "julia",
    ".f90": "fortran",
    ".f95": "fortran",
    ".f03": "fortran",
    ".f": "fortran",
}

# Map full filenames to language hints
_FILENAME_LANGUAGE_HINTS: dict[str, str] = {
    "CMakeLists.txt": "cmake",
    "Makefile": "makefile",
    "Dockerfile": "dockerfile",
    "Jenkinsfile": "groovy",
    ".gitlab-ci.yml": "yaml",
    ".clang-format": "yaml",
}


TOOL_DEFINITION = Tool(
    name="get_file_content",
    description=(
        "Retrieve the content of a specific file from a CERN GitLab repository. "
        "Returns the file content along with metadata like size, encoding, and "
        "a language hint for syntax highlighting. Binary files are detected and "
        "reported without attempting to decode them."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": (
                    "Project identifier — either a numeric ID (e.g. '12345') "
                    "or a path (e.g. 'atlas/athena')"
                ),
            },
            "file_path": {
                "type": "string",
                "description": "Path to the file within the repository (e.g. 'src/main.py')",
            },
            "ref": {
                "type": "string",
                "description": "Branch name, tag, or commit SHA (default: project's default branch)",
            },
        },
        "required": ["project", "file_path"],
    },
)


def _has_binary_extension(file_path: str) -> bool:
    """Check if a file has a known binary extension."""
    filename = file_path.split("/")[-1]
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in _BINARY_EXTENSIONS


def _is_binary_content(raw_bytes: bytes) -> bool:
    """Check if content is binary (contains NUL byte)."""
    return b"\x00" in raw_bytes


# Backward-compatibility alias
_is_binary = _has_binary_extension


def _get_language_hint(file_path: str) -> str | None:
    """Get a syntax highlighting language hint from the file name or extension."""
    filename = file_path.split("/")[-1]

    # Try full filename match first
    hint = _FILENAME_LANGUAGE_HINTS.get(filename)
    if hint:
        return hint

    ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
    # Try exact match first, then lowercase
    return _LANGUAGE_HINTS.get(ext) or _LANGUAGE_HINTS.get(ext.lower())


async def handle(client: GitLabClient, arguments: dict) -> dict[str, Any]:
    """Execute the get_file_content tool.

    Returns:
        Dict with file content and metadata.
    """
    project = arguments.get("project", "").strip()
    if not project:
        raise ValueError("'project' parameter is required")

    file_path = arguments.get("file_path", "").strip()
    if not file_path:
        raise ValueError("'file_path' parameter is required")

    encoded_project = encode_project(project)
    encoded_path = quote(file_path, safe="")

    ref = arguments.get("ref", "").strip()
    ref = await resolve_ref(client, encoded_project, ref)

    data = await client.get(
        f"/projects/{encoded_project}/repository/files/{encoded_path}",
        params={"ref": ref},
    )

    file_name = data.get("file_name", file_path.split("/")[-1])
    size = data.get("size", 0)
    encoding = data.get("encoding", "base64")
    content_encoded = data.get("content", "")

    result: dict[str, Any] = {
        "file_name": file_name,
        "file_path": data.get("file_path", file_path),
        "size": size,
        "ref": data.get("ref", ref or "(default branch)"),
        "last_commit_id": data.get("last_commit_id"),
        "content_sha256": data.get("content_sha256"),
    }

    # 1. Fast-path check: known binary extensions (.root, images, compiled binaries)
    if _has_binary_extension(file_name):
        result["is_binary"] = True
        result["content"] = f"[Binary file, {size} bytes]"
        result["language"] = None
        return result

    # 2. Treat as text candidate: decode and sniff content
    result["is_binary"] = False
    if encoding == "base64" and content_encoded:
        try:
            raw_bytes = base64.b64decode(content_encoded)
        except Exception:
            result["is_binary"] = True
            result["content"] = f"[Binary file, {size} bytes — failed to decode base64]"
            result["language"] = None
            return result

        # Check for NUL bytes in the first 8000 bytes (Git-style)
        if _is_binary_content(raw_bytes):
            result["is_binary"] = True
            result["content"] = f"[Binary file, {size} bytes]"
            result["language"] = None
            return result

        try:
            result["content"] = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            result["is_binary"] = True
            result["content"] = (
                f"[Binary file, {size} bytes — failed to decode as UTF-8]"
            )
            result["language"] = None
            return result
    else:
        result["content"] = content_encoded

    result["language"] = _get_language_hint(file_name)
    return result

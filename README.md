# CERN GitLab MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that connects LLMs to [CERN GitLab](https://gitlab.cern.ch) for discovering HEP code, documentation, and analysis examples.

## Features

- **14 MCP tools** for searching, browsing, and analyzing CERN GitLab repositories
- **Public access** — works without authentication for public repositories
- **HEP-focused** — dependency parsing for Python and C++ ecosystems, binary detection for `.root` files
- **Robust** — rate limiting, retries with exponential backoff, graceful error handling

## Installation

Requires Python 3.14+ and [UV](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone https://github.com/MohamedElashri/cerngitlab-mcp
cd cerngitlab-mcp

# Install with UV
uv sync
```

## Configuration

All settings are configured via environment variables prefixed with `CERNGITLAB_`:

| Variable | Default | Description |
|---|---|---|
| `CERNGITLAB_GITLAB_URL` | `https://gitlab.cern.ch` | GitLab instance URL |
| `CERNGITLAB_TOKEN` | *(empty)* | Personal access token (optional) |
| `CERNGITLAB_TIMEOUT` | `30` | HTTP timeout in seconds |
| `CERNGITLAB_MAX_RETRIES` | `3` | Max retries for failed requests |
| `CERNGITLAB_RATE_LIMIT_PER_MINUTE` | `300` | API rate limit |
| `CERNGITLAB_LOG_LEVEL` | `INFO` | Logging level |

### Authentication

The server works in two modes:

- **Without token** — Access to all public repositories. Sufficient for most HEP code discovery.
- **With token** — Additional access to internal/private projects, code search, and wiki pages.

To create a token:
1. Go to https://gitlab.cern.ch/-/user_settings/personal_access_tokens
2. Create a token with `read_api` scope
3. Set `CERNGITLAB_TOKEN=glpat-xxxxxxxxxxxx`

> **Note:** The code search (`search_code`) and wiki (`get_wiki_pages`) tools require authentication on CERN GitLab.

## Usage

### With Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cerngitlab": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/cerngitlab-mcp", "cerngitlab-mcp"],
      "env": {
        "CERNGITLAB_TOKEN": "glpat-xxxxxxxxxxxx"
      }
    }
  }
}
```

### With other MCP clients

```bash
# Run directly
uv run cerngitlab-mcp

# Or with environment variables
CERNGITLAB_TOKEN=glpat-xxx uv run cerngitlab-mcp
```

## Tools Reference

### Repository Discovery

#### `search_repositories`
Search for public repositories by keywords, topics, or programming language.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Search query (matches name, description) |
| `language` | string | Filter by language (e.g. `python`, `c++`) |
| `topic` | string | Filter by topic (e.g. `physics`, `atlas`) |
| `sort_by` | string | Sort field: `last_activity_at`, `name`, `created_at`, `stars` |
| `order` | string | `desc` or `asc` |
| `per_page` | integer | Results count (1–100, default: 20) |

#### `get_repository_info`
Get detailed information about a specific repository including languages, statistics, and license.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path (e.g. `atlas/athena`) |

#### `list_repository_files`
Browse the file tree of a repository.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `path` | string | no | Subdirectory path |
| `ref` | string | no | Branch/tag/commit |
| `recursive` | boolean | no | List recursively |
| `per_page` | integer | no | Results count (default: 100) |

### Code & Documentation Access

#### `get_file_content`
Retrieve file content with binary detection and syntax highlighting hints.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `file_path` | string | yes | Path within repository |
| `ref` | string | no | Branch/tag/commit |

#### `get_repository_readme`
Get the README file, automatically trying common filenames (README.md, .rst, .txt, etc.).

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `ref` | string | no | Branch/tag/commit |

#### `search_code`
Search for code across repositories. **Requires authentication.**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `search_term` | string | yes | Code/text to search for |
| `project` | string | no | Limit to specific project |
| `scope` | string | no | `blobs` (content) or `filenames` |
| `per_page` | integer | no | Results count (default: 20) |

#### `get_wiki_pages`
Access repository wiki pages. **Requires authentication.**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `page_slug` | string | no | Specific page slug (omit to list all) |

### Dependency & Build Analysis

#### `analyze_dependencies`
Parse dependency files for Python, C++, and Fortran ecosystems.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `ref` | string | no | Branch/tag/commit |

Detects: `requirements.txt`, `pyproject.toml`, `setup.py`, `CMakeLists.txt`, `conda.yaml`, and more.

#### `get_ci_config`
Retrieve and analyze `.gitlab-ci.yml` configuration.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `ref` | string | no | Branch/tag/commit |

Returns raw YAML content plus structural analysis (stages, jobs, includes, variables).

#### `get_build_config`
Find and retrieve build configuration files (CMakeLists.txt, Makefile, setup.py, pyproject.toml, etc.).

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `ref` | string | no | Branch/tag/commit |

### Release & Version Tracking

#### `list_releases`
List releases from a repository.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `per_page` | integer | no | Results count (default: 20) |

#### `get_release`
Get detailed information about a specific release.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `tag_name` | string | yes | Release tag (e.g. `v1.0.0`) |

#### `list_tags`
List repository tags with optional filtering.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `search` | string | no | Filter by name prefix |
| `sort` | string | no | `asc` or `desc` |
| `per_page` | integer | no | Results count (default: 20) |

### Utility

#### `test_connectivity`
Test connection to the CERN GitLab instance. No parameters required.

## Example LLM Prompts

### Find ROOT analysis code
> "Search CERN GitLab for Python repositories related to ROOT analysis and show me the most starred ones"

### Understand a project
> "Get the README and file structure of the lhcb/DaVinci project on CERN GitLab"

### Find fitting examples
> "Search for repositories on CERN GitLab that use RooFit and show me example fitting code"

### Check dependencies
> "What are the dependencies of the atlas/athena project? Show me the CMakeLists.txt and any Python requirements"

### Track releases
> "List the recent releases of lhcb/DaVinci and show me the release notes for the latest version"

### Explore CI/CD
> "Get the CI/CD configuration of the atlas/athena project and explain the pipeline stages"

### Find framework configurations
> "Search for Gaudi framework configuration files on CERN GitLab and show me examples"

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest tests/test_unit_tools.py -v

# Run integration tests (requires network access to gitlab.cern.ch)
uv run python tests/test_phase3_tools.py
uv run python tests/test_phase4_tools.py
uv run python tests/test_phase5_tools.py
uv run python tests/test_phase6_tools.py

# Lint
uv run ruff check src/
```

## Architecture

```
src/cerngitlab_mcp/
├── __init__.py              # Package version
├── config.py                # Pydantic Settings (env-based)
├── exceptions.py            # Custom exception hierarchy
├── gitlab_client.py         # Async HTTP client with rate limiting
├── logging.py               # Structured logging
├── server.py                # MCP server + tool dispatch
└── tools/
    ├── utils.py             # Shared helpers (encode_project, resolve_ref, fetch_file)
    ├── search_repositories.py
    ├── get_repository_info.py
    ├── list_repository_files.py
    ├── get_file_content.py
    ├── get_repository_readme.py
    ├── search_code.py
    ├── get_wiki_pages.py
    ├── analyze_dependencies.py
    ├── get_ci_config.py
    ├── get_build_config.py
    ├── list_releases.py
    ├── get_release.py
    └── list_tags.py
```

## License

AGPL-3.0

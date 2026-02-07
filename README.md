<p align="center">
  <img src="https://raw.githubusercontent.com/MohamedElashri/cerngitlab-mcp/main/icons/icon.svg" alt="CERN GitLab MCP Server" width="160" />
</p>

<h1 align="center">CERN GitLab MCP Server</h1>

<p align="center">
  An <a href="https://modelcontextprotocol.io/">MCP</a> server that connects LLMs to <a href="https://gitlab.cern.ch">CERN GitLab</a> for discovering HEP code, documentation, and analysis examples.
</p>

## Features

- **14 MCP tools** for searching, browsing, and analyzing CERN GitLab repositories
- **Public access** — works without authentication for public repositories
- **HEP-focused** — dependency parsing for Python and C++ ecosystems, binary detection for `.root` files
- **Robust** — rate limiting, retries with exponential backoff, graceful error handling

## Installation

Requires Python 3.10+.

### Quickstart (recommended)

No installation needed — just use [`uvx`](https://docs.astral.sh/uv/) to run directly:

```bash
uvx cerngitlab-mcp
```

### From PyPI

```bash
pip install cerngitlab-mcp
```

### From source

```bash
git clone https://github.com/MohamedElashri/cerngitlab-mcp
cd cerngitlab-mcp
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

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cerngitlab": {
      "command": "uvx",
      "args": ["cerngitlab-mcp"],
      "env": {
        "CERNGITLAB_TOKEN": "glpat-xxxxxxxxxxxx"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add cerngitlab-mcp -- uvx cerngitlab-mcp
```

To include authentication:

```bash
claude mcp add cerngitlab-mcp -e CERNGITLAB_TOKEN=glpat-xxxxxxxxxxxx -- uvx cerngitlab-mcp
```

### GitHub Copilot

Add to your VS Code `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "cerngitlab": {
        "command": "uvx",
        "args": ["cerngitlab-mcp"],
        "env": {
          "CERNGITLAB_TOKEN": "glpat-xxxxxxxxxxxx"
        }
      }
    }
  }
}
```

Or add a `.vscode/mcp.json` to your project:

```json
{
  "servers": {
    "cerngitlab": {
      "command": "uvx",
      "args": ["cerngitlab-mcp"],
      "env": {
        "CERNGITLAB_TOKEN": "glpat-xxxxxxxxxxxx"
      }
    }
  }
}
```

### Gemini CLI

Add to your `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "cerngitlab": {
      "command": "uvx",
      "args": ["cerngitlab-mcp"],
      "env": {
        "CERNGITLAB_TOKEN": "glpat-xxxxxxxxxxxx"
      }
    }
  }
}
```

### Direct usage

```bash
# Run with uvx (no install needed)
uvx cerngitlab-mcp

# Or if installed from PyPI
cerngitlab-mcp

# Or from source
uv run cerngitlab-mcp

# With authentication
CERNGITLAB_TOKEN=glpat-xxx uvx cerngitlab-mcp
```

## Tools

| Tool | Description | Auth required |
|---|---|---|
| `search_repositories` | Search public repositories by keywords, topics, or language | No |
| `get_repository_info` | Get repository details (languages, stats, license) | No |
| `list_repository_files` | Browse the file tree of a repository | No |
| `get_file_content` | Retrieve file content with binary detection | No |
| `get_repository_readme` | Get the README file (tries common filenames) | No |
| `search_code` | Search for code across repositories | Yes* |
| `get_wiki_pages` | Access repository wiki pages | Yes |
| `analyze_dependencies` | Parse dependency files (Python, C++, Fortran) | No |
| `get_ci_config` | Retrieve and analyze `.gitlab-ci.yml` | No |
| `get_build_config` | Find build config files (CMake, Make, setuptools, etc.) | No |
| `list_releases` | List releases from a repository | No |
| `get_release` | Get details of a specific release | No |
| `list_tags` | List repository tags with optional filtering | No |
| `test_connectivity` | Test connection to the GitLab instance | No |

\* `search_code` works without auth for project-scoped search (uses fallback grep). Global search requires authentication.

For detailed parameter documentation, see [dev.md](dev.md).

## Example Prompts

### Search for repositories
> "Search CERN GitLab for Python repositories related to ROOT analysis and show me the most starred ones"

### Understand a project
> "Get the README and file structure of the lhcb/DaVinci project on CERN GitLab"

### Find fitting examples
> "Search for repositories on CERN GitLab that use RooFit and show me example fitting code"

### Check dependencies
> "What are the dependencies of the lhcb/allen project? Show me the CMakeLists.txt and any Python requirements"

### Track releases
> "List the recent releases of lhcb/DaVinci and show me the release notes for the latest version"

### Explore CI/CD
> "Get the CI/CD configuration of the lhcb/allen project and explain the pipeline stages"

### Find framework configurations
> "Search for Gaudi framework configuration files on CERN GitLab and show me examples"

## Development

See [dev.md](dev.md) for development setup, project structure, testing, and release instructions.

## License

AGPL-3.0

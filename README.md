<p align="center">
  <img src="https://raw.githubusercontent.com/MohamedElashri/cerngitlab-mcp/main/icons/icon.svg" alt="CERN GitLab MCP Server" width="160" />
</p>

<h1 align="center">CERN GitLab MCP Server</h1>

<p align="center">
  An <a href="https://modelcontextprotocol.io/">MCP</a> server that connects LLMs to <a href="https://gitlab.cern.ch">CERN GitLab</a> for discovering HEP code, documentation, and analysis examples.
</p>

## Features

- **13 MCP tools** for searching, browsing, and analyzing CERN GitLab repositories
- **Public access** — works without authentication for public repositories
- **HEP-focused** — dependency parsing for Python and C++ ecosystems, binary detection for `.root` files, issue search
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

> **Note:** The code search (`search_code`), issue search (`search_issues`), and wiki (`get_wiki_pages`) tools require authentication on CERN GitLab.

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

**Project-specific (default)** — installs in the current directory's configuration:

```bash
claude mcp add cerngitlab-mcp -- uvx cerngitlab-mcp
```

**Global** — installs for your user account (works in all projects):

```bash
claude mcp add --scope user cerngitlab-mcp -- uvx cerngitlab-mcp
```

To include authentication, add `-e CERNGITLAB_TOKEN=glpat-xxxxxxxxxxxx` before the `--`:

```bash
# Example: Global installation with token
claude mcp add --scope user -e CERNGITLAB_TOKEN=glpat-xxxxxxxxxxxx cerngitlab-mcp -- uvx cerngitlab-mcp
```

**Manual Configuration** — you can also manually edit your global config at `~/.claude.json` (on Linux/macOS) or `%APPDATA%\Claude\claude.json` (on Windows):

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
| `search_projects` | Search for public CERN GitLab projects (repositories) by keyword, topic, or language | No |
| `get_project_info` | Get detailed project metadata (stars, description, languages, statistics) | No |
| `list_project_files` | List files and directories in a project's repository | No |
| `get_file_content` | Fetch the content of a specific file (includes binary detection) | No |
| `get_project_readme` | Get the README content for a project | No |
| `search_code` | Search for code within a specific project or globally | Yes* |
| `search_issues` | Search for issues in a project | Yes |
| `get_wiki_pages` | List wiki pages for a project | Yes |
| `inspect_project` | Analyze project structure, build system, dependencies, and CI/CD | No |
| `list_releases` | List releases for a project | No |
| `get_release` | Get details of a specific release | No |
| `list_tags` | List tags for a project | No |
| `test_connectivity` | Test connection to the GitLab instance | No |

For detailed parameter documentation, see [docs/dev.md](docs/dev.md).

## Example Prompts

### Search for repositories
> "Search CERN GitLab for Python repositories related to ROOT analysis and show me the most starred ones"

### Understand a project
> "Get the README and file structure of the lhcb/DaVinci project on CERN GitLab"

### Find fitting examples
> "Search for repositories on CERN GitLab that use RooFit and show me example fitting code"

### Analyze a project structure
> "Inspect the lhcb/allen project to understand its build system, dependencies, and CI pipeline configuration"

### Find usage context
> "Search for issues related to 'segmentation fault' in the atlas/athena project to see if others have encountered this"

### Track releases
> "List the recent releases of lhcb/DaVinci and show me the release notes for the latest version"

### Find framework configurations
> "Search for Gaudi framework configuration files on CERN GitLab and show me examples"

## Development

See [docs/dev.md](docs/dev.md) for development setup, project structure, testing, and release instructions.

## License

AGPL-3.0

<p align="center">
  <img src="https://raw.githubusercontent.com/MohamedElashri/cerngitlab-mcp/main/icons/icon.svg" alt="CERN GitLab MCP Server" width="160" />
</p>

<h1 align="center">CERN GitLab MCP Server</h1>

<p align="center">
  An <a href="https://modelcontextprotocol.io/">MCP</a> server that connects LLMs to <a href="https://gitlab.cern.ch">CERN GitLab</a> for discovering HEP code, documentation, and analysis examples.
</p>

## Features

- **14 MCP tools** for searching, browsing, and analyzing CERN GitLab repositories
- **Dual-mode operation** — stdio (single-user) and HTTP (multi-user) modes
- **CLI tool** (`cerngitlab-cli`) for direct command-line usage
- **Public access** — works without authentication for public repositories
- **Multi-user HTTP mode** — CERN SSO + GitLab OAuth authentication for centralized deployments; GitLab enforces all access permissions natively
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
| `CERNGITLAB_TOKEN` | *(empty)* | Personal access token (optional, for stdio mode) |
| `CERNGITLAB_TIMEOUT` | `30` | HTTP timeout in seconds |
| `CERNGITLAB_MAX_RETRIES` | `3` | Max retries for failed requests |
| `CERNGITLAB_RATE_LIMIT_PER_MINUTE` | `300` | API rate limit |
| `CERNGITLAB_LOG_LEVEL` | `INFO` | Logging level |
| `CERNGITLAB_DEFAULT_REF` | *(empty)* | Default Git branch or tag to search within. Empty means all branches. |
| `CERNGITLAB_HTTP_MODE` | *(empty)* | Set any value to auto-detect HTTP mode |
| `CERNGITLAB_HOST` | `0.0.0.0` | HTTP server bind address |
| `CERNGITLAB_PORT` | `8000` | HTTP server bind port |
| `CERNGITLAB_CERN_CLIENT_ID` | *(empty)* | **HTTP mode** — CERN SSO OAuth client ID |
| `CERNGITLAB_GITLAB_OAUTH_CLIENT_ID` | *(empty)* | **HTTP mode** — GitLab OAuth application client ID |
| `CERNGITLAB_GITLAB_OAUTH_CLIENT_SECRET` | *(empty)* | **HTTP mode** — GitLab OAuth application client secret |
| `CERNGITLAB_SERVER_BASE_URL` | `http://localhost:8000` | **HTTP mode** — Public base URL (used for OAuth callback) |
| `CERNGITLAB_SESSION_STORAGE_PATH` | `/tmp/cerngitlab/sessions` | **HTTP mode** — Directory for persisting OAuth session files |

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

> **Note for macOS users:** If you see an error about `uvx` not being found, you may need to provide the absolute path. Claude Desktop does not support `~` or `$HOME` expansion.
>
> 1. Run `which uvx` in your terminal to find the path (e.g., `/Users/yourusername/.local/bin/uvx`).
> 2. Use that absolute path in the `command` field:
>
> ```json
> "command": "/Users/yourusername/.local/bin/uvx"
> ```

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

#### Stdio Mode (Single-User, Default)

```bash
# Run with uvx (no install needed)
uvx cerngitlab-mcp

# Or if installed from PyPI
cerngitlab-mcp

# Explicit stdio mode
cerngitlab-mcp --mode stdio

# Or from source
uv run cerngitlab-mcp

# With authentication
CERNGITLAB_TOKEN=glpat-xxx uvx cerngitlab-mcp
```

#### HTTP Mode (Multi-User)

```bash
# HTTP mode for multi-user deployment
cerngitlab-mcp --mode http --host 0.0.0.0 --port 8080

# Or use environment variables
CERNGITLAB_HTTP_MODE=true CERNGITLAB_HOST=0.0.0.0 CERNGITLAB_PORT=8080 cerngitlab-mcp

# Dedicated HTTP entry point
cerngitlab-mcp-http
```

#### Mode Selection

- `--mode stdio` - Single-user mode using stdin/stdout (default)
- `--mode http` - Multi-user mode using HTTP API
- `--mode auto` - Auto-detect based on environment variables

The server automatically detects HTTP mode if `CERNGITLAB_HTTP_MODE`, `CERNGITLAB_HOST`, or `CERNGITLAB_PORT` environment variables are set.

## Tools

| Tool | Description | Auth required |
|---|---|---|
| `search_projects` | Search for public CERN GitLab projects (repositories) by keyword, topic, or language | No |
| `get_project_info` | Get detailed project metadata (stars, description, languages, statistics) | No |
| `list_project_files` | List files and directories in a project's repository | No |
| `get_file_content` | Fetch the content of a specific file (includes binary detection) | No |
| `get_project_readme` | Get the README content for a project | No |
| `search_code` | Search for code within a specific project or globally | Yes* |
| `search_lhcb_stack` | Search for code within an LHCb software stack (e.g., 'sim11'), with automatic Git ref resolution | Yes* |
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

### View LHCb software stack code
> "Search the LHCb sim11 stack for the initialization routines in the Boole project"

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

## Multi-User HTTP Deployment

HTTP mode provides a centralized server for multiple users. It uses **CERN SSO + GitLab OAuth** for authentication, users authenticate with their existing CERN identity, and GitLab's own permission system enforces all access controls.

### Prerequisites

1. **CERN SSO client** — Register a client at the [CERN Authorization Service](https://auth.cern.ch). Note the client ID.
2. **GitLab OAuth application** — Create one at `https://gitlab.cern.ch/-/profile/applications`.
   - Set the redirect URI to `https://gitlab.cern.ch/oauth/callback` (replace with actual URL)
   - Enable the `read_api read_repository read_user` scopes
   - Note the application ID and secret.

### Setup

```bash
export CERNGITLAB_CERN_CLIENT_ID=your-cern-sso-client-id
export CERNGITLAB_GITLAB_OAUTH_CLIENT_ID=your-gitlab-oauth-app-id
export CERNGITLAB_GITLAB_OAUTH_CLIENT_SECRET=your-gitlab-oauth-secret
export CERNGITLAB_SERVER_BASE_URL=https://your-server.cern.ch
export CERNGITLAB_SESSION_STORAGE_PATH=/var/lib/cerngitlab/sessions  # optional

# Start the server
cerngitlab-mcp --mode http --host 0.0.0.0 --port 8000
```

See `examples/oauth_server.py` in the repository for a self-contained reference script.

### Authentication Flow

1. Client sends a request with `Authorization: Bearer <cern-sso-token>` header.
2. Server validates the CERN SSO token via CERN's JWKS endpoint.
3. If the user has no active GitLab OAuth session, the server returns HTTP 202 with a `authorization_url` field.
4. The user visits that URL, authorizes the GitLab OAuth application, and is redirected back to `/oauth/callback`.
5. Subsequent requests are served using the stored GitLab OAuth token. Sessions expire after 2 hours.

### API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | — | Server information |
| `GET` | `/health` | — | Health check |
| `GET` | `/oauth/authorize` | CERN SSO | Start or check the OAuth authorization flow |
| `GET` | `/oauth/callback` | — | Receive the GitLab OAuth code (browser redirect) |
| `GET` | `/tools` | CERN SSO | List available MCP tools |
| `POST` | `/tools/{tool_name}` | CERN SSO | Execute a specific tool |
| `DELETE` | `/session` | CERN SSO | Revoke the current user's OAuth session |
| `GET` | `/admin/sessions` | — | List all active sessions (admin use) |

### Example Usage

```bash
# Step 1 – check authorization status
curl -H "Authorization: Bearer $CERN_SSO_TOKEN" \
     https://your-server.cern.ch/oauth/authorize
# If 202, visit the returned authorization_url in a browser and authorize.

# Step 2 – list available tools (once authorized)
curl -H "Authorization: Bearer $CERN_SSO_TOKEN" \
     https://your-server.cern.ch/tools

# Step 3 – execute a tool
curl -X POST -H "Authorization: Bearer $CERN_SSO_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"arguments": {"query": "ROOT"}}' \
     https://your-server.cern.ch/tools/search_projects

# Revoke session
curl -X DELETE -H "Authorization: Bearer $CERN_SSO_TOKEN" \
     https://your-server.cern.ch/session
```

## CLI Tool

A command-line interface is also available for direct usage without the MCP server:

```bash
# Install or use with uvx
uvx cerngitlab-cli

# Test connectivity
cerngitlab-cli test-connection

# Search for projects
cerngitlab-cli search-projects --query "ROOT analysis" --language python

# Get project info
cerngitlab-cli get-project-info --project lhcb/DaVinci

# Search code
cerngitlab-cli search-code --search-term "RooFit" --per-page 10

# Inspect project structure
cerngitlab-cli inspect-project --project lhcb/allen
```

All commands output JSON to stdout for easy piping and composition. See `cerngitlab-cli --help` for the full list of commands.

## Skill File

A detailed skill file ([`SKILL.md`](SKILL.md)) is available with:
- Complete documentation of all 14 tools
- Input/output specifications
- Usage examples
- Authentication requirements

This can be used by LLMs or agents to understand the available tools and how to use them.

## License

AGPL-3.0

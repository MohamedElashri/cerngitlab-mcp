# MCP client integration

Connect your coding agent or desktop client to CERN GitLab to search projects,
read source and documentation, inspect branches, and explore releases and issues.
The examples follow the same client configuration layout as ROOT-MCP and were
checked against upstream client documentation on 2026-10-31.

## Local setup

Install [uv](https://docs.astral.sh/uv/), then configure your client to launch:

```bash
uvx cerngitlab-mcp --mode stdio
```

The client starts the server. If the package is already installed, use
`cerngitlab-mcp --mode stdio` directly. Explicit stdio mode prevents inherited
HTTP settings from changing how the server starts.

For a development checkout:

```bash
uv sync --locked --all-groups
uv run --directory /absolute/path/to/cerngitlab-mcp cerngitlab-mcp --mode stdio
```

Use an absolute checkout path. If a desktop client cannot find `uvx`, find its
executable with `command -v uvx` and use that absolute path in the configuration.
Server logs go to stderr; stdout is reserved for MCP messages.

Public repositories need no token. For authenticated access, create a GitLab
personal access token with `read_api` scope and configure `CERNGITLAB_TOKEN` in
the server's environment. The [README authentication section](../../README.md#authentication)
explains which tools require it.

## Choose a client

Use the configuration for the agent actually making tool calls. An editor's
built-in agent, Codex extension, and Claude Code can use different configuration
files even when they run in the same workspace.

| Client | Project or user configuration | Template |
|---|---|---|
| Codex CLI / IDE extension | Trusted `.codex/config.toml` or `~/.codex/config.toml` | [codex.toml](../../examples/clients/codex.toml) |
| Claude Code / Desktop | `.mcp.json` / Desktop's MCP settings | [claude.json](../../examples/clients/claude.json) |
| VS Code Local harness | `.vscode/mcp.json` | [vscode.json](../../examples/clients/vscode.json) |
| Copilot CLI / VS Code Copilot harness | Trusted `.mcp.json` or `~/.copilot/mcp-config.json` | [copilot.json](../../examples/clients/copilot.json) |
| Cursor | `.cursor/mcp.json` or `~/.cursor/mcp.json` | [cursor.json](../../examples/clients/cursor.json) |
| Zed Agent | Settings opened by `zed: open settings file` | [zed.json](../../examples/clients/zed.json) |
| Antigravity app / IDE / CLI | `.agents/mcp_config.json` or `~/.gemini/config/mcp_config.json` | [antigravity.json](../../examples/clients/antigravity.json) |
| Qwen Code | `.qwen/settings.json` or `~/.qwen/settings.json` | [qwen.json](../../examples/clients/qwen.json) |
| Pi | Trusted `.pi/mcp.json` or `~/.pi/agent/mcp.json` | [pi.json](../../examples/clients/pi.json) |
| Oh My Pi | `.omp/mcp.json` or `~/.omp/agent/mcp.json` | [omp.json](../../examples/clients/omp.json) |
| OpenCode v2 | `opencode.json` or `opencode.jsonc` | [opencode-v2.json](../../examples/clients/opencode-v2.json) |
| Cline | MCP Servers → Configure MCP Servers | [cline.json](../../examples/clients/cline.json) |
| Roo Code | `.roo/mcp.json` | [roo.json](../../examples/clients/roo.json) |
| Continue | Active `config.yaml` | [continue.yaml](../../examples/clients/continue.yaml) |

Merge the entry for your client into its existing configuration. The
[template index](../../examples/clients/README.md) links each client's upstream
documentation. Templates use public access; add credentials only where needed.

## Codex

```bash
codex mcp add cerngitlab -- uvx cerngitlab-mcp --mode stdio
codex mcp list
```

Alternatively merge this into `~/.codex/config.toml` or a trusted project's
`.codex/config.toml`:

```toml
[mcp_servers.cerngitlab]
command = "uvx"
args = ["cerngitlab-mcp", "--mode", "stdio"]
```

For authenticated access, export `CERNGITLAB_TOKEN` before launching Codex and
add `env_vars = ["CERNGITLAB_TOKEN"]` to the server table. The CLI and IDE
extension share this configuration. Use `/mcp` to inspect the connection.
See the [official Codex MCP guide](https://learn.chatgpt.com/docs/extend/mcp).

## Claude Code and Claude Desktop

```bash
claude mcp add --transport stdio --scope project cerngitlab -- uvx cerngitlab-mcp --mode stdio
claude mcp list
```

Project scope writes `.mcp.json`. Use `--scope user` for a personal server
available across projects, and `/mcp` to inspect its status. For authenticated
Claude Code access, the project configuration can reference an exported token:

```json
{
  "mcpServers": {
    "cerngitlab": {
      "command": "uvx",
      "args": ["cerngitlab-mcp", "--mode", "stdio"],
      "env": {"CERNGITLAB_TOKEN": "${CERNGITLAB_TOKEN}"}
    }
  }
}
```

Omit `env` for public access. See [Claude Code MCP](https://code.claude.com/docs/en/mcp).

For Claude Desktop, merge [claude.json](../../examples/clients/claude.json) into
the MCP configuration opened from **Settings → Developer → Edit Config**, then
restart the app. To authenticate, set the token in that private configuration's
`env` object; do not assume Desktop supports Claude Code's `${...}` expansion.

## IDE clients

- **VS Code:** merge [vscode.json](../../examples/clients/vscode.json) into
  `.vscode/mcp.json` for the Local harness. Use **MCP: List Servers**, start
  `cerngitlab`, and enable its tools in chat. Current Copilot harness sessions
  can use workspace-root `.mcp.json` with `mcpServers`, as shown in
  [copilot.json](../../examples/clients/copilot.json). Match the configuration
  to the selected harness; see Microsoft's
  [configuration reference](https://code.visualstudio.com/docs/agents/reference/mcp-configuration).
- **Cursor:** merge [cursor.json](../../examples/clients/cursor.json) into
  `.cursor/mcp.json` or `~/.cursor/mcp.json`. Open the MCP settings, verify the
  server connects, then enable it in Agent chat. See [Cursor MCP](https://prod.cursor.com/docs/mcp).
- **Zed:** merge [zed.json](../../examples/clients/zed.json) into Zed settings.
  Check **Settings → AI → MCP Servers** and enable the tools for your agent.
  This directly configures Zed Agent; external agents can have their own setup.
  See [Zed MCP](https://zed.dev/docs/ai/mcp).
- **Antigravity:** use [antigravity.json](../../examples/clients/antigravity.json)
  in `.agents/mcp_config.json`, or the global
  `~/.gemini/config/mcp_config.json`. Reload through the MCP server settings.
  The `.gemini` directory name is intentional. See
  [Antigravity MCP](https://antigravity.google/docs/mcp).
- **Cline / Roo Code:** merge their template into the configuration shown in
  the client's MCP settings; Roo also supports `.roo/mcp.json`. Start the
  server and inspect its discovered tools. See
  [Cline](https://github.com/cline/cline/blob/main/docs/mcp/mcp-overview.mdx) and
  [Roo Code](https://roocodeinc.github.io/Roo-Code/features/mcp/using-mcp-in-roo/).
- **Continue:** merge the `mcpServers` list from
  [continue.yaml](../../examples/clients/continue.yaml) into the active YAML
  configuration, retaining existing models. Use Agent mode with a tool-capable
  model. See [Continue's reference](https://docs.continue.dev/reference).

## Other terminal agents

The following clients can register the same server command:

```bash
# GitHub Copilot CLI
copilot mcp add cerngitlab -- uvx cerngitlab-mcp --mode stdio
copilot mcp list

# Qwen Code, project scope
qwen mcp add --scope project cerngitlab uvx cerngitlab-mcp --mode stdio
qwen mcp list

# Antigravity CLI
agy mcp add cerngitlab uvx cerngitlab-mcp --mode stdio
agy mcp list

# Pi
pi mcp add cerngitlab -- uvx cerngitlab-mcp --mode stdio
pi mcp list

# OpenCode
opencode mcp add cerngitlab -- uvx cerngitlab-mcp --mode stdio
opencode mcp list
```

For Pi, `--local` before `--` selects a trusted project's `.pi/mcp.json`.
For Oh My Pi, merge [omp.json](../../examples/clients/omp.json) into
`.omp/mcp.json` or `~/.omp/agent/mcp.json`, then inspect `/mcp` inside `omp`.
OpenCode v2 uses `mcp.servers` and a combined command array; older versions use
different schemas, so prefer the installed CLI's `mcp add` command.
Use the client references in the [template index](../../examples/clients/README.md)
for version-specific flags and settings.

For Goose, run `goose configure`, add a command-line extension, and enter
`uvx cerngitlab-mcp --mode stdio`. Check the extension's discovered tools before
asking it to search GitLab. See the
[Goose extension guide](https://github.com/aaif-goose/goose/blob/main/documentation/docs/getting-started/using-extensions.md).

## Connect to a remote server

Ask the operator for the `/mcp` URL and CERN SSO setup. Complete the deployment's
separate GitLab authorization through `/oauth/authorize` before making tool calls.
See [HTTP deployment](../../README.md#multi-user-http-deployment) for that flow.

With a valid CERN SSO token exported as `CERN_SSO_TOKEN`, Codex can use:

```toml
[mcp_servers.cerngitlab]
url = "https://gitlabmcp.cern.ch/mcp"
bearer_token_env_var = "CERN_SSO_TOKEN"
```

Claude Code's `.mcp.json` can use:

```json
{
  "mcpServers": {
    "cerngitlab": {
      "type": "http",
      "url": "https://gitlabmcp.cern.ch/mcp",
      "headers": {"Authorization": "Bearer ${CERN_SSO_TOKEN}"}
    }
  }
}
```

Replace the example hostname with the operator's URL. Tokens must target the
deployment's configured CERN client audience. CERN registration and the GitLab
authorization are deployment requirements; `codex mcp login` alone does not
establish both. Missing GitLab authorization returns an authorization URL in
the HTTP 403 response. Browser clients must use an origin allowed by the operator.

## Verify and use the connection

After the client reports a connection, ask it to make an actual tool call:

> Use CERN GitLab's `test_connectivity` tool, then search for the public
> `lhcb/DaVinci` project and show its README.

For source browsing, use returned project identifiers and paths:

1. Find the project with `search_projects` or read metadata with `get_project_info`.
2. Use `list_branches` or `list_tags` to choose a ref.
3. Browse `list_project_files` and reuse the returned file path.
4. Call `get_file_content` with the same ref. For a focused read:

   ```json
   {"project": "lhcb/DaVinci", "file_path": "README.md", "ref": "master", "start_line": 1, "end_line": 80}
   ```

   Replace the example branch and filename with values returned by GitLab.

5. Use `search_code` for source matches or `search_lhcb_stack` when a specific
   LHCb stack matters. These searches can require GitLab authentication.

If no tools appear, check that the client uses the intended configuration,
that `uvx` is on its PATH, and that the server command uses stdio mode. For
HTTP authentication errors, check token expiry and GitLab authorization with
the operator. A connected status and a successful tool result verify different
parts of the setup; check both.

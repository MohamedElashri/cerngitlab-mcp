# Client configurations

These templates connect a client to CERN GitLab MCP over local stdio. Merge
the server entry into the destination for your client, retaining other settings.
The templates use public access and contain no credentials.

| Template | Destination | Client reference |
|---|---|---|
| [codex.toml](codex.toml) | Trusted project `.codex/config.toml` or `~/.codex/config.toml` | [Codex](https://learn.chatgpt.com/docs/extend/mcp) |
| [claude.json](claude.json) | Claude Code `.mcp.json`, or Claude Desktop's MCP configuration | [Claude Code](https://code.claude.com/docs/en/mcp) |
| [vscode.json](vscode.json) | `.vscode/mcp.json` for the Local harness | [VS Code](https://code.visualstudio.com/docs/agents/reference/mcp-configuration) |
| [copilot.json](copilot.json) | Trusted workspace `.mcp.json` or `~/.copilot/mcp-config.json` | [Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers) |
| [cursor.json](cursor.json) | `.cursor/mcp.json` or `~/.cursor/mcp.json` | [Cursor](https://prod.cursor.com/docs/mcp) |
| [zed.json](zed.json) | Settings opened by `zed: open settings file` | [Zed](https://zed.dev/docs/ai/mcp) |
| [antigravity.json](antigravity.json) | `.agents/mcp_config.json` or `~/.gemini/config/mcp_config.json` | [Antigravity](https://antigravity.google/docs/mcp) |
| [qwen.json](qwen.json) | `.qwen/settings.json` or `~/.qwen/settings.json` | [Qwen Code](https://qwenlm.github.io/qwen-code-docs/en/users/features/mcp/) |
| [pi.json](pi.json) | Trusted project `.pi/mcp.json` or `~/.pi/agent/mcp.json` | [Pi](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md) |
| [omp.json](omp.json) | `.omp/mcp.json` or `~/.omp/agent/mcp.json` | [Oh My Pi](https://github.com/can1357/oh-my-pi/blob/main/docs/mcp-config.md) |
| [opencode-v2.json](opencode-v2.json) | `opencode.json` or `opencode.jsonc` | [OpenCode v2](https://dev.opencode.ai/v2/docs/mcp-servers/) |
| [cline.json](cline.json) | Cline → MCP Servers → Configure MCP Servers | [Cline](https://github.com/cline/cline/blob/main/docs/mcp/mcp-overview.mdx) |
| [roo.json](roo.json) | `.roo/mcp.json` | [Roo Code](https://roocodeinc.github.io/Roo-Code/features/mcp/using-mcp-in-roo/) |
| [continue.yaml](continue.yaml) | Merge the `mcpServers` list into the active Continue YAML configuration | [Continue](https://docs.continue.dev/reference) |

For a checkout, replace `uvx` with `uv` and use these arguments:

```json
["run", "--directory", "/absolute/path/to/cerngitlab-mcp", "cerngitlab-mcp", "--mode", "stdio"]
```

OpenCode combines the executable and arguments in its `command` array.
Install checkout dependencies with `uv sync --locked --all-groups` first.

For private repositories, configure `CERNGITLAB_TOKEN` in the client's server
environment. Codex's template includes a commented `env_vars` setting for
forwarding an exported token. Other clients' environment-variable expansion
rules vary; keep any literal token in a private user configuration.

See the [integration guide](../../docs/guides/llm_integration.md) for commands,
authentication, remote HTTP, and example tool calls. Client formats vary by
release; use the linked upstream reference for your installed version.

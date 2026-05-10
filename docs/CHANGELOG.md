# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-05-10

### Added
- **CERN SSO OAuth Authentication**: HTTP mode now authenticates users via CERN Single Sign-On (SSO) + GitLab OAuth, replacing the demo environment-variable auth system
  - `OAuthService`: Validates incoming CERN SSO JWT tokens against CERN's JWKS endpoint and orchestrates the GitLab OAuth authorization code flow
  - `SessionStore`: File-backed, per-user OAuth token cache stored under `CERNGITLAB_SESSION_STORAGE_PATH` (default `/tmp/cerngitlab/sessions`)
  - Automatic periodic cleanup of expired sessions (every hour)
  - CERN SSO JWKS response cached for 1 hour to reduce external calls
- **New HTTP API Endpoints**:
  - `GET /oauth/authorize` — Begin or check the OAuth flow for a CERN SSO bearer token
  - `GET /oauth/callback` — Receive the GitLab OAuth authorization code and store the resulting token
  - `DELETE /session` — Revoke the current user's OAuth session
  - `GET /admin/sessions` — List all active sessions (admin use)
- **New Configuration Variables** (all prefixed `CERNGITLAB_`):
  - `CERN_CLIENT_ID` — CERN SSO OAuth client ID
  - `GITLAB_OAUTH_CLIENT_ID` — GitLab OAuth application client ID
  - `GITLAB_OAUTH_CLIENT_SECRET` — GitLab OAuth application client secret
  - `SERVER_BASE_URL` — Public base URL of this server (used for OAuth callback redirect)
  - `SESSION_STORAGE_PATH` — Directory for persisting OAuth session files (default `/tmp/cerngitlab/sessions`)
  - `HOST` — HTTP server bind address (default `0.0.0.0`)
  - `PORT` — HTTP server bind port (default `8000`)
- **New Dependencies**: `PyJWT>=2.8.0` and `aiofiles>=23.0.0`
- **`examples/oauth_server.py`**: Reference startup script demonstrating environment variable configuration for CERN SSO mode

### Changed
- **HTTP Transport** (`transports/http.py`): Replaced the demo API-key auth system with full CERN SSO + GitLab OAuth. Users now authenticate with their real CERN SSO token; GitLab enforces all permissions natively.
- **`McpRequest` / `McpResponse`**: Extracted from `transports/http.py` into a shared `models.py` module for reuse across transports.
- **`exceptions.py`**: Added `AuthorizationRequiredError` to signal when a user needs to complete the GitLab OAuth flow.

### Security
- Session files are written with `0o600` permissions (owner-read-only).
- OAuth `state` parameter is a signed, time-limited token (10-minute window) to prevent CSRF.
- No GitLab tokens are ever returned in API responses or admin listings.

## [0.1.7] - 2026-04-01

### Added
- **Dual-Mode Architecture**: Implemented support for both stdio (single-user) and HTTP (multi-user) modes
  - `--mode stdio|http|auto` CLI option for mode selection
  - Auto-detection based on environment variables (`CERNGITLAB_HTTP_MODE`, `CERNGITLAB_HOST`, `CERNGITLAB_PORT`)
  - Dedicated entry points: `cerngitlab-mcp-stdio` and `cerngitlab-mcp-http`
- **HTTP Multi-User Mode**: New FastAPI-based HTTP transport for centralized deployments
  - RESTful API endpoints: `/tools`, `/tools/{tool_name}`, `/mcp`, `/health`
  - User session isolation with per-user GitLab clients and settings
  - Demo authentication system via environment variables (`CERNGITLAB_DEMO_USER_*`)
  - CORS support for web-based integrations
- **Transport Layer Abstraction**: Refactored architecture with clean separation of concerns
  - `McpServerCore`: Transport-agnostic core logic
  - `StdioTransport`: Single-user stdio mode (maintains backward compatibility)
  - `HttpTransport`: Multi-user HTTP mode with session management

### Changed
- **Server Architecture**: Extracted core logic from transport concerns for better maintainability
- **Configuration**: Added HTTP-specific environment variables for multi-user deployments
- **Dependencies**: Added FastAPI and uvicorn for HTTP mode support

### Technical Details
- **Backward Compatibility**: 100% compatible with existing stdio-based deployments
- **Session Management**: Automatic user session creation, isolation, and cleanup in HTTP mode
- **Error Handling**: Improved error handling across both transport modes

## [0.1.6] - 2026-03-11

### Added
- **`cerngitlab-cli` Command-Line Interface**: Added a CLI tool for users to use the same tools provided by `cerngitlab-mcp` directly from the terminal. It can be used + the `SKILLS.md` file for skill + cli workflow.

## [0.1.5] - 2026-03-05

### Added
- **`search_lhcb_stack` Tool**: Added a dedicated tool for searching code across `LHCb` software stacks (e.g., 'sim11'). Automatically resolves the correct Git references for projects in that stack using the nightly API, so users no longer need to manually find and provide `ref` parameters.
- **Stack Resolver**: Implemented internal API client to resolve `LHCb` nightly stack properties. Includes automatic fallback if the API is down.

## [0.1.4] - 2026-03-04

### Added
- **Branch/Tag Filtering**: Added support for restricting code searches to specific Git branches or tags via the `CERNGITLAB_DEFAULT_REF` environment variable and the `ref` parameter in the `search_code` tool.

### Changed
- **Configuration Option**: New `CERNGITLAB_DEFAULT_REF` environment variable allows setting a default branch or tag for all code searches. When empty (default), searches across all branches.
- **Tool Parameter**: `search_code` tool now accepts an optional `ref` parameter to override the default branch/tag on a per-search basis.

## [0.1.3] - 2026-02-17

### Breaking Changes
- **Tool Renames**: Renamed several tools to align with GitLab terminology:
    - `search_repositories` -> `search_projects`
    - `get_repository_info` -> `get_project_info`
    - `list_repository_files` -> `list_project_files`
    - `get_repository_readme` -> `get_project_readme`

### Documentation
- Updated README and docs to reflect the new tool names.

## [0.1.2] - 2026-02-17

### Added
- **`inspect_project` Tool**: Consolidated analysis tool that detects build systems, parses dependencies (Python, C++, Fortran), and analyzes CI/CD configuration. Replaces `analyze_dependencies`, `get_build_config`, and `get_ci_config`.
- **`search_issues` Tool**: Start searching for issues and discussions in GitLab projects to find usage examples and solutions.
- **Pagination Support**: Added `page` and `per_page` parameters to `search_code` tool.

### Changed
- **`search_code` Performance**: Parallelized the fallback search mechanism (used when advanced search is unavailable) to significantly improve performance on large repositories.
- **Documentation**: Updated README with new tool usage examples and descriptions.

### Removed
- `analyze_dependencies` tool (merged into `inspect_project`).
- `get_build_config` tool (merged into `inspect_project`).
- `get_ci_config` tool (merged into `inspect_project`).

## [0.1.1] - 2026-02-10

### Changed
- Changed minimum Python version to 3.10 from 3.14


### Removed
- Removed unused imports


## [0.1.0] - 2026-02-07

### Added
- Initial release of `cerngitlab-mcp` server.
- Basic tools for repository search, file retrieval, and documentation access.

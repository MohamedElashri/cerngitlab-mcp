# Development Guide

## Tools Reference

### Project Discovery

#### `search_projects`
Search for public projects (which include repositories, issues, wikis) by keywords, topics, or programming language.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | string | no | Search query (matches name, description) |
| `language` | string | no | Filter by language (e.g. `python`, `c++`) |
| `topic` | string | no | Filter by topic (e.g. `physics`, `lhcb`) |
| `sort_by` | string | no | Sort field: `last_activity_at`, `name`, `created_at`, `stars` |
| `order` | string | no | `desc` or `asc` |
| `per_page` | integer | no | Results count (1–100, default: 20) |

#### `get_project_info`
Get detailed information about a specific project including languages, statistics, and license.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path (e.g. `lhcb/allen`) |

### Repository Content

#### `list_project_files`
Browse the file tree of a project's repository.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `path` | string | no | Subdirectory path |
| `ref` | string | no | Branch/tag/commit |
| `recursive` | boolean | no | List recursively |
| `per_page` | integer | no | Results count (default: 100) |

#### `get_file_content`
Retrieve file content with binary detection and syntax highlighting hints.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `file_path` | string | yes | Path within repository |
| `ref` | string | no | Branch/tag/commit |

#### `get_project_readme`
Get the README file, automatically trying common filenames (README.md, .rst, .txt, etc.).

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `ref` | string | no | Branch/tag/commit |

#### `search_code`
Search for code across repositories. Falls back to file-level grep when advanced search is unavailable. **Requires authentication for global search.**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `search_term` | string | yes | Code/text to search for |
| `project` | string | no | Limit to specific project |
| `scope` | string | no | `blobs` (content) or `filenames` |
| `page` | integer | no | Page number (default: 1) |
| `per_page` | integer | no | Results count (default: 20) |

### Context & Analysis

#### `inspect_project`
Comprehensive analysis of a project. Detects build systems (CMake, Make, Python, etc.), ecosystem dependencies (ROOT, Scipy, etc.), and CI/CD configuration.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `ref` | string | no | Branch/tag/commit |

#### `search_issues`
Search for issues and discussions in a project.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `search_term` | string | yes | Keywords to search for |
| `project` | string | no | Limit to specific project |
| `state` | string | no | `opened`, `closed`, or `all` |
| `per_page` | integer | no | Results count (default: 10) |

#### `get_wiki_pages`
Access project wiki pages. **Requires authentication.**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `page_slug` | string | no | Specific page slug (omit to list all) |

### Release & Version Tracking

#### `list_releases`
List releases for a project.

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
List project tags with optional filtering.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Numeric ID or path |
| `search` | string | no | Filter by name prefix |
| `sort` | string | no | `asc` or `desc` |
| `per_page` | integer | no | Results count (default: 20) |

### Utility

#### `test_connectivity`
Test connection to the CERN GitLab instance. No parameters required.

---

## Development Setup

```bash
# Clone and install dev dependencies
git clone https://github.com/MohamedElashri/cerngitlab-mcp
cd cerngitlab-mcp
uv sync

# Run unit tests
uv run pytest -v

# Run integration tests (requires network access to gitlab.cern.ch)
uv run python tests/test_integration.py

# Lint
uv run ruff check .
```


## Testing

- **Unit tests** (`tests/test_tools.py`): All tools tested with mocked HTTP via `pytest-httpx`. Run with `uv run pytest -v`.
- **Integration tests** (`tests/test_integration.py`): Standalone script hitting the real CERN GitLab API. Run with `uv run python tests/test_integration.py`.

## Releasing

1. Update version in `pyproject.toml` and `src/cerngitlab_mcp/__init__.py`
2. Commit and push to `main`
3. Tag the release: `git tag v0.1.0 && git push origin v0.1.0`
4. The GitHub Actions release workflow will automatically build and publish to PyPI

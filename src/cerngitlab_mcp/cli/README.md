# CERN GitLab CLI

A command-line interface for interacting with CERN GitLab repositories. This cli provides 14 tools for searching, browsing, and analyzing HEP (High Energy Physics) code, documentation, and examples from CERN GitLab.

## Overview

**Purpose**: Discover and analyze HEP code repositories, examine project structures, search for code patterns, and understand build systems used at CERN.

**Authentication**: Works with public repositories by default. Optional token for private repos and advanced features.

**Base URL**: `https://gitlab.cern.ch` (configurable)

---

## Configuration

All configuration is done via environment variables prefixed with `CERNGITLAB_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `CERNGITLAB_GITLAB_URL` | `https://gitlab.cern.ch` | GitLab instance URL |
| `CERNGITLAB_TOKEN` | *(empty)* | Personal access token (optional) |
| `CERNGITLAB_TIMEOUT` | `30` | HTTP timeout in seconds |
| `CERNGITLAB_MAX_RETRIES` | `3` | Max retries for failed requests |
| `CERNGITLAB_RATE_LIMIT_PER_MINUTE` | `300` | API rate limit |
| `CERNGITLAB_LOG_LEVEL` | `INFO` | Logging level |
| `CERNGITLAB_DEFAULT_REF` | *(empty)* | Default Git branch/tag (e.g., `main`, `master`) |

### Authentication Modes

- **Without token**: Access to all public repositories (sufficient for most use cases)
- **With token**: Additional access to internal/private projects, code search, and wiki pages

To create a token:
1. Visit https://gitlab.cern.ch/-/user_settings/personal_access_tokens
2. Create a token with `read_api` scope
3. Set `CERNGITLAB_TOKEN=glpat-xxxxxxxxxxxx`

---

## Tools

### 1. `search-projects`

Search for public CERN GitLab projects by keywords, topics, or programming language.

**Use case**: Discover HEP repositories related to specific frameworks, languages, or physics experiments.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--query` | string | No | - | Search query (matches project name, description) |
| `--language` | string | No | - | Filter by language (e.g., `python`, `c++`, `fortran`) |
| `--topic` | string | No | - | Filter by topic tag (e.g., `physics`, `root`, `lhcb`) |
| `--sort-by` | string | No | `last_activity_at` | Sort field: `last_activity_at`, `name`, `created_at`, `stars` |
| `--order` | string | No | `desc` | Sort order: `desc` or `asc` |
| `--per-page` | integer | No | `20` | Results count (1–100) |

#### Output Format

```json
[
  {
    "id": 12345,
    "name": "ProjectName",
    "path_with_namespace": "group/project",
    "description": "Project description text",
    "web_url": "https://gitlab.cern.ch/group/project",
    "default_branch": "main",
    "topics": ["physics", "root"],
    "star_count": 42,
    "forks_count": 15,
    "last_activity_at": "2025-03-10T10:30:00Z",
    "created_at": "2020-01-15T08:00:00Z",
    "visibility": "public"
  }
]
```

#### Example Usage

```bash
# Search for Python ROOT analysis projects
cerngitlab-cli search-projects --query "ROOT analysis" --language python --sort-by stars

# Find LHCb-related repositories
cerngitlab-cli search-projects --topic lhcb --per-page 50
```

---

### 2. `get-project-info`

Get detailed metadata about a specific project including languages, statistics, and license.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path (e.g., `12345` or `lhcb/allen`) |

#### Output Format

```json
{
  "id": 12345,
  "name": "ProjectName",
  "path_with_namespace": "group/project",
  "description": "...",
  "web_url": "...",
  "default_branch": "main",
  "languages": ["Python", "C++"],
  "language_percentages": {"Python": 60.5, "C++": 39.5},
  "star_count": 42,
  "forks_count": 15,
  "open_issues_count": 23,
  "license": "MIT",
  "visibility": "public",
  "created_at": "2020-01-15T08:00:00Z",
  "last_activity_at": "2025-03-10T10:30:00Z"
}
```

#### Example Usage

```bash
cerngitlab-cli get-project-info --project lhcb/DaVinci
```

---

### 3. `list-files`

List files and directories in a project's repository.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--project` | string | Yes | - | Project ID or path |
| `--path` | string | No | `/` | Subdirectory path to list |
| `--ref` | string | No | default branch | Branch/tag/commit |
| `--recursive` | boolean | No | `false` | List recursively |
| `--per-page` | integer | No | `100` | Results count |

#### Output Format

```json
[
  {
    "type": "tree",
    "path": "src",
    "name": "src"
  },
  {
    "type": "blob",
    "path": "README.md",
    "name": "README.md"
  }
]
```

#### Example Usage

```bash
# List root directory
cerngitlab-cli list-files --project atlas/athena

# List specific subdirectory
cerngitlab-cli list-files --project lhcb/Boole --path src/Kernel

# Recursive listing
cerngitlab-cli list-files --project mygroup/myproject --recursive
```

---

### 4. `get-file`

Retrieve the content of a specific file from a repository.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--file-path` | string | Yes | Path to file (e.g., `src/main.py`) |
| `--ref` | string | No | Branch/tag/commit |

#### Output Format

```json
{
  "file_name": "main.py",
  "file_path": "src/main.py",
  "size": 1234,
  "ref": "main",
  "last_commit_id": "abc123...",
  "content_sha256": "sha256hash...",
  "is_binary": false,
  "content": "#!/usr/bin/env python\n...",
  "language": "python"
}
```

For binary files:
```json
{
  "file_name": "data.root",
  "is_binary": true,
  "content": "[Binary file, 1048576 bytes]"
}
```

#### Example Usage

```bash
cerngitlab-cli get-file --project lhcb/DaVinci --file-path README.md
cerngitlab-cli get-file --project atlas/athena --file-path CMakeLists.txt --ref main
```

---

### 5. `get-readme`

Get the README content for a project (automatically finds README.md, .rst, .txt, etc.).

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--ref` | string | No | Branch/tag/commit |

#### Output Format

```json
{
  "file_name": "README.md",
  "content": "# Project Title\n\nDescription...",
  "language": "markdown"
}
```

#### Example Usage

```bash
cerngitlab-cli get-readme --project lhcb/allen
```

---

### 6. `search-code`

Search for code snippets across repositories. Returns matching files with line-level context.

**Requires authentication** for global search on CERN GitLab.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--search-term` | string | Yes | - | Code/text to search for |
| `--project` | string | No | - | Limit to specific project |
| `--scope` | string | No | `blobs` | `blobs` (content) or `filenames` |
| `--ref` | string | No | - | Git branch/tag to search within |
| `--page` | integer | No | `1` | Page number |
| `--per-page` | integer | No | `20` | Results count (max 100) |

#### Output Format

```json
{
  "search_term": "RooFit",
  "scope": "blobs",
  "project": "(global)",
  "page": 1,
  "per_page": 20,
  "total_results": 15,
  "results": [
    {
      "file_name": "fitting.py",
      "file_path": "src/analysis/fitting.py",
      "project_id": 12345,
      "data": "import ROOT\nfrom ROOT import RooFit\n...",
      "ref": "main",
      "startline": 10
    }
  ]
}
```

#### Example Usage

```bash
# Global search for RooFit usage
cerngitlab-cli search-code --search-term "RooFit" --per-page 10

# Search within specific project
cerngitlab-cli search-code --search-term "main()" --project lhcb/DaVinci
```

---

### 7. `search-lhcb-stack`

Search for code within a specific LHCb software stack (e.g., 'sim11'). Automatically resolves correct Git references using LHCb nightly API.

**Requires authentication** for global search.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--search-term` | string | Yes | Code/text to search for |
| `--stack` | string | Yes | Software stack name (e.g., `sim11`) |
| `--project` | string | No | Limit to specific project |
| `--scope` | string | No | `blobs` or `filenames` |
| `--ref` | string | No | Override automatic ref resolution |
| `--page` | integer | No | Page number |
| `--per-page` | integer | No | Results count |

#### Output Format

Same as `search-code`, with automatically resolved branch references.

#### Example Usage

```bash
# Search sim11 stack for initialization code
cerngitlab-cli search-lhcb-stack --search-term "initialize()" --stack sim11

# Search specific project in stack
cerngitlab-cli search-lhcb-stack --search-term "BooleInit" --stack sim11 --project lhcb/Boole
```

---

### 8. `search-issues`

Search for issues and discussions in a project.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--search-term` | string | Yes | - | Keywords to search for |
| `--project` | string | No | - | Limit to specific project |
| `--state` | string | No | `opened` | `opened`, `closed`, or `all` |
| `--per-page` | integer | No | `10` | Results count |

#### Output Format

```json
[
  {
    "id": 123,
    "iid": 45,
    "project_id": 67890,
    "title": "Issue title",
    "description": "Issue description...",
    "state": "opened",
    "created_at": "2025-01-10T09:00:00Z",
    "updated_at": "2025-03-05T14:30:00Z",
    "web_url": "https://gitlab.cern.ch/group/project/-/issues/45"
  }
]
```

#### Example Usage

```bash
cerngitlab-cli search-issues --search-term "segmentation fault" --project atlas/athena
```

---

### 9. `get-wiki`

Access project wiki pages. **Requires authentication.**

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--page-slug` | string | No | Specific page slug (omit to list all) |

#### Output Format

List all pages:
```json
[
  {
    "slug": "home",
    "title": "Home",
    "url": "https://gitlab.cern.ch/group/project/-/wikis/home"
  }
]
```

Get specific page:
```json
{
  "slug": "installation",
  "title": "Installation Guide",
  "content": "# Installation\n\nSteps to install..."
}
```

#### Example Usage

```bash
# List all wiki pages
cerngitlab-cli get-wiki --project lhcb/DaVinci

# Get specific page
cerngitlab-cli get-wiki --project lhcb/DaVinci --page-slug installation
```

---

### 10. `inspect-project`

Comprehensive analysis of a project's structure, build system, dependencies, and CI/CD configuration.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--ref` | string | No | Branch/tag/commit |

#### Output Format

```json
{
  "project": "lhcb/allen",
  "ref": "main",
  "ecosystems": ["python", "cpp"],
  "build_systems": ["cmake", "python-build"],
  "dependencies": [
    {
      "source_file": "requirements.txt",
      "ecosystem": "python",
      "count": 15,
      "items": [
        {"name": "numpy", "version_spec": ">=1.20"},
        {"name": "scipy", "version_spec": ""}
      ]
    }
  ],
  "ci_config": {
    "found": true,
    "analysis": {
      "stages": ["build", "test", "deploy"],
      "jobs": ["build_linux", "test_unit", "deploy_prod"],
      "image": "python:3.11"
    },
    "raw_preview": "stages:\n  - build\n  - test..."
  },
  "files_analyzed": 8
}
```

#### Example Usage

```bash
cerngitlab-cli inspect-project --project lhcb/allen
```

---

### 11. `list-releases`

List releases for a project.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--project` | string | Yes | - | Project ID or path |
| `--per-page` | integer | No | `20` | Results count |

#### Output Format

```json
[
  {
    "tag_name": "v1.2.0",
    "name": "Release 1.2.0",
    "description": "Release notes...",
    "created_at": "2025-02-15T10:00:00Z",
    "published_at": "2025-02-15T12:00:00Z",
    "web_url": "https://gitlab.cern.ch/group/project/-/releases/v1.2.0"
  }
]
```

#### Example Usage

```bash
cerngitlab-cli list-releases --project lhcb/DaVinci
```

---

### 12. `get-release`

Get detailed information about a specific release.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--tag-name` | string | Yes | Release tag (e.g., `v1.0.0`) |

#### Output Format

```json
{
  "tag_name": "v1.2.0",
  "name": "Release 1.2.0",
  "description": "Full release notes...",
  "created_at": "2025-02-15T10:00:00Z",
  "published_at": "2025-02-15T12:00:00Z",
  "web_url": "...",
  "assets": [
    {"name": "source.tar.gz", "url": "..."}
  ]
}
```

#### Example Usage

```bash
cerngitlab-cli get-release --project lhcb/DaVinci --tag-name v1.2.0
```

---

### 13. `list-tags`

List project tags with optional filtering.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--project` | string | Yes | - | Project ID or path |
| `--search` | string | No | - | Filter by name prefix |
| `--sort` | string | No | `desc` | `asc` or `desc` |
| `--per-page` | integer | No | `20` | Results count |

#### Output Format

```json
[
  {
    "name": "v1.2.0",
    "message": "Release 1.2.0",
    "target": "main",
    "commit": {
      "id": "abc123...",
      "short_id": "abc123",
      "created_at": "2025-02-15T10:00:00Z"
    }
  }
]
```

#### Example Usage

```bash
cerngitlab-cli list-tags --project lhcb/DaVinci --search v1
```

---

### 14. `test-connection`

Test connectivity to the CERN GitLab instance.

#### Input Parameters

None.

#### Output Format

```json
{
  "status": "connected",
  "gitlab_url": "https://gitlab.cern.ch",
  "authenticated": true,
  "version": "16.0.0",
  "revision": "abc123",
  "public_access": true
}
```

#### Example Usage

```bash
cerngitlab-cli test-connection
```

---

## Error Handling

All commands return structured JSON errors:

```json
{
  "error": "Error message describing what went wrong"
}
```

Common errors:
- **Authentication required**: Tool needs a token but none provided
- **Project not found**: Invalid project ID or path
- **Rate limit exceeded**: Too many requests, wait and retry
- **File not found**: Requested file doesn't exist in repository

---

## Usage Patterns

### Discover analysis frameworks
```bash
cerngitlab-cli search-projects --query "ROOT analysis" --language python --sort-by stars
```

### Understand a project
```bash
cerngitlab-cli get-readme --project lhcb/DaVinci
cerngitlab-cli list-files --project lhcb/DaVinci
cerngitlab-cli inspect-project --project lhcb/DaVinci
```

### Find code examples
```bash
cerngitlab-cli search-code --search-term "RooFit" --per-page 10
cerngitlab-cli search-lhcb-stack --search-term "initialize" --stack sim11
```

### Track releases
```bash
cerngitlab-cli list-releases --project lhcb/DaVinci
cerngitlab-cli get-release --project lhcb/DaVinci --tag-name v1.2.0
```

### Analyze dependencies
```bash
cerngitlab-cli inspect-project --project atlas/athena
```

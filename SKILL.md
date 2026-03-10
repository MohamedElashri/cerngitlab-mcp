---
name: cerngitlab-cli
description: "Search, browse, and analyze CERN GitLab repositories for HEP code, documentation, and examples. Use this skill whenever the user mentions CERN GitLab, LHCb/ATLAS/CMS code, HEP software stacks, or wants to find code patterns, inspect build systems, read READMEs, search issues, or explore releases in gitlab.cern.ch projects. Also trigger when the user references specific CERN projects like DaVinci, Allen, Athena, Gauss, Moore, Boole, or any gitlab.cern.ch URL."
---

# CERN GitLab CLI

A command-line interface for interacting with CERN GitLab (`gitlab.cern.ch`). Provides 14 tools for searching, browsing, and analyzing HEP code repositories.

The CLI binary is `cerngitlab-cli`. All commands return structured JSON. Public repositories work without authentication; private/internal repos and code search require a token.

## Configuration

Set environment variables prefixed with `CERNGITLAB_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `CERNGITLAB_GITLAB_URL` | `https://gitlab.cern.ch` | GitLab instance URL |
| `CERNGITLAB_TOKEN` | *(empty)* | Personal access token (`read_api` scope) |
| `CERNGITLAB_TIMEOUT` | `30` | HTTP timeout in seconds |
| `CERNGITLAB_MAX_RETRIES` | `3` | Max retries for failed requests |
| `CERNGITLAB_RATE_LIMIT_PER_MINUTE` | `300` | API rate limit |
| `CERNGITLAB_LOG_LEVEL` | `INFO` | Logging level |
| `CERNGITLAB_DEFAULT_REF` | *(empty)* | Default Git branch/tag |

To create a token: visit `https://gitlab.cern.ch/-/user_settings/personal_access_tokens`, create with `read_api` scope, then `export CERNGITLAB_TOKEN=glpat-xxxxxxxxxxxx`.

## Tool Selection Guide

| Goal | Tool | Auth Required |
|------|------|:---:|
| Find repos by keyword/topic/language | `search-projects` | No |
| Get project metadata & stats | `get-project-info` | No |
| Browse directory tree | `list-files` | No |
| Read a specific file | `get-file` | No |
| Read README (auto-detected) | `get-readme` | No |
| Search code globally | `search-code` | **Yes** |
| Search code in LHCb stack | `search-lhcb-stack` | **Yes** |
| Search issues | `search-issues` | No |
| Access wiki pages | `get-wiki` | **Yes** |
| Full project analysis (build, deps, CI) | `inspect-project` | No |
| List releases | `list-releases` | No |
| Get specific release details | `get-release` | No |
| List tags (filterable) | `list-tags` | No |
| Test connection & auth status | `test-connection` | No |

## Common Workflows

### Discover repositories

```bash
# Find Python ROOT analysis projects, sorted by stars
cerngitlab-cli search-projects --query "ROOT analysis" --language python --sort-by stars

# Find all LHCb-tagged repositories
cerngitlab-cli search-projects --topic lhcb --per-page 50
```

### Understand a project

```bash
# Get README, file tree, and full project inspection in sequence
cerngitlab-cli get-readme --project lhcb/DaVinci
cerngitlab-cli list-files --project lhcb/DaVinci --path src/
cerngitlab-cli inspect-project --project lhcb/DaVinci
```

`inspect-project` is the most powerful single command — it analyzes build systems, dependencies, CI/CD config, and language breakdown in one call.

### Find code patterns

```bash
# Global code search (requires token)
cerngitlab-cli search-code --search-term "RooFit" --per-page 10

# Search within a specific project
cerngitlab-cli search-code --search-term "PVFinder" --project lhcb/allen

# Search within an LHCb software stack (auto-resolves correct git refs)
cerngitlab-cli search-lhcb-stack --search-term "initialize()" --stack sim11
```

### Track releases and tags

```bash
cerngitlab-cli list-releases --project lhcb/DaVinci
cerngitlab-cli get-release --project lhcb/DaVinci --tag-name v1.2.0
cerngitlab-cli list-tags --project lhcb/DaVinci --search v1
```

## Error Handling

All commands return JSON errors: `{"error": "Error message"}`. Common causes:

- **"Authentication required"**: Tool needs `CERNGITLAB_TOKEN` but none is set.
- **"Project not found"**: Wrong project ID or path — verify with `search-projects`.
- **"Rate limit exceeded"**: Wait and retry (default: 300 req/min).
- **"File not found"**: Check `--ref` branch and verify path with `list-files`.

---

## Tool Reference

### 1. search-projects

Search for public CERN GitLab projects by keywords, topics, or programming language.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--query` | string | No | - | Matches project name and description |
| `--language` | string | No | - | Filter by language (`python`, `c++`, `fortran`) |
| `--topic` | string | No | - | Filter by topic tag (`physics`, `root`, `lhcb`) |
| `--sort-by` | string | No | `last_activity_at` | `last_activity_at`, `name`, `created_at`, `stars` |
| `--order` | string | No | `desc` | `desc` or `asc` |
| `--per-page` | integer | No | `20` | Results count (1–100) |

**Output:** Array of project objects:
```json
{
  "id": 12345,
  "name": "ProjectName",
  "path_with_namespace": "group/project",
  "description": "...",
  "web_url": "https://gitlab.cern.ch/group/project",
  "default_branch": "main",
  "topics": ["physics", "root"],
  "star_count": 42,
  "forks_count": 15,
  "last_activity_at": "2025-03-10T10:30:00Z",
  "created_at": "2020-01-15T08:00:00Z",
  "visibility": "public"
}
```

---

### 2. get-project-info

Get detailed metadata about a specific project including languages, statistics, and license.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path (e.g., `12345` or `lhcb/allen`) |

**Output:** Single project object with all fields from `search-projects` plus:
```json
{
  "languages": ["Python", "C++"],
  "language_percentages": {"Python": 60.5, "C++": 39.5},
  "open_issues_count": 23,
  "license": "MIT"
}
```

---

### 3. list-files

List files and directories in a project's repository.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--project` | string | Yes | - | Project ID or path |
| `--path` | string | No | `/` | Subdirectory path to list |
| `--ref` | string | No | default branch | Branch/tag/commit |
| `--recursive` | boolean | No | `false` | List recursively |
| `--per-page` | integer | No | `100` | Results count |

**Output:** Array of entries:
```json
{"type": "tree", "path": "src", "name": "src"}
{"type": "blob", "path": "README.md", "name": "README.md"}
```

---

### 4. get-file

Retrieve the content of a specific file from a repository.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--file-path` | string | Yes | Path to file (e.g., `src/main.py`) |
| `--ref` | string | No | Branch/tag/commit |

**Output:**
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

Binary files return `"is_binary": true` and `"content": "[Binary file, N bytes]"`.

---

### 5. get-readme

Get the README content for a project. Automatically finds README.md, .rst, .txt, etc.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--ref` | string | No | Branch/tag/commit |

**Output:**
```json
{
  "file_name": "README.md",
  "content": "# Project Title\n\nDescription...",
  "language": "markdown"
}
```

---

### 6. search-code

Search for code snippets across repositories. Returns matching files with line-level context. **Requires authentication** for global search on CERN GitLab.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--search-term` | string | Yes | - | Code/text to search for |
| `--project` | string | No | - | Limit to specific project |
| `--scope` | string | No | `blobs` | `blobs` (content) or `filenames` |
| `--ref` | string | No | - | Branch/tag to search within |
| `--page` | integer | No | `1` | Page number |
| `--per-page` | integer | No | `20` | Results count (max 100) |

**Output:**
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

---

### 7. search-lhcb-stack

Search for code within a specific LHCb software stack (e.g., `sim11`). Automatically resolves correct Git references using the LHCb nightly build API.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--search-term` | string | Yes | Code/text to search for |
| `--stack` | string | Yes | Stack name (e.g., `sim11`) |
| `--project` | string | No | Limit to specific project |
| `--scope` | string | No | `blobs` or `filenames` |
| `--ref` | string | No | Override automatic ref resolution |
| `--page` | integer | No | Page number |
| `--per-page` | integer | No | Results count |

**Output:** Same format as `search-code`, with automatically resolved branch references.

---

### 8. search-issues

Search for issues and discussions in a project.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--search-term` | string | Yes | - | Keywords to search for |
| `--project` | string | No | - | Limit to specific project |
| `--state` | string | No | `opened` | `opened`, `closed`, or `all` |
| `--per-page` | integer | No | `10` | Results count |

**Output:**
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

---

### 9. get-wiki

Access project wiki pages. **Requires authentication.**

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--page-slug` | string | No | Specific page slug (omit to list all pages) |

**Output (list mode):**
```json
[{"slug": "home", "title": "Home", "url": "https://gitlab.cern.ch/group/project/-/wikis/home"}]
```

**Output (specific page):**
```json
{"slug": "installation", "title": "Installation Guide", "content": "# Installation\n\nSteps..."}
```

---

### 10. inspect-project

Comprehensive analysis of a project's structure, build system, dependencies, and CI/CD configuration. This is the most informative single command for understanding a project.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--ref` | string | No | Branch/tag/commit |

**Output:**
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

---

### 11. list-releases

List releases for a project.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--project` | string | Yes | - | Project ID or path |
| `--per-page` | integer | No | `20` | Results count |

**Output:**
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

---

### 12. get-release

Get detailed information about a specific release.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--tag-name` | string | Yes | Release tag (e.g., `v1.0.0`) |

**Output:** Same as `list-releases` entry, plus `assets` array:
```json
{"assets": [{"name": "source.tar.gz", "url": "..."}]}
```

---

### 13. list-tags

List project tags with optional filtering.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--project` | string | Yes | - | Project ID or path |
| `--search` | string | No | - | Filter by name prefix |
| `--sort` | string | No | `desc` | `asc` or `desc` |
| `--per-page` | integer | No | `20` | Results count |

**Output:**
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

---

### 14. test-connection

Test connectivity to the CERN GitLab instance. Takes no parameters.

**Output:**
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
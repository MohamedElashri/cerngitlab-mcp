---
name: cerngitlab-cli
description: "Search, browse, and analyze CERN GitLab repositories for HEP code, documentation, and examples. Use this skill whenever the user mentions CERN GitLab, LHCb/ATLAS/CMS code, HEP software stacks, or wants to find code patterns, inspect build systems, read READMEs, search issues, or explore releases in gitlab.cern.ch projects. Also trigger when the user references specific CERN projects like DaVinci, Allen, Athena, Gauss, Moore, Boole, or any gitlab.cern.ch URL."
---

# CERN GitLab CLI

A command-line interface for interacting with CERN GitLab (`gitlab.cern.ch`). Provides 14 tools for searching, browsing, and analyzing HEP code repositories.

## Quick Start

The CLI binary is `cerngitlab-cli`. All commands return structured JSON. Public repositories work without authentication; private/internal repos and code search require a token.

## Configuration

Set environment variables prefixed with `CERNGITLAB_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `CERNGITLAB_GITLAB_URL` | `https://gitlab.cern.ch` | GitLab instance URL |
| `CERNGITLAB_TOKEN` | *(empty)* | Personal access token (`read_api` scope) |
| `CERNGITLAB_TIMEOUT` | `30` | HTTP timeout in seconds |
| `CERNGITLAB_DEFAULT_REF` | *(empty)* | Default Git branch/tag |

To create a token: visit `https://gitlab.cern.ch/-/user_settings/personal_access_tokens`, create with `read_api` scope, then `export CERNGITLAB_TOKEN=glpat-xxxxxxxxxxxx`.

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

# Search within a specific project (no token needed for public projects)
cerngitlab-cli search-code --search-term "PVFinder" --project lhcb/allen

# Search within an LHCb software stack (auto-resolves correct git refs)
cerngitlab-cli search-lhcb-stack --search-term "initialize()" --stack sim11
```

### Read specific files

```bash
cerngitlab-cli get-file --project lhcb/allen --file-path CMakeLists.txt --ref main
```

### Track releases and tags

```bash
cerngitlab-cli list-releases --project lhcb/DaVinci
cerngitlab-cli get-release --project lhcb/DaVinci --tag-name v1.2.0
cerngitlab-cli list-tags --project lhcb/DaVinci --search v1
```

### Search issues

```bash
cerngitlab-cli search-issues --search-term "segfault" --project atlas/athena --state all
```

### Access wiki pages (requires token)

```bash
cerngitlab-cli get-wiki --project lhcb/DaVinci
cerngitlab-cli get-wiki --project lhcb/DaVinci --page-slug installation
```

### Verify connectivity

```bash
cerngitlab-cli test-connection
```

## Tool Selection Guide

| Goal | Tool | Notes |
|------|------|-------|
| Find repos by keyword/topic/language | `search-projects` | No auth needed |
| Get project metadata & stats | `get-project-info` | No auth needed |
| Browse directory tree | `list-files` | Use `--recursive` for full tree |
| Read a file | `get-file` | Returns content or binary indicator |
| Read README | `get-readme` | Auto-finds README.md/.rst/.txt |
| Search code globally | `search-code` | **Requires token** |
| Search code in LHCb stack | `search-lhcb-stack` | **Requires token**; auto-resolves refs |
| Search issues | `search-issues` | Filter by `opened`/`closed`/`all` |
| Access wiki | `get-wiki` | **Requires token** |
| Full project analysis | `inspect-project` | Build system, deps, CI/CD |
| List releases | `list-releases` | Sorted by date |
| Get specific release | `get-release` | By tag name |
| List tags | `list-tags` | Filterable by prefix |
| Test connection | `test-connection` | Shows auth status & version |

## Error Handling

All commands return JSON errors: `{"error": "Error message"}`. Common causes:

- **"Authentication required"**: The tool needs a `CERNGITLAB_TOKEN` but none is set.
- **"Project not found"**: Wrong project ID or path — verify with `search-projects` first.
- **"Rate limit exceeded"**: Wait a moment and retry (default limit: 300 req/min).
- **"File not found"**: Check the `--ref` branch and verify the path with `list-files`.

## Detailed Tool Reference

For complete parameter schemas and output formats for all 14 tools, read `references/tools-reference.md`.
# CERN GitLab CLI — Tools Reference

Complete parameter schemas and output formats for all 14 tools.

## Table of Contents

1. [search-projects](#1-search-projects)
2. [get-project-info](#2-get-project-info)
3. [list-files](#3-list-files)
4. [get-file](#4-get-file)
5. [get-readme](#5-get-readme)
6. [search-code](#6-search-code)
7. [search-lhcb-stack](#7-search-lhcb-stack)
8. [search-issues](#8-search-issues)
9. [get-wiki](#9-get-wiki)
10. [inspect-project](#10-inspect-project)
11. [list-releases](#11-list-releases)
12. [get-release](#12-get-release)
13. [list-tags](#13-list-tags)
14. [test-connection](#14-test-connection)

---

## 1. search-projects

Search for public CERN GitLab projects by keywords, topics, or programming language.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--query` | string | No | - | Matches project name and description |
| `--language` | string | No | - | Filter by language (`python`, `c++`, `fortran`, etc.) |
| `--topic` | string | No | - | Filter by topic tag (`physics`, `root`, `lhcb`, etc.) |
| `--sort-by` | string | No | `last_activity_at` | One of: `last_activity_at`, `name`, `created_at`, `stars` |
| `--order` | string | No | `desc` | `desc` or `asc` |
| `--per-page` | integer | No | `20` | Results count (1–100) |

**Output:** Array of project objects with `id`, `name`, `path_with_namespace`, `description`, `web_url`, `default_branch`, `topics`, `star_count`, `forks_count`, `last_activity_at`, `created_at`, `visibility`.

---

## 2. get-project-info

Get detailed metadata about a specific project including languages, statistics, and license.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path (e.g., `12345` or `lhcb/allen`) |

**Output:** Single project object with all fields from `search-projects` plus `languages` (array), `language_percentages` (object), `open_issues_count`, `license`.

---

## 3. list-files

List files and directories in a project's repository.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--project` | string | Yes | - | Project ID or path |
| `--path` | string | No | `/` | Subdirectory path to list |
| `--ref` | string | No | default branch | Branch/tag/commit |
| `--recursive` | boolean | No | `false` | List recursively |
| `--per-page` | integer | No | `100` | Results count |

**Output:** Array of objects with `type` (`tree` for directory, `blob` for file), `path`, `name`.

---

## 4. get-file

Retrieve the content of a specific file from a repository.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--file-path` | string | Yes | Path to file (e.g., `src/main.py`) |
| `--ref` | string | No | Branch/tag/commit |

**Output:** Object with `file_name`, `file_path`, `size`, `ref`, `last_commit_id`, `content_sha256`, `is_binary`, `content`, `language`. Binary files return `is_binary: true` and a size summary instead of content.

---

## 5. get-readme

Get the README content for a project. Automatically finds README.md, .rst, .txt, etc.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--ref` | string | No | Branch/tag/commit |

**Output:** Object with `file_name`, `content`, `language`.

---

## 6. search-code

Search for code snippets across repositories. Returns matching files with line-level context. **Requires authentication** for global search.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--search-term` | string | Yes | - | Code/text to search for |
| `--project` | string | No | - | Limit to specific project |
| `--scope` | string | No | `blobs` | `blobs` (content) or `filenames` |
| `--ref` | string | No | - | Git branch/tag to search within |
| `--page` | integer | No | `1` | Page number |
| `--per-page` | integer | No | `20` | Results count (max 100) |

**Output:** Object with `search_term`, `scope`, `project`, `page`, `per_page`, `total_results`, and `results` array. Each result has `file_name`, `file_path`, `project_id`, `data` (matched content), `ref`, `startline`.

---

## 7. search-lhcb-stack

Search for code within a specific LHCb software stack (e.g., `sim11`). Automatically resolves correct Git references using the LHCb nightly build API.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--search-term` | string | Yes | Code/text to search for |
| `--stack` | string | Yes | Software stack name (e.g., `sim11`) |
| `--project` | string | No | Limit to specific project |
| `--scope` | string | No | `blobs` or `filenames` |
| `--ref` | string | No | Override automatic ref resolution |
| `--page` | integer | No | Page number |
| `--per-page` | integer | No | Results count |

**Output:** Same format as `search-code`, with automatically resolved branch references.

---

## 8. search-issues

Search for issues and discussions in a project.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--search-term` | string | Yes | - | Keywords to search for |
| `--project` | string | No | - | Limit to specific project |
| `--state` | string | No | `opened` | `opened`, `closed`, or `all` |
| `--per-page` | integer | No | `10` | Results count |

**Output:** Array of issue objects with `id`, `iid`, `project_id`, `title`, `description`, `state`, `created_at`, `updated_at`, `web_url`.

---

## 9. get-wiki

Access project wiki pages. **Requires authentication.**

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--page-slug` | string | No | Specific page slug (omit to list all pages) |

**Output (list mode):** Array of objects with `slug`, `title`, `url`.

**Output (specific page):** Object with `slug`, `title`, `content`.

---

## 10. inspect-project

Comprehensive analysis of a project's structure, build system, dependencies, and CI/CD configuration. This is the most informative single command for understanding a project.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--ref` | string | No | Branch/tag/commit |

**Output:** Object with:
- `project`, `ref` — identifiers
- `ecosystems` — detected language ecosystems (e.g., `["python", "cpp"]`)
- `build_systems` — detected build tools (e.g., `["cmake", "python-build"]`)
- `dependencies` — array of dependency groups, each with `source_file`, `ecosystem`, `count`, `items` (name + version_spec)
- `ci_config` — CI/CD analysis: `found`, `analysis` (stages, jobs, image), `raw_preview`
- `files_analyzed` — count of config files examined

---

## 11. list-releases

List releases for a project.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--project` | string | Yes | - | Project ID or path |
| `--per-page` | integer | No | `20` | Results count |

**Output:** Array of release objects with `tag_name`, `name`, `description`, `created_at`, `published_at`, `web_url`.

---

## 12. get-release

Get detailed information about a specific release.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project ID or path |
| `--tag-name` | string | Yes | Release tag (e.g., `v1.0.0`) |

**Output:** Release object with `tag_name`, `name`, `description`, `created_at`, `published_at`, `web_url`, `assets` (array of name + url).

---

## 13. list-tags

List project tags with optional filtering.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--project` | string | Yes | - | Project ID or path |
| `--search` | string | No | - | Filter by name prefix |
| `--sort` | string | No | `desc` | `asc` or `desc` |
| `--per-page` | integer | No | `20` | Results count |

**Output:** Array of tag objects with `name`, `message`, `target`, `commit` (object with `id`, `short_id`, `created_at`).

---

## 14. test-connection

Test connectivity to the CERN GitLab instance. Takes no parameters.

**Output:** Object with `status`, `gitlab_url`, `authenticated`, `version`, `revision`, `public_access`.
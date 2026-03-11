# Changelog

All notable changes to this project will be documented in this file.

## [0.1.6] - 2026-03-11

### Added
- **`cerngitlab-cli`** Command-Line Interface**: Added a CLI tool for users to use the same tools provided by `cerngitlab-mcp` directly from the terminal. It can be used + the `SKILLS.md` file for skill + cli workflow.


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

# Changelog

All notable changes to this project will be documented in this file.

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

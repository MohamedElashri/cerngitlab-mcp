"""Integration tests against the real CERN GitLab API.

These tests require network access to https://gitlab.cern.ch.
Run with: uv run python tests/test_integration.py

They are NOT run by pytest by default — they hit the live API and depend on
real project data being available.
"""

import asyncio
import sys

from cerngitlab_mcp.config import get_settings
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.tools import (
    get_file_content,
    get_release,
    get_project_info,
    get_project_readme,
    get_wiki_pages,
    inspect_project,
    list_releases,
    list_project_files,
    list_tags,
    search_code,
    search_issues,
    search_projects,
)
from cerngitlab_mcp.tools.utils import encode_project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _header(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def _sub(title: str) -> None:
    print(f"\n  --- {title} ---")


async def find_test_project(client: GitLabClient) -> dict:
    """Find a public project suitable for integration testing."""
    projects = await search_projects.handle(client, {"query": "root", "per_page": 5})
    if not projects:
        print("ERROR: No public projects found on CERN GitLab")
        sys.exit(1)
    return projects[0]


async def find_project_with_tags(client: GitLabClient) -> tuple[str, str | None]:
    """Find a public project that has tags/releases."""
    candidates = ["lhcb/DaVinci", "lhcb/Moore", "atlas-sit/lcgcmake"]
    for candidate in candidates:
        encoded = encode_project(candidate)
        try:
            tags = await client.get(
                f"/projects/{encoded}/repository/tags",
                params={"per_page": 1},
            )
            if isinstance(tags, list) and tags:
                return candidate, tags[0].get("name")
        except Exception:
            continue
    return "", None


# ---------------------------------------------------------------------------
# Connectivity
# ---------------------------------------------------------------------------

async def test_connectivity(client: GitLabClient) -> None:
    _header("Connectivity")
    result = await client.test_connection()
    for key, value in result.items():
        print(f"  {key}: {value}")
    if result["status"] != "connected":
        print("\nConnection failed — cannot run integration tests")
        sys.exit(0)


# ---------------------------------------------------------------------------
# Project discovery
# ---------------------------------------------------------------------------

async def test_search_projects(client: GitLabClient) -> None:
    _header("search_projects")

    _sub("keyword search: 'root'")
    result = await search_projects.handle(client, {"query": "root", "per_page": 5})
    print(f"  Found {len(result)} projects")
    for p in result[:3]:
        print(f"    {p['path_with_namespace']}: {(p.get('description') or '')[:60]}")

    _sub("language filter: python")
    result = await search_projects.handle(client, {
        "query": "analysis", "language": "python", "per_page": 5,
    })
    print(f"  Found {len(result)} Python projects")

    _sub("sort by stars")
    result = await search_projects.handle(client, {
        "query": "physics", "sort_by": "stars", "per_page": 5,
    })
    print(f"  Found {len(result)} projects")


async def test_get_project_info(client: GitLabClient, project: str, project_id: str) -> None:
    _header(f"get_project_info ({project})")
    result = await get_project_info.handle(client, {"project": project})
    print(f"  Name: {result['name']}")
    print(f"  Languages: {result['languages']}")
    print(f"  Stars: {result['star_count']}")

    _sub(f"by numeric ID ({project_id})")
    result2 = await get_project_info.handle(client, {"project": project_id})
    print(f"  Resolved: {result2['path_with_namespace']}")


async def test_list_project_files(client: GitLabClient, project: str) -> None:
    _header(f"list_project_files ({project})")

    result = await list_project_files.handle(client, {"project": project})
    print(f"  Directories: {len(result['directories'])}")
    print(f"  Files: {len(result['files'])}")
    for d in result["directories"][:5]:
        print(f"    dir/  {d['name']}")
    for f in result["files"][:5]:
        print(f"    file  {f['name']}")

    if result["directories"]:
        subdir = result["directories"][0]["path"]
        _sub(f"subdirectory: {subdir}")
        sub = await list_project_files.handle(client, {"project": project, "path": subdir})
        print(f"  Entries: {sub['total_entries']}")


# ---------------------------------------------------------------------------
# Code and documentation access
# ---------------------------------------------------------------------------

async def test_get_file_content(client: GitLabClient, project: str) -> None:
    _header(f"get_file_content ({project})")

    _sub("README.md")
    result = await get_file_content.handle(client, {"project": project, "file_path": "README.md"})
    print(f"  Size: {result['size']} bytes, binary: {result['is_binary']}, lang: {result['language']}")

    _sub(".gitlab-ci.yml")
    try:
        result = await get_file_content.handle(client, {"project": project, "file_path": ".gitlab-ci.yml"})
        print(f"  Size: {result['size']} bytes, lang: {result['language']}")
    except Exception as e:
        print(f"  Not found (expected for some repos): {e}")

    _sub("CMakeLists.txt")
    try:
        result = await get_file_content.handle(client, {"project": project, "file_path": "CMakeLists.txt"})
        print(f"  Size: {result['size']} bytes, lang: {result['language']}")
    except Exception as e:
        print(f"  Not found: {e}")


async def test_get_project_readme(client: GitLabClient, project: str) -> None:
    _header(f"get_project_readme ({project})")
    result = await get_project_readme.handle(client, {"project": project})
    if result.get("content"):
        print(f"  File: {result['file_name']}, format: {result['format']}, size: {result['size']} bytes")
    else:
        print(f"  No README found: {result.get('error')}")


async def test_search_code(client: GitLabClient, project: str) -> None:
    _header("search_code")

    _sub(f"project-scoped: 'include' in {project}")
    result = await search_code.handle(client, {"search_term": "include", "project": project, "per_page": 5})
    print(f"  Results: {result['total_results']}")
    if result.get("error"):
        print(f"  Note: {result['error']}")

    _sub("global: 'RooFit'")
    result = await search_code.handle(client, {"search_term": "RooFit", "per_page": 5})
    print(f"  Results: {result['total_results']}")
    if result.get("error"):
        print(f"  Note: {result['error']}")


async def test_get_wiki_pages(client: GitLabClient, project: str) -> None:
    _header(f"get_wiki_pages ({project})")
    result = await get_wiki_pages.handle(client, {"project": project})
    if result.get("error"):
        print(f"  {result['error']} (expected for many repos)")
    else:
        print(f"  Pages: {result['total_pages']}")


# ---------------------------------------------------------------------------
# Dependency and build analysis
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Interaction and context
# ---------------------------------------------------------------------------

async def test_search_issues(client: GitLabClient, project: str) -> None:
    _header(f"search_issues ({project})")
    # Search for something likely to exist
    result = await search_issues.handle(client, {"search_term": "fix", "project": project})
    print(f"  Found {result['count']} issues matching 'fix'")
    for issue in result['issues'][:3]:
        print(f"    #{issue['iid']}: {issue['title']}")


# ---------------------------------------------------------------------------
# Project analysis
# ---------------------------------------------------------------------------

async def test_inspect_project(client: GitLabClient, project: str) -> None:
    _header(f"inspect_project ({project})")
    result = await inspect_project.handle(client, {"project": project})
    
    print(f"  Ecosystems: {result['ecosystems']}")
    print(f"  Build systems: {result['build_systems']}")
    
    ci = result.get("ci_config", {})
    if ci.get("found"):
        print(f"  CI Config: Found ({ci.get('path', 'unknown')})")
        analysis = ci.get("analysis", {})
        if analysis.get("stages"):
            print(f"    Stages: {analysis['stages']}")
    else:
        print("  CI Config: Not found")
        
    print(f"  Dependencies found: {sum(len(f['items']) for f in result['dependencies'])}")
    for f in result['dependencies']:
        if f['items']:
            print(f"    {f['source_file']}: {len(f['items'])} items")


# ---------------------------------------------------------------------------
# Release and version tools
# ---------------------------------------------------------------------------

async def test_list_tags(client: GitLabClient, project: str) -> str | None:
    _header(f"list_tags ({project})")
    result = await list_tags.handle(client, {"project": project, "per_page": 10})
    print(f"  Total tags: {result['total_tags']}")
    first_tag = None
    for t in result["tags"][:5]:
        title = t["commit"]["title"][:60] if t["commit"].get("title") else "(no title)"
        print(f"    {t['name']} — {title}")
        if first_tag is None:
            first_tag = t["name"]

    if first_tag:
        prefix = first_tag[:2]
        _sub(f"filtered search: '{prefix}'")
        filtered = await list_tags.handle(client, {"project": project, "search": prefix, "per_page": 5})
        print(f"  Matching tags: {filtered['total_tags']}")

    return first_tag


async def test_list_releases(client: GitLabClient, project: str) -> str | None:
    _header(f"list_releases ({project})")
    result = await list_releases.handle(client, {"project": project, "per_page": 10})
    print(f"  Total releases: {result['total_releases']}")
    first_tag = None
    for r in result["releases"][:5]:
        print(f"    {r['tag_name']} — {r['name'] or '(unnamed)'} ({r['released_at']})")
        if first_tag is None:
            first_tag = r["tag_name"]
    if not result["releases"]:
        print("  (no releases — common for many CERN projects)")
    return first_tag


async def test_get_release(client: GitLabClient, project: str, tag_name: str) -> None:
    _header(f"get_release ({project}, tag={tag_name})")
    result = await get_release.handle(client, {"project": project, "tag_name": tag_name})
    if not result.get("found"):
        print(f"  {result.get('error', 'Not found')}")
        return
    print(f"  Tag: {result['tag_name']}, name: {result['name']}")
    print(f"  Released: {result['released_at']}, author: {result['author']}")
    commit = result.get("commit", {})
    print(f"  Commit: {commit.get('short_id')} — {commit.get('title', '')[:60]}")
    assets = result.get("assets", {})
    print(f"  Assets: {len(assets.get('links', []))} links, {len(assets.get('sources', []))} sources")

    _sub("non-existent release")
    bad = await get_release.handle(client, {"project": project, "tag_name": "v999.999.999-nonexistent"})
    print(f"  Found: {bad.get('found')} — {bad.get('error', '')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    settings = get_settings()
    client = GitLabClient(settings)

    try:
        await test_connectivity(client)

        # Find a general test project
        proj = await find_test_project(client)
        project = proj["path_with_namespace"]
        project_id = str(proj["id"])
        print(f"\nUsing general test project: {project} (id={project_id})")

        # Repository discovery
        await test_search_projects(client)
        await test_get_project_info(client, project, project_id)
        await test_list_project_files(client, project)

        # Code and documentation
        await test_get_file_content(client, project)
        await test_get_project_readme(client, project)
        await test_search_code(client, project)
        await test_get_wiki_pages(client, project)
        
        # Context
        await test_search_issues(client, project)

        # Analysis
        await test_inspect_project(client, project)

        # Release and version tools — need a project with tags
        tag_project, known_tag = await find_project_with_tags(client)
        if tag_project:
            print(f"\nUsing release test project: {tag_project}")
            tag_from_list = await test_list_tags(client, tag_project)
            release_tag = await test_list_releases(client, tag_project)
            test_tag = release_tag or tag_from_list or known_tag
            if test_tag:
                await test_get_release(client, tag_project, test_tag)
            else:
                print("\n  Skipping get_release — no tags found")
        else:
            print("\n  Skipping release tools — no project with tags found")

        _header("ALL INTEGRATION TESTS PASSED")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

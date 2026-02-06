"""Test Phase 3 tools against real CERN GitLab API."""

import asyncio
import json
import sys

from cerngitlab_mcp.config import get_settings
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.tools import search_repositories, get_repository_info, list_repository_files


async def test_search_repositories(client: GitLabClient) -> None:
    """Test search_repositories with various queries."""
    print("=" * 60)
    print("TEST: search_repositories")
    print("=" * 60)

    # Test 1: Basic keyword search
    print("\n--- Search: query='root', per_page=5 ---")
    result = await search_repositories.handle(client, {"query": "root", "per_page": 5})
    print(f"Found {len(result)} projects")
    for p in result[:3]:
        print(f"  {p['path_with_namespace']}: {p['description'][:60]}")

    # Test 2: Search with language filter
    print("\n--- Search: query='analysis', language='python', per_page=5 ---")
    result = await search_repositories.handle(client, {
        "query": "analysis",
        "language": "python",
        "per_page": 5,
    })
    print(f"Found {len(result)} Python projects")
    for p in result[:3]:
        print(f"  {p['path_with_namespace']}: stars={p['star_count']}")

    # Test 3: Search sorted by stars
    print("\n--- Search: query='physics', sort_by='stars', per_page=5 ---")
    result = await search_repositories.handle(client, {
        "query": "physics",
        "sort_by": "stars",
        "per_page": 5,
    })
    print(f"Found {len(result)} projects")
    for p in result[:3]:
        print(f"  {p['path_with_namespace']}: stars={p['star_count']}")

    # Test 4: Empty search (list recent public projects)
    print("\n--- Search: no query (recent public projects) ---")
    result = await search_repositories.handle(client, {"per_page": 3})
    print(f"Found {len(result)} projects")
    for p in result:
        print(f"  {p['path_with_namespace']}: last_activity={p['last_activity_at']}")


async def test_get_repository_info(client: GitLabClient, project_path: str) -> None:
    """Test get_repository_info with a known project."""
    print("\n" + "=" * 60)
    print(f"TEST: get_repository_info (project={project_path})")
    print("=" * 60)

    result = await get_repository_info.handle(client, {"project": project_path})
    print(f"  Name: {result['name']}")
    print(f"  Path: {result['path_with_namespace']}")
    print(f"  Description: {result['description'][:80]}")
    print(f"  Default branch: {result['default_branch']}")
    print(f"  Topics: {result['topics']}")
    print(f"  Languages: {result['languages']}")
    print(f"  Stars: {result['star_count']}")
    print(f"  License: {result['license']}")
    if result.get("statistics"):
        print(f"  Commits: {result['statistics']['commit_count']}")


async def test_list_repository_files(client: GitLabClient, project_path: str) -> None:
    """Test list_repository_files with a known project."""
    print("\n" + "=" * 60)
    print(f"TEST: list_repository_files (project={project_path})")
    print("=" * 60)

    # Test 1: Root directory
    print("\n--- Root directory ---")
    result = await list_repository_files.handle(client, {"project": project_path})
    print(f"  Path: {result['path']}")
    print(f"  Total entries: {result['total_entries']}")
    print(f"  Directories ({len(result['directories'])}):")
    for d in result["directories"][:5]:
        print(f"    📁 {d['name']}")
    print(f"  Files ({len(result['files'])}):")
    for f in result["files"][:5]:
        print(f"    📄 {f['name']}")

    # Test 2: Subdirectory (if directories exist)
    if result["directories"]:
        subdir = result["directories"][0]["path"]
        print(f"\n--- Subdirectory: {subdir} ---")
        sub_result = await list_repository_files.handle(client, {
            "project": project_path,
            "path": subdir,
        })
        print(f"  Total entries: {sub_result['total_entries']}")
        for e in (sub_result["directories"] + sub_result["files"])[:5]:
            icon = "📁" if e["type"] == "tree" else "📄"
            print(f"    {icon} {e['name']}")


async def main() -> None:
    settings = get_settings()
    client = GitLabClient(settings)

    try:
        # First find a project to use for detailed tests
        print("Finding a test project...")
        projects = await search_repositories.handle(client, {"query": "root", "per_page": 5})
        if not projects:
            print("ERROR: No public projects found. Cannot proceed.")
            sys.exit(1)

        test_project = projects[0]["path_with_namespace"]
        test_project_id = str(projects[0]["id"])
        print(f"Using test project: {test_project} (id={test_project_id})\n")

        await test_search_repositories(client)
        await test_get_repository_info(client, test_project)
        await test_list_repository_files(client, test_project)

        # Also test with numeric ID
        print("\n--- get_repository_info with numeric ID ---")
        result = await get_repository_info.handle(client, {"project": test_project_id})
        print(f"  Resolved: {result['path_with_namespace']}")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

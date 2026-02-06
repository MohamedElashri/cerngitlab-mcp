"""Test Phase 4 tools against real CERN GitLab API."""

import asyncio
import sys

from cerngitlab_mcp.config import get_settings
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.tools import get_file_content, get_repository_readme, search_code, get_wiki_pages


async def test_get_file_content(client: GitLabClient, project: str) -> None:
    """Test get_file_content with various file types."""
    print("=" * 60)
    print("TEST: get_file_content")
    print("=" * 60)

    # Test 1: Get a known text file (README.md)
    print("\n--- Get README.md ---")
    result = await get_file_content.handle(client, {
        "project": project,
        "file_path": "README.md",
    })
    print(f"  File: {result['file_name']}")
    print(f"  Size: {result['size']} bytes")
    print(f"  Binary: {result['is_binary']}")
    print(f"  Language: {result['language']}")
    print(f"  Content preview: {result['content'][:100]}...")

    # Test 2: Get .gitlab-ci.yml (YAML)
    print("\n--- Get .gitlab-ci.yml ---")
    try:
        result = await get_file_content.handle(client, {
            "project": project,
            "file_path": ".gitlab-ci.yml",
        })
        print(f"  File: {result['file_name']}")
        print(f"  Language: {result['language']}")
        print(f"  Content preview: {result['content'][:100]}...")
    except Exception as e:
        print(f"  Not found (expected for some repos): {e}")

    # Test 3: Get CMakeLists.txt
    print("\n--- Get CMakeLists.txt ---")
    try:
        result = await get_file_content.handle(client, {
            "project": project,
            "file_path": "CMakeLists.txt",
        })
        print(f"  File: {result['file_name']}")
        print(f"  Language: {result['language']}")
        print(f"  Content preview: {result['content'][:100]}...")
    except Exception as e:
        print(f"  Not found: {e}")


async def test_get_repository_readme(client: GitLabClient, project: str) -> None:
    """Test get_repository_readme."""
    print("\n" + "=" * 60)
    print("TEST: get_repository_readme")
    print("=" * 60)

    result = await get_repository_readme.handle(client, {"project": project})
    if result.get("content"):
        print(f"  File: {result['file_name']}")
        print(f"  Format: {result['format']}")
        print(f"  Size: {result['size']} bytes")
        print(f"  Content preview:\n{result['content'][:200]}...")
    else:
        print(f"  No README found: {result.get('error')}")


async def test_search_code(client: GitLabClient, project: str) -> None:
    """Test search_code with project-scoped and global searches."""
    print("\n" + "=" * 60)
    print("TEST: search_code")
    print("=" * 60)

    # Test 1: Project-scoped search
    print("\n--- Project-scoped search: 'include' ---")
    result = await search_code.handle(client, {
        "search_term": "include",
        "project": project,
        "per_page": 5,
    })
    print(f"  Scope: {result['scope']}")
    print(f"  Results: {result['total_results']}")
    for r in result["results"][:3]:
        print(f"    {r['file_path']}: {r.get('data', '')[:60]}...")

    # Test 2: Global search
    print("\n--- Global search: 'RooFit' (per_page=5) ---")
    result = await search_code.handle(client, {
        "search_term": "RooFit",
        "per_page": 5,
    })
    print(f"  Scope: {result['scope']}")
    print(f"  Project: {result['project']}")
    print(f"  Results: {result['total_results']}")
    for r in result["results"][:3]:
        print(f"    [project {r['project_id']}] {r['file_path']}")

    # Test 3: Filename search
    print("\n--- Filename search: 'CMakeLists' ---")
    result = await search_code.handle(client, {
        "search_term": "CMakeLists",
        "project": project,
        "scope": "filenames",
        "per_page": 5,
    })
    print(f"  Results: {result['total_results']}")
    for r in result["results"][:3]:
        print(f"    {r['file_path']}")


async def test_get_wiki_pages(client: GitLabClient, project: str) -> None:
    """Test get_wiki_pages."""
    print("\n" + "=" * 60)
    print("TEST: get_wiki_pages")
    print("=" * 60)

    result = await get_wiki_pages.handle(client, {"project": project})
    if result.get("error"):
        print(f"  {result['error']} (expected for many repos)")
    else:
        print(f"  Mode: {result['mode']}")
        print(f"  Total pages: {result['total_pages']}")
        for p in result.get("pages", [])[:5]:
            print(f"    {p['title']} ({p['format']})")


async def main() -> None:
    settings = get_settings()
    client = GitLabClient(settings)

    try:
        # Use a known project with good content
        # First search for a project with C++ and Python
        from cerngitlab_mcp.tools import search_repositories
        projects = await search_repositories.handle(client, {
            "query": "root",
            "per_page": 5,
        })
        if not projects:
            print("ERROR: No public projects found")
            sys.exit(1)

        test_project = projects[0]["path_with_namespace"]
        print(f"Using test project: {test_project}\n")

        await test_get_file_content(client, test_project)
        await test_get_repository_readme(client, test_project)
        await test_search_code(client, test_project)
        await test_get_wiki_pages(client, test_project)

        print("\n" + "=" * 60)
        print("ALL PHASE 4 TESTS PASSED")
        print("=" * 60)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

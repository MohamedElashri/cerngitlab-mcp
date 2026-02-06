"""Test basic connectivity and client functionality."""

import asyncio
import sys

from cerngitlab_mcp.config import get_settings
from cerngitlab_mcp.gitlab_client import GitLabClient


async def test_connection() -> None:
    """Test connectivity to CERN GitLab and print results."""
    settings = get_settings()
    client = GitLabClient(settings)

    print(f"Target: {settings.gitlab_url}")
    print(f"Authenticated: {bool(settings.token)}")
    print()

    result = await client.test_connection()
    for key, value in result.items():
        print(f"  {key}: {value}")

    await client.close()

    if result["status"] != "connected":
        print("\n⚠ Connection failed — this is expected if you're not on the CERN network")
        print("  The server will still start and work when connectivity is available.")
        sys.exit(0)

    # If connected, try a simple public project search to verify API works
    print("\nTesting public project search...")
    try:
        projects = await _test_public_search(client)
        print(f"  Found {len(projects)} public projects matching 'root'")
        if projects:
            p = projects[0]
            print(f"  First result: {p.get('path_with_namespace', '?')} — {p.get('description', 'no description')[:80]}")
    except Exception as exc:
        print(f"  Search test failed: {exc}")
    finally:
        await client.close()


async def _test_public_search(client: GitLabClient) -> list:
    """Search for public projects to verify API access."""
    # Re-create client since we closed it
    settings = get_settings()
    client = GitLabClient(settings)
    try:
        return await client.get(
            "/projects",
            params={"search": "root", "per_page": 5, "visibility": "public"},
        )
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_connection())

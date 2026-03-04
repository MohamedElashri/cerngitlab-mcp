import httpx
import logging

logger = logging.getLogger("cerngitlab_mcp")

STACK_API_BASE = "https://lhcb-nightlies.web.cern.ch/api/v1/nightly"

async def resolve_stack(stack_name: str) -> dict[str, str]:
    """
    Queries the LHCb nightly build API to return mapping of projects to their branch refs.
    {
        "Boole": "sim11",
        "DD4hepDDG4": "sim11",
        ...
    }
    """
    if not stack_name:
        return {}

    stack_name = stack_name.lower()
    url = f"{STACK_API_BASE}/lhcb-{stack_name}/latest/"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning(f"Failed to resolve stack '{stack_name}': {e}")
        return {}

    builds = data.get("builds", {})

    if not builds:
        return {}

    # Take first platform (e.g. armv8.1_a-el9-gcc13-opt)
    platform = next(iter(builds))
    projects = builds.get(platform, {})

    repo_map = {}

    # Branch naming convention
    branch_name = stack_name  # e.g. "sim11"

    for project_name in projects.keys():
        repo_map[project_name] = branch_name

    return repo_map

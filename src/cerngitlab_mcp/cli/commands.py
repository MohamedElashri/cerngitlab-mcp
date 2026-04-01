"""CLI command implementations for all CERN GitLab tools."""

import asyncio
import json
import sys
from typing import Any

import click

from cerngitlab_mcp.config import get_settings
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.exceptions import CERNGitLabError
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
    search_lhcb_stack,
    search_issues,
    search_projects,
)


def _output_json(data: Any) -> None:
    """Output data as formatted JSON to stdout."""
    click.echo(json.dumps(data, indent=2))


def _output_error(message: str) -> None:
    """Output an error message as JSON to stderr."""
    click.echo(json.dumps({"error": message}, indent=2), err=True)
    sys.exit(1)


def _create_client() -> GitLabClient:
    """Create a GitLab client from settings."""
    settings = get_settings()
    return GitLabClient(settings)


def _run_async(coro):
    """Run an async coroutine."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# search-projects
# ---------------------------------------------------------------------------


@click.command("search-projects")
@click.option(
    "--query", "-q", default="", help="Search query (matches project name, description)"
)
@click.option(
    "--language", "-l", default="", help="Filter by language (e.g., python, c++)"
)
@click.option(
    "--topic", "-t", default="", help="Filter by topic tag (e.g., physics, root)"
)
@click.option(
    "--sort-by",
    default="last_activity_at",
    type=click.Choice(["last_activity_at", "name", "created_at", "stars"]),
    help="Sort field",
)
@click.option(
    "--order", default="desc", type=click.Choice(["desc", "asc"]), help="Sort order"
)
@click.option(
    "--per-page", default=20, type=click.IntRange(1, 100), help="Results count (1-100)"
)
def search_projects_cmd(
    query: str,
    language: str,
    topic: str,
    sort_by: str,
    order: str,
    per_page: int,
) -> None:
    """Search for public CERN GitLab projects by keywords, topics, or language."""

    async def _run():
        client = _create_client()
        try:
            arguments = {
                "query": query,
                "language": language,
                "topic": topic,
                "sort_by": sort_by,
                "order": order,
                "per_page": per_page,
            }
            result = await search_projects.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# get-project-info
# ---------------------------------------------------------------------------


@click.command("get-project-info")
@click.option(
    "--project",
    "-p",
    required=True,
    help="Project ID or path (e.g., 12345 or lhcb/allen)",
)
def get_project_info_cmd(project: str) -> None:
    """Get detailed information about a specific project."""

    async def _run():
        client = _create_client()
        try:
            arguments = {"project": project}
            result = await get_project_info.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# list-files
# ---------------------------------------------------------------------------


@click.command("list-files")
@click.option("--project", "-p", required=True, help="Project ID or path")
@click.option("--path", default="", help="Subdirectory path to list")
@click.option("--ref", default="", help="Branch/tag/commit")
@click.option("--recursive", is_flag=True, help="List recursively")
@click.option(
    "--per-page", default=100, type=click.IntRange(1, 100), help="Results count"
)
def list_files_cmd(
    project: str,
    path: str,
    ref: str,
    recursive: bool,
    per_page: int,
) -> None:
    """List files and directories in a project's repository."""

    async def _run():
        client = _create_client()
        try:
            arguments = {
                "project": project,
                "path": path,
                "ref": ref,
                "recursive": recursive,
                "per_page": per_page,
            }
            result = await list_project_files.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# get-file
# ---------------------------------------------------------------------------


@click.command("get-file")
@click.option("--project", "-p", required=True, help="Project ID or path")
@click.option("--file-path", "-f", required=True, help="Path to file within repository")
@click.option("--ref", default="", help="Branch/tag/commit")
def get_file_cmd(project: str, file_path: str, ref: str) -> None:
    """Retrieve the content of a specific file from a repository."""

    async def _run():
        client = _create_client()
        try:
            arguments = {
                "project": project,
                "file_path": file_path,
                "ref": ref,
            }
            result = await get_file_content.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# get-readme
# ---------------------------------------------------------------------------


@click.command("get-readme")
@click.option("--project", "-p", required=True, help="Project ID or path")
@click.option("--ref", default="", help="Branch/tag/commit")
def get_readme_cmd(project: str, ref: str) -> None:
    """Get the README content for a project."""

    async def _run():
        client = _create_client()
        try:
            arguments = {"project": project, "ref": ref}
            result = await get_project_readme.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# search-code
# ---------------------------------------------------------------------------


@click.command("search-code")
@click.option("--search-term", "-s", required=True, help="Code/text to search for")
@click.option("--project", "-p", default="", help="Limit to specific project")
@click.option(
    "--scope",
    default="blobs",
    type=click.Choice(["blobs", "filenames"]),
    help="Search scope: blobs (content) or filenames",
)
@click.option("--ref", default="", help="Git branch/tag to search within")
@click.option("--page", default=1, type=click.IntRange(1), help="Page number")
@click.option(
    "--per-page", default=20, type=click.IntRange(1, 100), help="Results count"
)
def search_code_cmd(
    search_term: str,
    project: str,
    scope: str,
    ref: str,
    page: int,
    per_page: int,
) -> None:
    """Search for code snippets across CERN GitLab repositories."""

    async def _run():
        client = _create_client()
        try:
            arguments = {
                "search_term": search_term,
                "project": project,
                "scope": scope,
                "ref": ref,
                "page": page,
                "per_page": per_page,
            }
            result = await search_code.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# search-lhcb-stack
# ---------------------------------------------------------------------------


@click.command("search-lhcb-stack")
@click.option("--search-term", "-s", required=True, help="Code/text to search for")
@click.option("--stack", required=True, help="Software stack name (e.g., sim11)")
@click.option("--project", "-p", default="", help="Limit to specific project")
@click.option(
    "--scope",
    default="blobs",
    type=click.Choice(["blobs", "filenames"]),
    help="Search scope",
)
@click.option("--ref", default="", help="Override automatic ref resolution")
@click.option("--page", default=1, type=click.IntRange(1), help="Page number")
@click.option(
    "--per-page", default=20, type=click.IntRange(1, 100), help="Results count"
)
def search_lhcb_stack_cmd(
    search_term: str,
    stack: str,
    project: str,
    scope: str,
    ref: str,
    page: int,
    per_page: int,
) -> None:
    """Search for code within a specific LHCb software stack."""

    async def _run():
        client = _create_client()
        try:
            arguments = {
                "search_term": search_term,
                "stack": stack,
                "project": project,
                "scope": scope,
                "ref": ref,
                "page": page,
                "per_page": per_page,
            }
            result = await search_lhcb_stack.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# search-issues
# ---------------------------------------------------------------------------


@click.command("search-issues")
@click.option("--search-term", "-s", required=True, help="Keywords to search for")
@click.option("--project", "-p", default="", help="Limit to specific project")
@click.option(
    "--state",
    default="opened",
    type=click.Choice(["opened", "closed", "all"]),
    help="Issue state",
)
@click.option(
    "--per-page", default=10, type=click.IntRange(1, 100), help="Results count"
)
def search_issues_cmd(
    search_term: str,
    project: str,
    state: str,
    per_page: int,
) -> None:
    """Search for issues and discussions in a project."""

    async def _run():
        client = _create_client()
        try:
            arguments = {
                "search_term": search_term,
                "project": project,
                "state": state,
                "per_page": per_page,
            }
            result = await search_issues.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# get-wiki
# ---------------------------------------------------------------------------


@click.command("get-wiki")
@click.option("--project", "-p", required=True, help="Project ID or path")
@click.option("--page-slug", default="", help="Specific page slug (omit to list all)")
def get_wiki_cmd(project: str, page_slug: str) -> None:
    """Access project wiki pages."""

    async def _run():
        client = _create_client()
        try:
            arguments = {"project": project, "page_slug": page_slug}
            result = await get_wiki_pages.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# inspect-project
# ---------------------------------------------------------------------------


@click.command("inspect-project")
@click.option("--project", "-p", required=True, help="Project ID or path")
@click.option("--ref", default="", help="Branch/tag/commit")
def inspect_project_cmd(project: str, ref: str) -> None:
    """Analyze a project's structure, build system, and dependencies."""

    async def _run():
        client = _create_client()
        try:
            arguments = {"project": project, "ref": ref}
            result = await inspect_project.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# list-releases
# ---------------------------------------------------------------------------


@click.command("list-releases")
@click.option("--project", "-p", required=True, help="Project ID or path")
@click.option(
    "--per-page", default=20, type=click.IntRange(1, 100), help="Results count"
)
def list_releases_cmd(project: str, per_page: int) -> None:
    """List releases for a project."""

    async def _run():
        client = _create_client()
        try:
            arguments = {"project": project, "per_page": per_page}
            result = await list_releases.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# get-release
# ---------------------------------------------------------------------------


@click.command("get-release")
@click.option("--project", "-p", required=True, help="Project ID or path")
@click.option("--tag-name", required=True, help="Release tag (e.g., v1.0.0)")
def get_release_cmd(project: str, tag_name: str) -> None:
    """Get detailed information about a specific release."""

    async def _run():
        client = _create_client()
        try:
            arguments = {"project": project, "tag_name": tag_name}
            result = await get_release.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# list-tags
# ---------------------------------------------------------------------------


@click.command("list-tags")
@click.option("--project", "-p", required=True, help="Project ID or path")
@click.option("--search", default="", help="Filter by name prefix")
@click.option(
    "--sort", default="desc", type=click.Choice(["asc", "desc"]), help="Sort order"
)
@click.option(
    "--per-page", default=20, type=click.IntRange(1, 100), help="Results count"
)
def list_tags_cmd(project: str, search: str, sort: str, per_page: int) -> None:
    """List project tags with optional filtering."""

    async def _run():
        client = _create_client()
        try:
            arguments = {
                "project": project,
                "search": search,
                "sort": sort,
                "per_page": per_page,
            }
            result = await list_tags.handle(client, arguments)
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())


# ---------------------------------------------------------------------------
# test-connection
# ---------------------------------------------------------------------------


@click.command("test-connection")
def test_connection_cmd() -> None:
    """Test connectivity to the CERN GitLab instance."""

    async def _run():
        client = _create_client()
        try:
            result = await client.test_connection()
            _output_json(result)
        except CERNGitLabError as exc:
            _output_error(exc.message)
        finally:
            await client.close()

    _run_async(_run())

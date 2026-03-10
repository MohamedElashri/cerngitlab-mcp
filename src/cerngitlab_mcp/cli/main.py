"""Main CLI entry point for CERN GitLab tools."""

import asyncio
import json
import sys

import click

from cerngitlab_mcp.config import get_settings
from cerngitlab_mcp.gitlab_client import GitLabClient
from cerngitlab_mcp.cli.commands import (
    search_projects_cmd,
    get_project_info_cmd,
    list_files_cmd,
    get_file_cmd,
    get_readme_cmd,
    search_code_cmd,
    search_lhcb_stack_cmd,
    search_issues_cmd,
    get_wiki_cmd,
    inspect_project_cmd,
    list_releases_cmd,
    get_release_cmd,
    list_tags_cmd,
    test_connection_cmd,
)


@click.group()
@click.version_option(version="0.1.5", prog_name="cerngitlab-cli")
def cli() -> None:
    """CERN GitLab CLI - Tools for discovering and analyzing HEP code repositories.
    
    All commands output JSON to stdout for easy piping and composition.
    
    Configuration via environment variables (prefix CERNGITLAB_):
      - CERNGITLAB_GITLAB_URL: GitLab instance URL (default: https://gitlab.cern.ch)
      - CERNGITLAB_TOKEN: Personal access token (optional)
      - CERNGITLAB_TIMEOUT: HTTP timeout in seconds (default: 30)
      - CERNGITLAB_MAX_RETRIES: Max retries (default: 3)
      - CERNGITLAB_RATE_LIMIT_PER_MINUTE: Rate limit (default: 300)
      - CERNGITLAB_DEFAULT_REF: Default Git branch/tag
    """
    pass


def _run_async(coro):
    """Run an async coroutine."""
    return asyncio.run(coro)


# Register commands
cli.add_command(search_projects_cmd)
cli.add_command(get_project_info_cmd)
cli.add_command(list_files_cmd)
cli.add_command(get_file_cmd)
cli.add_command(get_readme_cmd)
cli.add_command(search_code_cmd)
cli.add_command(search_lhcb_stack_cmd)
cli.add_command(search_issues_cmd)
cli.add_command(get_wiki_cmd)
cli.add_command(inspect_project_cmd)
cli.add_command(list_releases_cmd)
cli.add_command(get_release_cmd)
cli.add_command(list_tags_cmd)
cli.add_command(test_connection_cmd)


def main() -> None:
    """Main entry point for the cerngitlab-cli command."""
    cli()


if __name__ == "__main__":
    main()

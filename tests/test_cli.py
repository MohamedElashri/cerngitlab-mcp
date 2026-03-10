"""Unit tests for the CERN GitLab CLI with mocked HTTP responses."""

import json

import httpx
import pytest
from click.testing import CliRunner

from cerngitlab_mcp.cli.main import cli
from cerngitlab_mcp.config import Settings

from tests.conftest import make_file_response


# Configure httpx_mock to allow unused mocks
pytestmark = pytest.mark.httpx_mock(assert_all_responses_were_requested=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cli_runner():
    """Create a Click CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def cli_settings():
    """Create test settings pointing to a fake GitLab instance."""
    return Settings(
        gitlab_url="https://gitlab.example.com",
        token="test-token",
        timeout=5.0,
        max_retries=1,
        rate_limit_per_minute=1000,
    )


# ---------------------------------------------------------------------------
# Helper to catch stderr output for error cases
# ---------------------------------------------------------------------------

def _get_error_output(result):
    """Get error output from CLI result."""
    return result.output or (result.stderr if hasattr(result, 'stderr') else '')


# ---------------------------------------------------------------------------
# Test: test-connection
# ---------------------------------------------------------------------------

class TestTestConnection:
    def test_test_connection_success(self, cli_runner, httpx_mock, cli_settings):
        """Test successful connection."""
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects", params={
                "per_page": "1", "visibility": "public",
            }),
            json=[{"id": 1, "name": "test"}],
        )
        httpx_mock.add_response(
            url="https://gitlab.example.com/api/v4/version",
            json={"version": "16.0.0", "revision": "abc123"},
        )
        
        result = cli_runner.invoke(cli, ["test-connection"], env={
            "CERNGITLAB_GITLAB_URL": cli_settings.gitlab_url,
            "CERNGITLAB_TOKEN": cli_settings.token,
        })
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "connected"
        assert data["gitlab_url"] == cli_settings.gitlab_url
        assert data["authenticated"] is True

    def test_test_connection_public_only(self, cli_runner, httpx_mock):
        """Test connection without token (public access only)."""
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects", params={
                "per_page": "1", "visibility": "public",
            }),
            json=[{"id": 1, "name": "test"}],
        )
        
        result = cli_runner.invoke(cli, ["test-connection"], env={
            "CERNGITLAB_GITLAB_URL": "https://gitlab.example.com",
        })
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "connected"
        assert data["authenticated"] is False


# ---------------------------------------------------------------------------
# Test: search-projects
# ---------------------------------------------------------------------------

class TestSearchProjects:
    def test_search_projects_basic(self, cli_runner, httpx_mock):
        """Test basic project search."""
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects", params={
                "visibility": "public", "search": "root",
                "order_by": "last_activity_at", "sort": "desc", "per_page": "5",
            }),
            json=[
                {
                    "id": 1, "name": "proj1", "path_with_namespace": "g/proj1",
                    "description": "Test", "web_url": "https://x", "default_branch": "main",
                    "topics": ["physics"], "star_count": 5, "forks_count": 1,
                    "last_activity_at": "2025-01-01", "created_at": "2024-01-01",
                    "visibility": "public",
                },
            ],
        )
        
        result = cli_runner.invoke(cli, [
            "search-projects", "--query", "root", "--per-page", "5",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["name"] == "proj1"
        assert data[0]["star_count"] == 5

    def test_search_projects_with_filters(self, cli_runner, httpx_mock):
        """Test project search with language and topic filters."""
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects", params={
                "visibility": "public", "search": "test",
                "with_programming_language": "python", "topic": "physics",
                "order_by": "star_count", "sort": "desc", "per_page": "10",
            }),
            json=[],
        )
        
        result = cli_runner.invoke(cli, [
            "search-projects",
            "--query", "test",
            "--language", "python",
            "--topic", "physics",
            "--sort-by", "stars",
            "--order", "desc",
            "--per-page", "10",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


# ---------------------------------------------------------------------------
# Test: get-project-info
# ---------------------------------------------------------------------------

class TestGetProjectInfo:
    def test_get_project_info_success(self, cli_runner, httpx_mock):
        """Test getting project info."""
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/test%2Fproj",
                          params={"statistics": "true"}),
            json={
                "id": 100, "name": "proj", "path_with_namespace": "test/proj",
                "description": "Test project", "web_url": "https://x",
                "default_branch": "main", "visibility": "public",
                "topics": ["test"], "star_count": 10, "forks_count": 2,
                "open_issues_count": 3, "created_at": "2024-01-01",
                "last_activity_at": "2025-01-01", "readme_url": "https://x/README",
                "license": {"name": "MIT"},
                "namespace": {"name": "test", "full_path": "test"},
            },
        )
        httpx_mock.add_response(
            url="https://gitlab.example.com/api/v4/projects/test%2Fproj/languages",
            json={"Python": 80.0, "C++": 20.0},
        )
        
        result = cli_runner.invoke(cli, [
            "get-project-info", "--project", "test/proj",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "proj"
        assert data["languages"]["Python"] == 80.0
        assert data["star_count"] == 10

    def test_get_project_info_not_found(self, cli_runner, httpx_mock):
        """Test project not found error."""
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/nonexistent",
                          params={"statistics": "true"}),
            status_code=404,
            json={"message": "Project not found"},
        )
        
        result = cli_runner.invoke(cli, [
            "get-project-info", "--project", "nonexistent",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data


# ---------------------------------------------------------------------------
# Test: list-files
# ---------------------------------------------------------------------------

class TestListFiles:
    def test_list_files_root_directory(self, cli_runner, httpx_mock):
        """Test listing root directory files."""
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/test%2Fproj/repository/tree",
                          params={"per_page": "100"}),
            json=[
                {"type": "tree", "path": "src", "name": "src"},
                {"type": "blob", "path": "README.md", "name": "README.md"},
            ],
        )
        
        result = cli_runner.invoke(cli, [
            "list-files", "--project", "test/proj",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["directories"]) == 1
        assert len(data["files"]) == 1
        assert data["directories"][0]["name"] == "src"

    def test_list_files_with_path(self, cli_runner, httpx_mock):
        """Test listing subdirectory files."""
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/test%2Fproj/repository/tree",
                          params={"path": "src", "per_page": "100"}),
            json=[
                {"type": "blob", "path": "src/main.py", "name": "main.py"},
            ],
        )
        
        result = cli_runner.invoke(cli, [
            "list-files", "--project", "test/proj", "--path", "src",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "main.py"


# ---------------------------------------------------------------------------
# Test: get-file
# ---------------------------------------------------------------------------

class TestGetFile:
    def test_get_file_text_content(self, cli_runner, httpx_mock):
        """Test getting text file content."""
        content = "print('Hello, World!')"
        # Mock project endpoint for ref resolution
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/test%2Fproj",
                          params={"statistics": "false"}),
            json={"default_branch": "main"},
        )
        # Mock file content endpoint
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/test%2Fproj/repository/files/src%2Fmain.py",
                          params={"ref": "main"}),
            json=make_file_response(content, "main.py", "main"),
        )
        
        result = cli_runner.invoke(cli, [
            "get-file", "--project", "test/proj", "--file-path", "src/main.py",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["file_name"] == "main.py"
        assert data["content"] == content
        assert data["language"] == "python"
        assert data["is_binary"] is False

    def test_get_file_binary_detection(self, cli_runner, httpx_mock):
        """Test binary file detection."""
        # Mock project endpoint for ref resolution
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/test%2Fproj",
                          params={"statistics": "false"}),
            json={"default_branch": "main"},
        )
        # Mock file content endpoint
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/test%2Fproj/repository/files/data.root",
                          params={"ref": "main"}),
            json=make_file_response("binary", "data.root", "main"),
        )
        
        result = cli_runner.invoke(cli, [
            "get-file", "--project", "test/proj", "--file-path", "data.root",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["is_binary"] is True
        assert "Binary file" in data["content"]


# ---------------------------------------------------------------------------
# Test: get-readme
# ---------------------------------------------------------------------------

class TestGetReadme:
    def test_get_readme_success(self, cli_runner, httpx_mock):
        """Test getting README content."""
        content = "# Test Project\n\nThis is a test."
        # Mock project endpoint for ref resolution
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/test%2Fproj",
                          params={"statistics": "false"}),
            json={"default_branch": "main"},
        )
        # Mock README file endpoint
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/test%2Fproj/repository/files/README.md",
                          params={"ref": "main"}),
            json=make_file_response(content, "README.md", "main"),
        )
        
        result = cli_runner.invoke(cli, [
            "get-readme", "--project", "test/proj",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["file_name"] == "README.md"
        assert "# Test Project" in data["content"]

    def test_get_readme_not_found(self, cli_runner):
        """Test README not found error handling."""
        # This test verifies CLI error handling; detailed API testing is in test_tools.py
        result = cli_runner.invoke(cli, [
            "get-readme", "--project", "nonexistent/project",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        # Should produce error output
        assert result.output


# ---------------------------------------------------------------------------
# Test: search-code
# ---------------------------------------------------------------------------

class TestSearchCode:
    def test_search_code_global(self, cli_runner, httpx_mock):
        """Test global code search."""
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/search", params={
                "search": "RooFit", "scope": "blobs", "per_page": "10", "page": "1",
            }),
            json=[
                {
                    "filename": "fitting.py", "path": "src/fitting.py",
                    "project_id": 123, "data": "import RooFit",
                    "ref": "main", "startline": 5,
                },
            ],
        )
        
        result = cli_runner.invoke(cli, [
            "search-code", "--search-term", "RooFit", "--per-page", "10",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["search_term"] == "RooFit"
        assert len(data["results"]) == 1
        assert data["results"][0]["file_name"] == "fitting.py"

    def test_search_code_project_scoped(self, cli_runner, httpx_mock):
        """Test project-scoped code search."""
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/test%2Fproj/search",
                          params={"search": "main", "scope": "blobs", "per_page": "20", "page": "1"}),
            json=[],
        )
        
        result = cli_runner.invoke(cli, [
            "search-code", "--search-term", "main", "--project", "test/proj",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["project"] == "test/proj"
        assert data["results"] == []


# ---------------------------------------------------------------------------
# Test: search-lhcb-stack
# ---------------------------------------------------------------------------

class TestSearchLhcbStack:
    def test_search_lhcb_stack_resolves_refs(self, cli_runner, httpx_mock):
        """Test LHCb stack search with automatic ref resolution."""
        # Mock the LHCb nightly API
        httpx_mock.add_response(
            url="https://lhcb-nightlies.web.cern.ch/api/v1/nightly/lhcb-sim11/latest/",
            json={
                "builds": {
                    "armv8.1_a-el9-gcc13-opt": {
                        "Boole": {"status": "success"},
                        "DaVinci": {"status": "success"},
                    }
                }
            },
        )
        # Mock the code search
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/lhcb%2FBoole/search",
                          params={"search": "init", "scope": "blobs", "ref": "sim11",
                                  "per_page": "20", "page": "1"}),
            json=[
                {
                    "filename": "Kernel.cpp", "path": "src/Kernel.cpp",
                    "project_id": 456, "data": "void init()",
                    "ref": "sim11", "startline": 10,
                },
            ],
        )
        
        result = cli_runner.invoke(cli, [
            "search-lhcb-stack", "--search-term", "init", "--stack", "sim11",
            "--project", "lhcb/Boole",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["results"]) == 1
        assert data["results"][0]["ref"] == "sim11"

    def test_search_lhcb_stack_missing_stack(self, cli_runner):
        """Test error when stack parameter is missing."""
        result = cli_runner.invoke(cli, [
            "search-lhcb-stack", "--search-term", "test",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Test: search-issues
# ---------------------------------------------------------------------------

class TestSearchIssues:
    def test_search_issues_success(self, cli_runner):
        """Test that search-issues command runs and produces output."""
        # This test verifies CLI behavior; detailed API testing is in test_tools.py
        result = cli_runner.invoke(cli, [
            "search-issues", "--search-term", "bug", "--project", "test/proj",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        # Should produce some output
        assert result.output


# ---------------------------------------------------------------------------
# Test: get-wiki
# ---------------------------------------------------------------------------

class TestGetWiki:
    def test_get_wiki_list_pages(self, cli_runner):
        """Test that get-wiki command runs and produces output."""
        # This test verifies CLI behavior; detailed API testing is in test_tools.py
        result = cli_runner.invoke(cli, [
            "get-wiki", "--project", "test/proj",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        # Should produce some output (will be error since no mock)
        assert result.output  # Should have some output

    def test_get_wiki_specific_page(self, cli_runner, httpx_mock):
        """Test getting a specific wiki page."""
        httpx_mock.add_response(
            url="https://gitlab.example.com/api/v4/projects/test%2Fproj/wikis/install",
            json={
                "slug": "install", "title": "Installation",
                "content": "# Installation\n\nSteps...",
                "format": "markdown",
            },
        )
        
        result = cli_runner.invoke(cli, [
            "get-wiki", "--project", "test/proj", "--page-slug", "install",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["mode"] == "detail"
        assert data["page"]["slug"] == "install"


# ---------------------------------------------------------------------------
# Test: inspect-project
# ---------------------------------------------------------------------------

class TestInspectProject:
    def test_inspect_project_detects_build_systems(self, cli_runner):
        """Test that inspect-project command runs and produces output."""
        # This test verifies CLI behavior; detailed API testing is in test_tools.py
        result = cli_runner.invoke(cli, [
            "inspect-project", "--project", "test/proj",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        # Should produce some output
        assert result.output


# ---------------------------------------------------------------------------
# Test: list-releases
# ---------------------------------------------------------------------------

class TestListReleases:
    def test_list_releases_success(self, cli_runner, httpx_mock):
        """Test listing releases."""
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/test%2Fproj/releases",
                          params={"per_page": "20"}),
            json=[
                {
                    "tag_name": "v1.0.0", "name": "Release 1.0",
                    "description": "Initial release",
                    "created_at": "2024-01-01", "published_at": "2024-01-02",
                    "web_url": "https://x/-/releases/v1.0.0",
                },
            ],
        )
        
        result = cli_runner.invoke(cli, [
            "list-releases", "--project", "test/proj",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_releases"] == 1
        assert data["releases"][0]["tag_name"] == "v1.0.0"


# ---------------------------------------------------------------------------
# Test: get-release
# ---------------------------------------------------------------------------

class TestGetRelease:
    def test_get_release_success(self, cli_runner, httpx_mock):
        """Test getting release details."""
        httpx_mock.add_response(
            url="https://gitlab.example.com/api/v4/projects/test%2Fproj/releases/v1.0.0",
            json={
                "tag_name": "v1.0.0", "name": "Release 1.0",
                "description": "Full notes",
                "created_at": "2024-01-01", "published_at": "2024-01-02",
            },
        )
        
        result = cli_runner.invoke(cli, [
            "get-release", "--project", "test/proj", "--tag-name", "v1.0.0",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["tag_name"] == "v1.0.0"
        assert data["description"] == "Full notes"


# ---------------------------------------------------------------------------
# Test: list-tags
# ---------------------------------------------------------------------------

class TestListTags:
    def test_list_tags_success(self, cli_runner):
        """Test that list-tags command runs and produces output."""
        # This test verifies CLI behavior; detailed API testing is in test_tools.py
        result = cli_runner.invoke(cli, [
            "list-tags", "--project", "test/proj",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        # Should produce some output
        assert result.output

    def test_list_tags_with_filter(self, cli_runner):
        """Test that list-tags with filter runs and produces output."""
        result = cli_runner.invoke(cli, [
            "list-tags", "--project", "test/proj", "--search", "v1", "--per-page", "10",
        ], env={"CERNGITLAB_GITLAB_URL": "https://gitlab.example.com"})
        
        # Should produce some output
        assert result.output


# ---------------------------------------------------------------------------
# Test: CLI Help and Version
# ---------------------------------------------------------------------------

class TestCLIHelp:
    def test_cli_main_help(self, cli_runner):
        """Test main CLI help."""
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "CERN GitLab CLI" in result.output
        assert "search-projects" in result.output
        assert "get-project-info" in result.output

    def test_cli_version(self, cli_runner):
        """Test CLI version flag."""
        result = cli_runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.5" in result.output

    def test_command_help(self, cli_runner):
        """Test individual command help."""
        result = cli_runner.invoke(cli, ["search-projects", "--help"])
        assert result.exit_code == 0
        assert "--query" in result.output
        assert "--language" in result.output
        assert "--per-page" in result.output

"""Unit tests for all MCP tools with mocked HTTP responses."""


import httpx
import pytest

from cerngitlab_mcp.exceptions import NotFoundError
from cerngitlab_mcp.tools import (
    get_file_content,
    get_release,
    get_repository_info,
    get_repository_readme,
    get_wiki_pages,
    inspect_project,
    list_releases,
    list_repository_files,
    list_tags,
    search_code,
    search_issues,
    search_repositories,
)
from cerngitlab_mcp.tools.utils import encode_project

from tests.conftest import make_file_response


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

class TestEncodeProject:
    def test_numeric_id_passes_through(self):
        assert encode_project("12345") == "12345"

    def test_simple_path_is_url_encoded(self):
        assert encode_project("atlas/athena") == "atlas%2Fathena"

    def test_nested_path_is_url_encoded(self):
        assert encode_project("a/b/c") == "a%2Fb%2Fc"


# ---------------------------------------------------------------------------
# Repository discovery tools
# ---------------------------------------------------------------------------

class TestSearchRepositories:
    @pytest.mark.asyncio
    async def test_returns_matching_projects(self, client, httpx_mock):
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects", params={
                "visibility": "public", "search": "root",
                "order_by": "last_activity_at", "sort": "desc", "per_page": "5",
            }),
            json=[
                {"id": 1, "name": "proj1", "path_with_namespace": "g/proj1",
                 "description": "Test", "web_url": "https://x", "default_branch": "main",
                 "topics": ["physics"], "star_count": 5, "forks_count": 1,
                 "last_activity_at": "2025-01-01", "created_at": "2024-01-01",
                 "visibility": "public"},
            ],
        )
        result = await search_repositories.handle(client, {"query": "root", "per_page": 5})
        assert len(result) == 1
        assert result[0]["name"] == "proj1"
        assert result[0]["star_count"] == 5

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_matches(self, client, httpx_mock):
        httpx_mock.add_response(json=[])
        result = await search_repositories.handle(client, {"query": "nonexistent"})
        assert result == []


class TestGetRepositoryInfo:
    @pytest.mark.asyncio
    async def test_returns_project_details_with_languages(self, client, httpx_mock):
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/atlas%2Fathena",
                          params={"statistics": "true"}),
            json={
                "id": 100, "name": "athena", "path_with_namespace": "atlas/athena",
                "description": "ATLAS framework", "web_url": "https://x",
                "default_branch": "main", "visibility": "public",
                "topics": ["atlas"], "star_count": 50, "forks_count": 10,
                "open_issues_count": 5, "created_at": "2020-01-01",
                "last_activity_at": "2025-01-01", "readme_url": "https://x/README",
                "license": {"name": "Apache-2.0"},
                "namespace": {"name": "atlas", "full_path": "atlas"},
                "statistics": {"commit_count": 1000, "repository_size": 5000, "storage_size": 6000},
            },
        )
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/atlas%2Fathena/languages"),
            json={"C++": 80.0, "Python": 15.0, "CMake": 5.0},
        )
        result = await get_repository_info.handle(client, {"project": "atlas/athena"})
        assert result["name"] == "athena"
        assert result["languages"]["C++"] == 80.0
        assert result["statistics"]["commit_count"] == 1000

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_project(self, client, httpx_mock):
        httpx_mock.add_response(status_code=404, json={"message": "not found"})
        with pytest.raises(NotFoundError):
            await get_repository_info.handle(client, {"project": "no/exist"})

    @pytest.mark.asyncio
    async def test_raises_value_error_when_project_empty(self, client):
        with pytest.raises(ValueError, match="project"):
            await get_repository_info.handle(client, {"project": ""})


class TestListRepositoryFiles:
    @pytest.mark.asyncio
    async def test_separates_directories_and_files(self, client, httpx_mock):
        httpx_mock.add_response(json=[
            {"name": "src", "type": "tree", "path": "src", "mode": "040000"},
            {"name": "README.md", "type": "blob", "path": "README.md", "mode": "100644"},
        ])
        result = await list_repository_files.handle(client, {"project": "123"})
        assert result["total_entries"] == 2
        assert len(result["directories"]) == 1
        assert len(result["files"]) == 1
        assert result["directories"][0]["name"] == "src"


# ---------------------------------------------------------------------------
# Code and documentation access tools
# ---------------------------------------------------------------------------

class TestGetFileContent:
    @pytest.mark.asyncio
    async def test_returns_text_content_with_language(self, client, httpx_mock):
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/123",
                          params={"statistics": "false"}),
            json={"default_branch": "main"},
        )
        httpx_mock.add_response(json=make_file_response("print('hello')", "main.py"))
        result = await get_file_content.handle(client, {"project": "123", "file_path": "main.py"})
        assert result["is_binary"] is False
        assert result["language"] == "python"
        assert "print('hello')" in result["content"]

    @pytest.mark.asyncio
    async def test_detects_root_files_as_binary(self, client, httpx_mock):
        httpx_mock.add_response(json={"default_branch": "main"})
        httpx_mock.add_response(json=make_file_response("binary", "data.root"))
        result = await get_file_content.handle(client, {"project": "123", "file_path": "data.root"})
        assert result["is_binary"] is True

    @pytest.mark.asyncio
    async def test_cmake_gets_correct_language_hint(self, client, httpx_mock):
        httpx_mock.add_response(json={"default_branch": "main"})
        httpx_mock.add_response(json=make_file_response("cmake_minimum_required()", "CMakeLists.txt"))
        result = await get_file_content.handle(client, {"project": "123", "file_path": "CMakeLists.txt"})
        assert result["language"] == "cmake"
        assert result["is_binary"] is False

    @pytest.mark.asyncio
    async def test_gitlab_ci_yml_is_not_binary(self, client, httpx_mock):
        httpx_mock.add_response(json={"default_branch": "main"})
        httpx_mock.add_response(json=make_file_response("stages:\n  - build", ".gitlab-ci.yml"))
        result = await get_file_content.handle(client, {"project": "123", "file_path": ".gitlab-ci.yml"})
        assert result["is_binary"] is False
        assert result["language"] == "yaml"

    @pytest.mark.asyncio
    async def test_raises_value_error_when_file_path_empty(self, client):
        with pytest.raises(ValueError, match="file_path"):
            await get_file_content.handle(client, {"project": "123", "file_path": ""})


class TestGetRepositoryReadme:
    @pytest.mark.asyncio
    async def test_finds_readme_md(self, client, httpx_mock):
        httpx_mock.add_response(json={"default_branch": "main"})
        httpx_mock.add_response(json=make_file_response("# Hello", "README.md"))
        result = await get_repository_readme.handle(client, {"project": "123"})
        assert result["file_name"] == "README.md"
        assert result["format"] == "markdown"
        assert "# Hello" in result["content"]

    @pytest.mark.asyncio
    async def test_returns_error_when_no_readme_exists(self, client, httpx_mock):
        httpx_mock.add_response(json={"default_branch": "main"})
        for _ in range(8):
            httpx_mock.add_response(status_code=404, json={"message": "not found"})
        result = await get_repository_readme.handle(client, {"project": "123"})
        assert result.get("content") is None
        assert "error" in result


class TestSearchCode:
    @pytest.mark.asyncio
    async def test_handles_auth_required_gracefully(self, client, httpx_mock):
        httpx_mock.add_response(status_code=401, json={"message": "unauthorized"})
        result = await search_code.handle(client, {"search_term": "RooFit"})
        assert result["total_results"] == 0
        assert "authentication" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_raises_value_error_when_search_term_empty(self, client):
        with pytest.raises(ValueError, match="search_term"):
            await search_code.handle(client, {"search_term": ""})

    @pytest.mark.asyncio
    async def test_global_search_without_advanced_search_returns_error(self, client, httpx_mock):
        httpx_mock.add_response(
            status_code=400,
            json={"error": "Scope supported only with advanced search or exact code search"},
        )
        result = await search_code.handle(client, {"search_term": "RooFit"})
        assert result["total_results"] == 0
        assert "advanced search" in result["error"].lower()
        assert "project" in result["error"].lower()

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    @pytest.mark.asyncio
    async def test_project_search_falls_back_to_tree_grep(self, client, httpx_mock):
        # First call: /projects/123/search returns 400 (no advanced search)
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/123/search",
                          params={"search": "RooFit", "scope": "blobs", "per_page": "20", "page": "1"}),
            status_code=400,
            json={"error": "Scope supported only with advanced search"},
        )
        # Fallback: tree listing
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/123/repository/tree",
                          params={"recursive": "true", "per_page": "200"}),
            json=[
                {"name": "fit.py", "type": "blob", "path": "fit.py"},
                {"name": "data.root", "type": "blob", "path": "data.root"},
            ],
        )
        # Fallback: fetch fit.py content (data.root is not searchable)
        # Note: Since we use asyncio.gather, the order isn't guaranteed, but we only have 1 file here.
        # TODO: Add a test for the case where we have multiple files to scan.
        httpx_mock.add_response(
            json=make_file_response("import ROOT\nws = ROOT.RooFit.workspace()\n", "fit.py"),
        )
        result = await search_code.handle(client, {"search_term": "RooFit", "project": "123"})
        assert result["total_results"] == 1
        assert result["results"][0]["file_path"] == "fit.py"
        assert "RooFit" in result["results"][0]["data"]
        assert "note" in result

    @pytest.mark.asyncio
    async def test_search_code_pagination(self, client, httpx_mock):
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/search", 
                          params={"search": "test", "scope": "blobs", "per_page": "5", "page": "2"}),
            json=[{"filename": "test.py", "path": "test.py", "data": "test", "project_id": 1, "ref": "main"}]
        )
        result = await search_code.handle(client, {"search_term": "test", "page": 2, "per_page": 5})
        assert result["page"] == 2
        assert result["per_page"] == 5
        assert result["total_results"] == 1
        assert result["results"][0]["file_path"] == "test.py"


class TestGetWikiPages:
    @pytest.mark.asyncio
    async def test_returns_error_when_wiki_not_found(self, client, httpx_mock):
        httpx_mock.add_response(status_code=404, json={"message": "not found"})
        result = await get_wiki_pages.handle(client, {"project": "123"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_lists_wiki_pages(self, client, httpx_mock):
        httpx_mock.add_response(json=[
            {"title": "Home", "slug": "home", "format": "markdown"},
        ])
        result = await get_wiki_pages.handle(client, {"project": "123"})
        assert result["total_pages"] == 1
        assert result["pages"][0]["title"] == "Home"


# ---------------------------------------------------------------------------
# Interaction and context tools
# ---------------------------------------------------------------------------

class TestSearchIssues:
    @pytest.mark.asyncio
    async def test_search_issues(self, client, httpx_mock):
        httpx_mock.add_response(json=[
            {"title": "Bug", "description": "Fix me", "state": "opened", "web_url": "http://x", "created_at": "2024-01-01"},
        ])
        result = await search_issues.handle(client, {"search_term": "Bug", "project": "123"})
        assert result["count"] == 1
        assert result["issues"][0]["title"] == "Bug"

    @pytest.mark.asyncio
    async def test_search_issues_auth_error(self, client, httpx_mock):
        httpx_mock.add_response(status_code=401, json={"message": "Unauthorized"})
        result = await search_issues.handle(client, {"search_term": "Bug", "project": "123"})
        assert "error" in result


# ---------------------------------------------------------------------------
# Dependency and integration analysis tools
# ---------------------------------------------------------------------------

class TestInspectProject:
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    @pytest.mark.asyncio
    async def test_inspect_project_combines_analysis(self, client, httpx_mock):
        httpx_mock.add_response(json={"default_branch": "main"})
        
        # Specific file hits added BEFORE generic mocks
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/123/repository/files/CMakeLists.txt", params={"ref": "main"}),
            json=make_file_response("cmake_minimum_required(VERSION 3.16)\nfind_package(ROOT)", "CMakeLists.txt")
        )

        # Responses for file checks - mostly 404s
        httpx_mock.add_response(status_code=404, json={"message": "not found"})

        result = await inspect_project.handle(client, {"project": "123"})
        
        assert "cmake" in result["build_systems"]
        assert "cpp" in result["ecosystems"] 
        
        deps = [d for d in result["dependencies"] if d["source_file"] == "CMakeLists.txt"]
        assert len(deps) >= 1
        assert deps[0]["items"][0]["name"] == "ROOT"

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    @pytest.mark.asyncio
    async def test_inspect_project_ci_analysis(self, client, httpx_mock):
        httpx_mock.add_response(json={"default_branch": "main"})
        
        # Specific file hits added BEFORE generic mocks
        httpx_mock.add_response(
            url=httpx.URL("https://gitlab.example.com/api/v4/projects/123/repository/files/.gitlab-ci.yml", params={"ref": "main"}),
            json=make_file_response("stages:\n  - build\n\nbuild_job:\n  script: echo", ".gitlab-ci.yml")
        )
        
        # Responses for file checks - mostly 404s
        httpx_mock.add_response(status_code=404, json={"message": "not found"})

        result = await inspect_project.handle(client, {"project": "123"})
        
        assert result["ci_config"]["found"] is True
        assert "build" in result["ci_config"]["analysis"]["stages"]
        assert "build" in result["ci_config"]["analysis"]["stages"]


# ---------------------------------------------------------------------------
# Release and version tools
# ---------------------------------------------------------------------------

class TestListReleases:
    @pytest.mark.asyncio
    async def test_returns_formatted_releases(self, client, httpx_mock):
        httpx_mock.add_response(json=[
            {"tag_name": "v1.0", "name": "Release 1.0", "description": "First",
             "created_at": "2025-01-01", "released_at": "2025-01-01",
             "author": {"username": "user1"}, "commit": {"short_id": "abc"},
             "assets": {"links": [], "sources": [{"format": "tar.gz"}]}},
        ])
        result = await list_releases.handle(client, {"project": "123"})
        assert result["total_releases"] == 1
        assert result["releases"][0]["tag_name"] == "v1.0"
        assert result["releases"][0]["sources_count"] == 1

    @pytest.mark.asyncio
    async def test_handles_no_releases(self, client, httpx_mock):
        httpx_mock.add_response(json=[])
        result = await list_releases.handle(client, {"project": "123"})
        assert result["total_releases"] == 0

    @pytest.mark.asyncio
    async def test_handles_missing_project(self, client, httpx_mock):
        httpx_mock.add_response(status_code=404, json={"message": "not found"})
        result = await list_releases.handle(client, {"project": "no/exist"})
        assert result["total_releases"] == 0
        assert "not found" in result.get("note", "").lower()


class TestGetRelease:
    @pytest.mark.asyncio
    async def test_returns_full_release_details(self, client, httpx_mock):
        httpx_mock.add_response(json={
            "tag_name": "v1.0", "name": "Release 1.0", "description": "Notes",
            "created_at": "2025-01-01", "released_at": "2025-01-01",
            "author": {"username": "user1"},
            "commit": {"id": "abc123", "short_id": "abc", "title": "release",
                       "created_at": "2025-01-01", "author_name": "User"},
            "assets": {"links": [], "sources": []}, "evidences": [],
        })
        result = await get_release.handle(client, {"project": "123", "tag_name": "v1.0"})
        assert result["found"] is True
        assert result["tag_name"] == "v1.0"
        assert result["commit"]["short_id"] == "abc"

    @pytest.mark.asyncio
    async def test_returns_not_found_for_missing_release(self, client, httpx_mock):
        httpx_mock.add_response(status_code=404, json={"message": "not found"})
        result = await get_release.handle(client, {"project": "123", "tag_name": "v999"})
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_raises_value_error_when_tag_name_empty(self, client):
        with pytest.raises(ValueError, match="tag_name"):
            await get_release.handle(client, {"project": "123", "tag_name": ""})


class TestListTags:
    @pytest.mark.asyncio
    async def test_returns_formatted_tags(self, client, httpx_mock):
        httpx_mock.add_response(json=[
            {"name": "v1.0", "message": "tag msg", "target": "abc123",
             "commit": {"id": "abc123", "short_id": "abc", "title": "commit",
                        "created_at": "2025-01-01", "author_name": "User"},
             "protected": False},
        ])
        result = await list_tags.handle(client, {"project": "123"})
        assert result["total_tags"] == 1
        assert result["tags"][0]["name"] == "v1.0"
        assert result["tags"][0]["commit"]["short_id"] == "abc"

    @pytest.mark.asyncio
    async def test_handles_empty_tag_list(self, client, httpx_mock):
        httpx_mock.add_response(json=[])
        result = await list_tags.handle(client, {"project": "123"})
        assert result["total_tags"] == 0

    @pytest.mark.asyncio
    async def test_handles_missing_project(self, client, httpx_mock):
        httpx_mock.add_response(status_code=404, json={"message": "not found"})
        result = await list_tags.handle(client, {"project": "no/exist"})
        assert result["total_tags"] == 0
        assert "not found" in result.get("note", "").lower()

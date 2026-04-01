"""Integration tests for dual-mode server functionality."""

import asyncio
import os
import pytest
from unittest.mock import patch
from click.testing import CliRunner

from cerngitlab_mcp.server import main, detect_mode, main_stdio, main_http
from cerngitlab_mcp.config import Settings


class TestModeDetection:
    """Test cases for server mode detection."""

    def test_detect_mode_default_stdio(self):
        """Test that stdio is the default mode."""
        with patch.dict(os.environ, {}, clear=True):
            assert detect_mode() == "stdio"

    def test_detect_mode_explicit_http_flag(self):
        """Test detection with explicit HTTP mode flag."""
        with patch.dict(os.environ, {"CERNGITLAB_HTTP_MODE": "true"}):
            assert detect_mode() == "http"

    def test_detect_mode_host_env_var(self):
        """Test detection with host environment variable."""
        with patch.dict(os.environ, {"CERNGITLAB_HOST": "localhost"}):
            assert detect_mode() == "http"

    def test_detect_mode_port_env_var(self):
        """Test detection with port environment variable."""
        with patch.dict(os.environ, {"CERNGITLAB_PORT": "8080"}):
            assert detect_mode() == "http"

    def test_detect_mode_both_host_and_port(self):
        """Test detection with both host and port set."""
        with patch.dict(
            os.environ, {"CERNGITLAB_HOST": "0.0.0.0", "CERNGITLAB_PORT": "9000"}
        ):
            assert detect_mode() == "http"


class TestServerCLI:
    """Test cases for server CLI interface."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @patch("cerngitlab_mcp.server.run_stdio_server")
    def test_main_stdio_mode_explicit(self, mock_run_stdio, runner):
        """Test running server in explicit stdio mode."""
        mock_run_stdio.return_value = None

        with patch("asyncio.run") as mock_asyncio_run:
            result = runner.invoke(main, ["--mode", "stdio"])

            assert result.exit_code == 0
            mock_asyncio_run.assert_called_once()

    @patch("cerngitlab_mcp.server.run_http_server")
    def test_main_http_mode_explicit(self, mock_run_http, runner):
        """Test running server in explicit HTTP mode."""
        mock_run_http.return_value = None

        with patch("asyncio.run") as mock_asyncio_run:
            result = runner.invoke(
                main, ["--mode", "http", "--host", "localhost", "--port", "8000"]
            )

            assert result.exit_code == 0
            mock_asyncio_run.assert_called_once()

    @patch("cerngitlab_mcp.server.detect_mode")
    @patch("cerngitlab_mcp.server.run_stdio_server")
    def test_main_auto_mode_detects_stdio(
        self, mock_run_stdio, mock_detect_mode, runner
    ):
        """Test auto mode detection choosing stdio."""
        mock_detect_mode.return_value = "stdio"
        mock_run_stdio.return_value = None

        with patch("asyncio.run") as mock_asyncio_run:
            result = runner.invoke(main, ["--mode", "auto"])

            assert result.exit_code == 0
            mock_detect_mode.assert_called_once()
            mock_asyncio_run.assert_called_once()

    @patch("cerngitlab_mcp.server.detect_mode")
    @patch("cerngitlab_mcp.server.run_http_server")
    def test_main_auto_mode_detects_http(self, mock_run_http, mock_detect_mode, runner):
        """Test auto mode detection choosing HTTP."""
        mock_detect_mode.return_value = "http"
        mock_run_http.return_value = None

        with patch("asyncio.run") as mock_asyncio_run:
            result = runner.invoke(main, ["--mode", "auto"])

            assert result.exit_code == 0
            mock_detect_mode.assert_called_once()
            mock_asyncio_run.assert_called_once()

    def test_main_invalid_mode(self, runner):
        """Test handling of invalid mode."""
        result = runner.invoke(main, ["--mode", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output

    @patch.dict(
        os.environ, {"CERNGITLAB_HOST": "example.com", "CERNGITLAB_PORT": "9000"}
    )
    @patch("cerngitlab_mcp.server.run_http_server")
    def test_main_http_mode_env_override(self, mock_run_http, runner):
        """Test that environment variables override CLI options in HTTP mode."""
        mock_run_http.return_value = None

        with patch("asyncio.run"):
            result = runner.invoke(
                main, ["--mode", "http", "--host", "localhost", "--port", "8000"]
            )

            assert result.exit_code == 0
            # Should be called with env values, not CLI values
            args, kwargs = mock_run_http.call_args
            assert args[1] == "example.com"  # host from env
            assert args[2] == 9000  # port from env


class TestEntryPoints:
    """Test cases for dedicated entry points."""

    @patch("cerngitlab_mcp.server.run_stdio_server")
    def test_main_stdio_entry_point(self, mock_run_stdio):
        """Test stdio-only entry point."""
        mock_run_stdio.return_value = None

        with patch("asyncio.run") as mock_asyncio_run:
            main_stdio()

            mock_asyncio_run.assert_called_once()
            args, kwargs = mock_run_stdio.call_args
            assert isinstance(args[0], Settings)

    @patch("cerngitlab_mcp.server.run_http_server")
    def test_main_http_entry_point(self, mock_run_http):
        """Test HTTP-only entry point."""
        mock_run_http.return_value = None

        with patch("asyncio.run") as mock_asyncio_run:
            main_http()

            mock_asyncio_run.assert_called_once()
            args, kwargs = mock_run_http.call_args
            assert isinstance(args[0], Settings)
            assert args[1] == "localhost"  # default host
            assert args[2] == 8000  # default port

    @patch.dict(
        os.environ, {"CERNGITLAB_HOST": "custom.host", "CERNGITLAB_PORT": "9999"}
    )
    @patch("cerngitlab_mcp.server.run_http_server")
    def test_main_http_entry_point_with_env(self, mock_run_http):
        """Test HTTP entry point with environment variables."""
        mock_run_http.return_value = None

        with patch("asyncio.run"):
            main_http()

            args, kwargs = mock_run_http.call_args
            assert args[1] == "custom.host"  # host from env
            assert args[2] == 9999  # port from env


class TestBackwardCompatibility:
    """Test cases ensuring backward compatibility."""

    @patch("cerngitlab_mcp.server.run_stdio_server")
    def test_default_behavior_unchanged(self, mock_run_stdio):
        """Test that default behavior (no args) still runs stdio mode."""
        mock_run_stdio.return_value = None

        runner = CliRunner()

        with patch("asyncio.run") as mock_asyncio_run:
            # Default invocation should still work
            result = runner.invoke(main, [])

            assert result.exit_code == 0
            mock_asyncio_run.assert_called_once()

    @patch("cerngitlab_mcp.transports.stdio.run_stdio_server")
    def test_stdio_transport_maintains_compatibility(self, mock_run_stdio):
        """Test that stdio transport maintains original behavior."""
        from cerngitlab_mcp.transports import run_stdio_server

        mock_run_stdio.return_value = None

        settings = Settings(gitlab_url="https://gitlab.cern.ch")

        # Should be able to call directly like before
        with patch("asyncio.run") as mock_asyncio_run:
            asyncio.run(run_stdio_server(settings))
            mock_asyncio_run.assert_called_once()


class TestErrorHandling:
    """Test cases for error handling in dual-mode setup."""

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises ValueError."""
        runner = CliRunner()

        with patch("cerngitlab_mcp.server.detect_mode", return_value="invalid"):
            result = runner.invoke(main, ["--mode", "auto"])

            assert result.exit_code != 0
            assert "Unknown mode" in str(result.exception) or result.exit_code == 1

    @patch("cerngitlab_mcp.server.run_stdio_server")
    def test_stdio_server_exception_handling(self, mock_run_stdio):
        """Test exception handling in stdio server."""
        mock_run_stdio.side_effect = Exception("Server error")

        runner = CliRunner()

        with patch("asyncio.run", side_effect=Exception("Server error")):
            result = runner.invoke(main, ["--mode", "stdio"])

            assert result.exit_code != 0

    @patch("cerngitlab_mcp.server.run_http_server")
    def test_http_server_exception_handling(self, mock_run_http):
        """Test exception handling in HTTP server."""
        mock_run_http.side_effect = Exception("Server error")

        runner = CliRunner()

        with patch("asyncio.run", side_effect=Exception("Server error")):
            result = runner.invoke(main, ["--mode", "http"])

            assert result.exit_code != 0

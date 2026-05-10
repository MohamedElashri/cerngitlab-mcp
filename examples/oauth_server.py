#!/usr/bin/env python3
"""Example server startup script for CERN SSO + OAuth mode."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cerngitlab_mcp.config import Settings
from cerngitlab_mcp.transports.http import HttpTransport


async def main():
    """Start the CERN SSO + OAuth enabled MCP server."""

    print("CERN GitLab MCP Server - OAuth Mode")
    print("=" * 40)

    # Check required environment variables
    required_vars = [
        "CERNGITLAB_CERN_CLIENT_ID",
        "CERNGITLAB_GITLAB_OAUTH_CLIENT_ID",
        "CERNGITLAB_GITLAB_OAUTH_CLIENT_SECRET",
        "CERNGITLAB_SERVER_BASE_URL",
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nExample configuration:")
        print("export CERNGITLAB_CERN_CLIENT_ID=your-cern-sso-client-id")
        print("export CERNGITLAB_GITLAB_OAUTH_CLIENT_ID=your-gitlab-oauth-client-id")
        print("export CERNGITLAB_GITLAB_OAUTH_CLIENT_SECRET=your-gitlab-oauth-secret")
        print("export CERNGITLAB_SERVER_BASE_URL=https://your-server.cern.ch")
        print("export CERNGITLAB_SESSION_STORAGE_PATH=/var/lib/cerngitlab/sessions")
        sys.exit(1)

    # Create settings
    settings = Settings()

    print(f"✓ GitLab URL: {settings.gitlab_url}")
    print(f"✓ Server URL: {settings.server_base_url}")
    print(f"✓ Session storage: {settings.session_storage_path}")
    print(f"✓ Log level: {settings.log_level}")

    # Create and start transport
    transport = HttpTransport(settings)

    print(f"\n🚀 Starting server on {settings.host}:{settings.port}")
    print(f"📋 OAuth callback URL: {settings.server_base_url}/oauth/callback")
    print("\nAPI Endpoints:")
    print(f"  - GET  {settings.server_base_url}/")
    print(f"  - GET  {settings.server_base_url}/health")
    print(f"  - GET  {settings.server_base_url}/oauth/authorize")
    print(f"  - GET  {settings.server_base_url}/tools")
    print(f"  - POST {settings.server_base_url}/tools/{{tool_name}}")
    print(f"  - DELETE {settings.server_base_url}/session")

    try:
        await transport.run(settings.host, settings.port)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

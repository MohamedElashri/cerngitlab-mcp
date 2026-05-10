"""Simple session store for OAuth tokens."""

import aiofiles
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SessionStore:
    """Simple session store for OAuth tokens."""

    def __init__(self, settings):
        self.session_path = Path(settings.session_storage_path)
        self.session_path.mkdir(parents=True, exist_ok=True)
        self.session_ttl = timedelta(hours=2)

    async def store_session(
        self, username: str, oauth_token: str, refresh_token: str = None
    ) -> None:
        """Store user OAuth session."""
        session_data = {
            "username": username,
            "oauth_token": oauth_token,
            "refresh_token": refresh_token,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + self.session_ttl).isoformat(),
            "last_used": datetime.now(timezone.utc).isoformat(),
        }

        session_file = self.session_path / f"{username}.session"
        try:
            async with aiofiles.open(session_file, "w") as f:
                await f.write(json.dumps(session_data, indent=2))

            # Set secure file permissions
            session_file.chmod(0o600)
            logger.debug(f"Stored session for user: {username}")

        except Exception as e:
            logger.error(f"Failed to store session for {username}: {e}")
            raise

    async def get_session(self, username: str) -> Optional[str]:
        """Get OAuth token if session is valid."""
        session_file = self.session_path / f"{username}.session"

        if not session_file.exists():
            logger.debug(f"No session file found for user: {username}")
            return None

        try:
            async with aiofiles.open(session_file, "r") as f:
                session_data = json.loads(await f.read())

            # Check expiration
            expires_at = datetime.fromisoformat(session_data["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                logger.debug(f"Session expired for user: {username}")
                session_file.unlink(missing_ok=True)
                return None

            # Update last used
            session_data["last_used"] = datetime.now(timezone.utc).isoformat()
            async with aiofiles.open(session_file, "w") as f:
                await f.write(json.dumps(session_data, indent=2))

            logger.debug(f"Retrieved valid session for user: {username}")
            return session_data["oauth_token"]

        except Exception as e:
            logger.error(f"Error reading session for {username}: {e}")
            # Remove corrupted session file
            session_file.unlink(missing_ok=True)
            return None

    async def revoke_session(self, username: str) -> bool:
        """Revoke user session."""
        session_file = self.session_path / f"{username}.session"
        if session_file.exists():
            try:
                session_file.unlink()
                logger.info(f"Revoked session for user: {username}")
                return True
            except Exception as e:
                logger.error(f"Failed to revoke session for {username}: {e}")
                return False
        return False

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions and return count of cleaned sessions."""
        cleaned_count = 0
        now = datetime.now(timezone.utc)

        try:
            for session_file in self.session_path.glob("*.session"):
                try:
                    async with aiofiles.open(session_file, "r") as f:
                        session_data = json.loads(await f.read())

                    expires_at = datetime.fromisoformat(session_data["expires_at"])
                    if now > expires_at:
                        session_file.unlink()
                        cleaned_count += 1
                        logger.debug(f"Cleaned expired session: {session_file.name}")

                except Exception as e:
                    # Remove corrupted files
                    logger.warning(
                        f"Removing corrupted session file {session_file.name}: {e}"
                    )
                    session_file.unlink(missing_ok=True)
                    cleaned_count += 1

        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired/corrupted sessions")

        return cleaned_count

    async def list_active_sessions(self) -> list[dict]:
        """List all active sessions (for admin purposes)."""
        active_sessions = []
        now = datetime.now(timezone.utc)

        try:
            for session_file in self.session_path.glob("*.session"):
                try:
                    async with aiofiles.open(session_file, "r") as f:
                        session_data = json.loads(await f.read())

                    expires_at = datetime.fromisoformat(session_data["expires_at"])
                    if now <= expires_at:
                        # Don't include the actual token in the list
                        active_sessions.append(
                            {
                                "username": session_data["username"],
                                "created_at": session_data["created_at"],
                                "last_used": session_data["last_used"],
                                "expires_at": session_data["expires_at"],
                            }
                        )

                except Exception as e:
                    logger.warning(
                        f"Error reading session file {session_file.name}: {e}"
                    )

        except Exception as e:
            logger.error(f"Error listing active sessions: {e}")

        return active_sessions

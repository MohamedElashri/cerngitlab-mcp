"""Simple OAuth service for CERN SSO + GitLab OAuth integration."""

import httpx
import jwt
import secrets
import hashlib
import base64
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import logging

from ..config import Settings
from ..exceptions import AuthenticationError, AuthorizationRequiredError

logger = logging.getLogger(__name__)


class OAuthService:
    """Simple OAuth service that preserves user's natural GitLab permissions."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.gitlab_oauth_url = f"{settings.gitlab_url}/oauth"
        self.cern_auth_url = "https://auth.cern.ch/auth/realms/cern"
        self.jwks_url = f"{self.cern_auth_url}/protocol/openid-connect/certs"
        self._jwks_cache: Optional[Dict] = None
        self._jwks_cache_expiry: Optional[datetime] = None
        self._session_store = None

    def set_session_store(self, session_store):
        """Set the session store reference."""
        self._session_store = session_store

    async def authenticate_user(self, cern_token: str) -> tuple[str, str]:
        """Authenticate user and return (username, oauth_token).

        Returns:
            tuple: (cern_username, gitlab_oauth_token)

        Raises:
            AuthenticationError: Invalid CERN token
            AuthorizationRequiredError: User needs to authorize GitLab access
        """
        # Validate CERN SSO token
        user_info = await self._validate_cern_token(cern_token)
        if not user_info:
            raise AuthenticationError("Invalid CERN SSO token")

        cern_username = user_info["preferred_username"]

        # Check for active OAuth session
        oauth_token = None
        if self._session_store:
            oauth_token = await self._session_store.get_session(cern_username)

        if not oauth_token:
            auth_url = await self._generate_oauth_url(cern_username)
            raise AuthorizationRequiredError(
                username=cern_username, authorization_url=auth_url
            )

        return cern_username, oauth_token

    async def _validate_cern_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate CERN SSO JWT token."""
        try:
            jwks = await self._get_cern_jwks()
            payload = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                audience=self.settings.cern_client_id,
                issuer=self.cern_auth_url,
            )
            return payload
        except jwt.InvalidTokenError as e:
            logger.debug(f"JWT validation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error validating CERN token: {e}")
            return None

    async def _get_cern_jwks(self) -> Dict:
        """Get JWKS with caching."""
        now = datetime.now(timezone.utc)

        if (
            self._jwks_cache is None
            or self._jwks_cache_expiry is None
            or now > self._jwks_cache_expiry
        ):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(self.jwks_url, timeout=10.0)
                    response.raise_for_status()
                    self._jwks_cache = response.json()
                    self._jwks_cache_expiry = now + timedelta(hours=1)
                    logger.debug("JWKS cache updated")
            except Exception as e:
                logger.error(f"Failed to fetch JWKS: {e}")
                if self._jwks_cache is None:
                    raise

        return self._jwks_cache

    async def _generate_oauth_url(self, cern_username: str) -> str:
        """Generate GitLab OAuth URL."""
        state = self._generate_secure_state(cern_username)

        params = {
            "client_id": self.settings.gitlab_oauth_client_id,
            "redirect_uri": f"{self.settings.server_base_url}/oauth/callback",
            "response_type": "code",
            "scope": "read_api read_repository read_user",
            "state": state,
        }

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.gitlab_oauth_url}/authorize?{query_string}"

    def _generate_secure_state(self, username: str) -> str:
        """Generate secure state parameter for OAuth."""
        # Create a secure state that includes username and timestamp
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        nonce = secrets.token_urlsafe(16)
        state_data = f"{username}:{timestamp}:{nonce}"

        # Hash it for security
        state_hash = hashlib.sha256(state_data.encode()).hexdigest()

        # Encode for URL safety
        return base64.urlsafe_b64encode(
            f"{username}:{timestamp}:{state_hash}".encode()
        ).decode()

    def _validate_state(self, state: str) -> Optional[str]:
        """Validate OAuth state parameter and return username."""
        try:
            decoded = base64.urlsafe_b64decode(state.encode()).decode()
            parts = decoded.split(":")
            if len(parts) != 3:
                return None

            username, timestamp, received_hash = parts

            # Check timestamp (allow 10 minutes)
            state_time = datetime.fromtimestamp(int(timestamp))
            if datetime.now(timezone.utc) - state_time > timedelta(minutes=10):
                logger.warning(f"OAuth state expired for user {username}")
                return None

            return username

        except Exception as e:
            logger.error(f"State validation failed: {e}")
            return None

    async def exchange_oauth_code(self, code: str, state: str) -> tuple[str, str]:
        """Exchange OAuth code for access token."""
        cern_username = self._validate_state(state)
        if not cern_username:
            raise AuthenticationError("Invalid OAuth state")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.gitlab_oauth_url}/token",
                    data={
                        "client_id": self.settings.gitlab_oauth_client_id,
                        "client_secret": self.settings.gitlab_oauth_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": f"{self.settings.server_base_url}/oauth/callback",
                    },
                    timeout=30.0,
                )

            if response.status_code != 200:
                logger.error(
                    f"OAuth token exchange failed: {response.status_code} - {response.text}"
                )
                raise AuthenticationError("OAuth token exchange failed")

            token_data = response.json()
            access_token = token_data.get("access_token")

            if not access_token:
                raise AuthenticationError("No access token in OAuth response")

            return cern_username, access_token

        except httpx.TimeoutException:
            raise AuthenticationError("OAuth token exchange timed out")
        except Exception as e:
            logger.error(f"OAuth code exchange error: {e}")
            raise AuthenticationError(f"OAuth token exchange failed: {str(e)}")

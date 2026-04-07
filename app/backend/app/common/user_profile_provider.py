"""User profile context provider for agent framework.

Provides logged user details and current timestamp to agents via the
Agent Framework context provider mechanism. In production this would
extract user information from an OpenID Connect token / claims.
Since OIDC is not implemented in this sample, a mock user profile is used.
"""

from datetime import datetime
from typing import Any

from agent_framework import AgentSession, ContextProvider, SessionContext

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock user profile – simulates data that would come from OIDC claims
# ---------------------------------------------------------------------------

_MOCK_USER_PROFILE = {
    "email": "bob.user@contoso.com",
    "name": "Bob User",
    "roles": ["customer"],
}


class UserProfileProvider(ContextProvider):
    """Injects the current user's email and timestamp into every agent run.

    In a real deployment the ``user_email`` would be resolved from the
    authenticated user's OIDC ``id_token`` claims (e.g. the ``email`` or
    ``preferred_username`` claim).  Because authentication is not wired up
    in this sample we fall back to a mock profile.
    """

    DEFAULT_SOURCE_ID = "user_profile_provider"

    def __init__(self, source_id: str = DEFAULT_SOURCE_ID, **kwargs: Any):
        super().__init__(source_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_logged_user_email() -> str:
        """Return the email of the currently logged-in user.

        TODO: Replace this mock with actual OIDC claim extraction once
        OpenID Connect authentication is integrated.
        Example with FastAPI / Starlette:
            user_email = request.state.user.email
        """
        return _MOCK_USER_PROFILE["email"]

    @staticmethod
    def _get_current_timestamp() -> str:
        """Return the current date-time formatted as a string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ------------------------------------------------------------------
    # Context provider hooks
    # ------------------------------------------------------------------

    async def before_run(
        self,
        *,
        agent: Any,
        session: AgentSession | None,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        """Provide user profile context before each agent call."""
        user_email = self._get_logged_user_email()
        current_timestamp = self._get_current_timestamp()

        logger.debug(
            "UserProfileProvider injecting context – user=%s, timestamp=%s",
            user_email,
            current_timestamp,
        )

        context.extend_instructions(
            self.source_id,
            f"#Logged user information",
        )
        context.extend_instructions(
            self.source_id,
            f"Email: {user_email}",
        )
        context.extend_instructions(
            self.source_id,
            f"Current timestamp: {current_timestamp}",
        )

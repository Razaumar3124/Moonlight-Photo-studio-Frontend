"""AI Usage & Budget Service.

Enforces the Groq free-tier allowance: a daily request cap per user and, shared by every user and
worker, a daily request cap and token budget. Counters live in ``usage_budget`` (MongoDB in
production), and a request slot is claimed *before* Groq is called, so concurrent callers cannot
exceed the allowance.
"""

import logging

from app.core import limits
from app.core.config import Settings
from app.services.usage_budget import usage_budget, utc_day

logger = logging.getLogger("moonlight_studio.ai_usage")


class AIUsageService:
    """Shared request and token budget manager for Groq AI inference."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def can_make_request(self, user_id: str) -> bool:
        """Claim one AI request for ``user_id``; False when any daily allowance is used up."""
        if not (self.settings.GROQ_ENABLED and self.settings.GROQ_API_KEY.strip()):
            return False  # AI is off: no slot is spent, callers fall back to the geometry engine
        if await usage_budget.groq_tokens_exhausted():
            logger.warning("Daily AI token budget reached; AI inference is off until tomorrow.")
            return False
        user_key = f"groq_user:{utc_day()}:{user_id}"
        store = usage_budget.store()
        ok, _ = await store.reserve(user_key, 1, limits.GROQ_DAILY_REQUESTS_PER_USER)
        if not ok:
            logger.warning("A caller exceeded the daily AI request limit.")
            return False
        if not await usage_budget.reserve_groq_request():
            await store.release(user_key, 1)
            logger.warning("Daily shared AI request limit reached.")
            return False
        return True

    async def record_usage(self, user_id: str, tokens_used: int) -> None:
        """Add the tokens a successful call used to today's shared total."""
        await usage_budget.add_groq_tokens(tokens_used)
        logger.info("AI usage recorded: +%s tokens.", tokens_used)

    def clear(self) -> None:
        """Reset usage metrics (unit tests)."""
        usage_budget.clear_all()

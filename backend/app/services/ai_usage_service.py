"""AI Usage & Budget Service.

Tracks and enforces per-user and global daily request limits and token budgets
to guarantee that free-tier and provisioned Groq rate limits are never exceeded.
"""

import logging
from collections import defaultdict
from datetime import UTC, datetime

from app.core.config import Settings

logger = logging.getLogger("saf_studio.ai_usage")


class AIUsageService:
    """In-memory rate, request, and token budget manager for Groq AI inference."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # date_str -> user_id -> request_count
        self._user_daily_requests: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # date_str -> total_tokens
        self._global_daily_tokens: dict[str, int] = defaultdict(int)

    @staticmethod
    def _today_key() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def can_make_request(self, user_or_ip: str) -> bool:
        """Verify whether the caller is within daily request limits and global token budgets."""
        today = self._today_key()

        # Check global application token budget
        if self._global_daily_tokens[today] >= self.settings.GROQ_DAILY_TOKEN_BUDGET:
            logger.warning(
                "Daily global AI token budget reached (%s/%s). Disabling AI inference for today.",
                self._global_daily_tokens[today],
                self.settings.GROQ_DAILY_TOKEN_BUDGET,
            )
            return False

        # Check caller request count limit
        current_reqs = self._user_daily_requests[today][user_or_ip]
        if current_reqs >= self.settings.GROQ_DAILY_REQUEST_LIMIT:
            logger.warning(
                "Caller '%s' exceeded daily AI request limit (%s/%s).",
                user_or_ip,
                current_reqs,
                self.settings.GROQ_DAILY_REQUEST_LIMIT,
            )
            return False

        return True

    def record_usage(self, user_or_ip: str, tokens_used: int) -> None:
        """Record successful AI inference request and token consumption."""
        today = self._today_key()
        self._user_daily_requests[today][user_or_ip] += 1
        self._global_daily_tokens[today] += max(0, tokens_used)
        logger.info(
            "AI Usage recorded for '%s': +%s tokens. Total today: %s tokens.",
            user_or_ip,
            tokens_used,
            self._global_daily_tokens[today],
        )

    def get_user_usage(self, user_or_ip: str) -> dict[str, int]:
        """Return today's usage statistics for caller."""
        today = self._today_key()
        return {
            "requests_today": self._user_daily_requests[today][user_or_ip],
            "max_requests_daily": self.settings.GROQ_DAILY_REQUEST_LIMIT,
            "tokens_consumed_global_today": self._global_daily_tokens[today],
            "max_tokens_global_daily": self.settings.GROQ_DAILY_TOKEN_BUDGET,
        }

    def clear(self) -> None:
        """Reset usage metrics (useful in unit tests)."""
        self._user_daily_requests.clear()
        self._global_daily_tokens.clear()

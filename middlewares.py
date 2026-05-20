"""
Rate limiting and throttling middleware.
Protects against spam and abuse.
"""

import logging
import time
from typing import Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update

from config import config

logger = logging.getLogger(__name__)


class RateLimiter:
    """Per-user rate limiting."""

    def __init__(
        self,
        rate: int,
        window: int,
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            rate: Max requests per window
            window: Time window in seconds
        """
        self.rate = rate
        self.window = window
        self.users: Dict[int, list] = {}

    def is_allowed(self, user_id: int) -> bool:
        """
        Check if user is allowed to make request.

        Args:
            user_id: Telegram user ID

        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()

        if user_id not in self.users:
            self.users[user_id] = []

        # Remove old requests outside window
        self.users[user_id] = [
            timestamp
            for timestamp in self.users[user_id]
            if now - timestamp < self.window
        ]

        # Check if under limit
        if len(self.users[user_id]) < self.rate:
            self.users[user_id].append(now)
            return True

        return False

    def get_reset_time(self, user_id: int) -> Optional[float]:
        """
        Get time until rate limit resets.

        Args:
            user_id: Telegram user ID

        Returns:
            Seconds until reset, or None if not limited
        """
        if user_id not in self.users or not self.users[user_id]:
            return None

        oldest = self.users[user_id][0]
        reset_time = oldest + self.window - time.time()

        return max(0, reset_time)


class ThrottleMiddleware(BaseMiddleware):
    """
    Middleware for rate limiting.
    
    Prevents:
    - Callback spam
    - Message spam
    - API abuse
    """

    def __init__(self) -> None:
        """Initialize middleware."""
        self.callback_limiter = RateLimiter(
            config.RATE_LIMIT_CALLBACKS,
            config.RATE_LIMIT_WINDOW,
        )
        self.message_limiter = RateLimiter(
            config.RATE_LIMIT_QUESTIONS,
            config.RATE_LIMIT_WINDOW,
        )

    async def __call__(
        self,
        handler: Callable,
        event: Update,
        data: dict,
    ):
        """Process middleware."""
        user_id = None

        # Get user ID from different update types
        if event.callback_query:
            user_id = event.callback_query.from_user.id
            limiter = self.callback_limiter
        elif event.message:
            user_id = event.message.from_user.id
            limiter = self.message_limiter
        else:
            # No user, pass through
            return await handler(event, data)

        # Check rate limit
        if not limiter.is_allowed(user_id):
            reset_time = limiter.get_reset_time(user_id)
            logger.warning(
                f"Rate limit exceeded for user {user_id}, "
                f"reset in {reset_time:.1f}s"
            )
            
            # Store rate limit info in data for handlers to access
            data["rate_limited"] = True
            data["reset_time"] = reset_time
            
            # For callbacks, answer with notification
            if event.callback_query:
                try:
                    await event.callback_query.answer(
                        f"⏱️ Please wait {int(reset_time) + 1} seconds",
                        show_alert=False,
                    )
                except Exception as e:
                    logger.error(f"Failed to answer callback query: {e}")
                return
            
            # For messages, continue to handler (handler should check rate_limited)
            data["rate_limited"] = True
            return await handler(event, data)

        # Not rate limited, continue
        return await handler(event, data)

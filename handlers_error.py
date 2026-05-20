"""
Global error handler middleware.
Handles all unexpected errors and Telegram API errors gracefully.
Prevents bot crashes and provides detailed logging.
"""

import logging
from typing import Callable

from aiogram import BaseMiddleware
from aiogram.types import Update, TelegramError

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Middleware for global error handling.
    
    Catches:
    - TelegramBadRequest (parsing errors)
    - TelegramRetryAfter (rate limits)
    - Network failures
    - Unexpected exceptions
    """

    async def __call__(
        self,
        handler: Callable,
        event: Update,
        data: dict,
    ):
        """Process middleware with error handling."""
        try:
            return await handler(event, data)
        except TelegramError as e:
            # Telegram API errors
            if "can't parse entities" in str(e).lower():
                logger.warning(f"Telegram parse error (likely bad Markdown): {e}")
                # Try to respond with plain text fallback
                if event.message:
                    try:
                        await event.message.answer(
                            "⚠️ Message formatting error. Please try again."
                        )
                    except Exception as fallback_error:
                        logger.exception(f"Fallback message failed: {fallback_error}")
            elif "retry_after" in str(e).lower():
                logger.warning(f"Telegram rate limit: {e}")
            else:
                logger.exception(f"Telegram API error: {e}")
            # Continue even on Telegram errors
            return
        except Exception as e:
            logger.exception(f"Unexpected error in handler: {e}")
            # Try to notify user if possible
            if event.message:
                try:
                    await event.message.answer(
                        "❌ An unexpected error occurred. Please try again later."
                    )
                except Exception:
                    pass
            return

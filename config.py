"""
Configuration module with Pydantic validation.
Handles all environment variables, constants, and configuration.
"""

from typing import Dict

from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Application configuration with validation."""

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_PAYMENT_PROVIDER_TOKEN: str = ""

    # OpenRouter API
    OPENROUTER_API_KEY: str
    OPENROUTER_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT: int = 60

    # Database
    DATABASE_PATH: str = "users.db"

    # Models
    AVAILABLE_MODELS: Dict[str, str] = {
        "gpt4o": "openai/gpt-4o",
        "gpt41": "openai/gpt-4.1-turbo-preview",
        "claude_sonnet": "anthropic/claude-3.5-sonnet",
        "free": "openai/gpt-oss-120b:free",
    }
    DEFAULT_MODEL: str = "free"

    # Payment
    STARS_PER_PACKAGE: Dict[str, int] = {
        "small": 10,
        "medium": 50,
        "large": 100,
    }
    QUESTIONS_PER_STAR: int = 10
    QUESTIONS_PER_PACKAGE: Dict[str, int] = {
        "small": 100,
        "medium": 500,
        "large": 1000,
    }

    # Telegram message limits
    MESSAGE_CHAR_LIMIT: int = 4096
    CAPTION_CHAR_LIMIT: int = 1024

    # Logging
    LOG_LEVEL: str = "INFO"

    # API Retry
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0

    # Rate limiting (per user)
    RATE_LIMIT_QUESTIONS: int = 10  # questions per minute
    RATE_LIMIT_CALLBACKS: int = 5  # callback clicks per second
    RATE_LIMIT_WINDOW: int = 60  # seconds

    # Typing action refresh
    TYPING_REFRESH_INTERVAL: int = 4  # seconds
    TYPING_MAX_DURATION: int = 120  # max seconds before timeout

    # Request timeout
    AI_REQUEST_TIMEOUT: int = 120  # seconds for AI requests

    # Input validation
    MAX_PROMPT_LENGTH: int = 4000
    MIN_PROMPT_LENGTH: int = 1

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def get_model_by_key(self, model_key: str) -> str:
        """
        Get model name by key.

        Args:
            model_key: Model identifier key

        Returns:
            Full model name from OpenRouter

        Raises:
            ValueError: If model key is invalid
        """
        if model_key not in self.AVAILABLE_MODELS:
            raise ValueError(
                f"Invalid model '{model_key}'. "
                f"Available: {', '.join(self.AVAILABLE_MODELS.keys())}"
            )
        return self.AVAILABLE_MODELS[model_key]

    def get_questions_for_package(self, package: str) -> int:
        """Get questions count for a package."""
        return self.QUESTIONS_PER_PACKAGE.get(package, 0)

    def get_stars_for_package(self, package: str) -> int:
        """Get stars count for a package."""
        return self.STARS_PER_PACKAGE.get(package, 0)


# Global config instance with validation
try:
    config = Config()
except Exception as e:
    raise RuntimeError(f"Failed to load configuration: {e}") from e


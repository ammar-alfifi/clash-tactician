import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    coc_api_token: str | None
    ai_key_encryption_key: str | None
    openrouter_api_key: str | None
    openrouter_model: str
    openrouter_fallback_models: tuple[str, ...]
    openrouter_base_url: str
    database_path: Path
    support_chat_id: int | None
    default_language: str
    war_reminder_interval_minutes: int

    @classmethod
    def from_environment(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is missing. Copy .env.example to .env and add a new token."
            )

        database_path = Path(os.getenv("DATABASE_PATH", "data/bot.sqlite3"))
        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path

        support_chat_value = os.getenv("SUPPORT_CHAT_ID", "").strip()
        try:
            support_chat_id = int(support_chat_value) if support_chat_value else None
        except ValueError as exc:
            raise ValueError("SUPPORT_CHAT_ID must be an integer Telegram chat ID.") from exc

        reminder_value = os.getenv("WAR_REMINDER_INTERVAL_MINUTES", "60").strip() or "60"
        try:
            war_reminder_interval_minutes = int(reminder_value)
        except ValueError as exc:
            raise ValueError("WAR_REMINDER_INTERVAL_MINUTES must be an integer.") from exc
        war_reminder_interval_minutes = max(5, min(war_reminder_interval_minutes, 24 * 60))

        openrouter_model = (
            os.getenv("OPENROUTER_MODEL", "stealth/space-bunny-alpha").strip()
            or "stealth/space-bunny-alpha"
        )
        openrouter_fallback_models = tuple(
            dict.fromkeys(
                model
                for candidate in os.getenv(
                    "OPENROUTER_FALLBACK_MODELS",
                    "google/gemma-4-31b-it:free,qwen/qwen3.8-27b:free",
                ).split(",")
                if (model := candidate.strip()) and model != openrouter_model
            )
        )

        return cls(
            telegram_bot_token=token,
            coc_api_token=os.getenv("COC_API_TOKEN", "").strip() or None,
            ai_key_encryption_key=os.getenv("AI_KEY_ENCRYPTION_KEY", "").strip() or None,
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip() or None,
            openrouter_model=openrouter_model,
            openrouter_fallback_models=openrouter_fallback_models,
            openrouter_base_url=os.getenv(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            ).strip().rstrip("/")
            or "https://openrouter.ai/api/v1",
            database_path=database_path,
            support_chat_id=support_chat_id,
            default_language=os.getenv("DEFAULT_LANGUAGE", "ar").strip() or "ar",
            war_reminder_interval_minutes=war_reminder_interval_minutes,
        )

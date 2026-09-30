"""Application settings.

All secrets come from environment variables (or a local ``.env`` file). The
variable names are kept stable so the existing cloud deployment keeps working
without any Render-side changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value.strip()) if value and value.strip() else default
    except ValueError:
        return default


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(value.strip()) if value and value.strip() else default
    except ValueError:
        return default


def _id_list(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    ids: list[int] = []
    for chunk in value.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk and chunk.lstrip("-").isdigit():
            ids.append(int(chunk))
    return tuple(ids)


def _model_list(value: str | None, default: str) -> tuple[str, ...]:
    raw = value if value is not None else default
    seen: list[str] = []
    for candidate in raw.split(","):
        model = candidate.strip()
        if model and model not in seen:
            seen.append(model)
    return tuple(seen)


@dataclass(frozen=True)
class Settings:
    # Telegram
    bot_token: str
    admin_ids: tuple[int, ...] = ()
    support_chat_id: int | None = None

    # Clash of Clans official API
    coc_api_token: str | None = None
    coc_base_url: str = "https://api.clashofclans.com/v1"
    coc_cache_seconds: int = 300
    coc_timeout_seconds: int = 20

    # AI providers
    ai_key_encryption_key: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str = "stealth/space-bunny-alpha"
    openrouter_fallback_models: tuple[str, ...] = ()
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    nvidia_api_key: str | None = None
    nvidia_model: str = "meta/llama-3.2-11b-vision-instruct"
    nvidia_fallback_models: tuple[str, ...] = ()
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_timeout_seconds: int = 180

    # Storage
    database_path: Path = PROJECT_ROOT / "data/bot.sqlite3"

    # Runtime
    default_language: str = "ar"
    war_reminder_interval_minutes: int = 60
    reminder_tick_seconds: int = 60
    ai_timeout_seconds: int = 120
    max_image_bytes: int = 8 * 1024 * 1024
    port: int | None = 8080

    # Diagnostics
    diag_token: str | None = None
    egress_interval_seconds: int = 300

    # Feature flags
    enable_background_jobs: bool = True
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_environment(cls) -> Settings:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is missing. Copy .env.example to .env and add a token."
            )

        raw_db = os.getenv("DATABASE_PATH", "data/bot.sqlite3").strip() or "data/bot.sqlite3"
        database_path = Path(raw_db)
        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path

        support_raw = os.getenv("SUPPORT_CHAT_ID", "").strip()
        support_chat_id: int | None = None
        if support_raw:
            try:
                support_chat_id = int(support_raw)
            except ValueError as exc:
                raise ValueError("SUPPORT_CHAT_ID must be an integer Telegram chat ID.") from exc

        model = os.getenv("OPENROUTER_MODEL", "").strip() or "stealth/space-bunny-alpha"
        fallbacks = tuple(
            candidate
            for candidate in _model_list(
                os.getenv("OPENROUTER_FALLBACK_MODELS"),
                "google/gemma-4-31b-it:free,qwen/qwen3.8-27b:free",
            )
            if candidate != model
        )

        nvidia_model = (
            os.getenv("NVIDIA_MODEL", "").strip() or "meta/llama-3.2-11b-vision-instruct"
        )
        nvidia_fallbacks = tuple(
            candidate
            for candidate in _model_list(
                os.getenv("NVIDIA_FALLBACK_MODELS"),
                "meta/muse-glimmer-30b,nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
            )
            if candidate != nvidia_model
        )

        port_raw = os.getenv("PORT", "8080").strip()
        port: int | None = None if not port_raw else _as_int(port_raw, 8080)

        return cls(
            bot_token=token,
            admin_ids=_id_list(os.getenv("ADMIN_IDS")),
            support_chat_id=support_chat_id,
            coc_api_token=os.getenv("COC_API_TOKEN", "").strip() or None,
            coc_base_url=(
                os.getenv("COC_BASE_URL", "https://api.clashofclans.com/v1").strip().rstrip("/")
                or "https://api.clashofclans.com/v1"
            ),
            coc_cache_seconds=max(30, _as_int(os.getenv("COC_CACHE_SECONDS"), 300)),
            coc_timeout_seconds=max(5, _as_int(os.getenv("COC_TIMEOUT_SECONDS"), 20)),
            ai_key_encryption_key=os.getenv("AI_KEY_ENCRYPTION_KEY", "").strip() or None,
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip() or None,
            openrouter_model=model,
            openrouter_fallback_models=fallbacks[:3],
            openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            .strip()
            .rstrip("/")
            or "https://openrouter.ai/api/v1",
            nvidia_api_key=os.getenv("NVIDIA_API_KEY", "").strip() or None,
            nvidia_model=nvidia_model,
            nvidia_fallback_models=nvidia_fallbacks[:3],
            nvidia_base_url=(
                os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
                .strip()
                .rstrip("/")
                or "https://integrate.api.nvidia.com/v1"
            ),
            nvidia_timeout_seconds=max(30, _as_int(os.getenv("NVIDIA_TIMEOUT_SECONDS"), 180)),
            database_path=database_path,
            default_language=os.getenv("DEFAULT_LANGUAGE", "ar").strip() or "ar",
            war_reminder_interval_minutes=max(
                5, min(_as_int(os.getenv("WAR_REMINDER_INTERVAL_MINUTES"), 60), 24 * 60)
            ),
            reminder_tick_seconds=max(30, _as_int(os.getenv("REMINDER_TICK_SECONDS"), 60)),
            ai_timeout_seconds=max(30, _as_int(os.getenv("AI_TIMEOUT_SECONDS"), 120)),
            max_image_bytes=max(1, _as_int(os.getenv("MAX_IMAGE_BYTES"), 8 * 1024 * 1024)),
            port=port,
            diag_token=os.getenv("DIAG_TOKEN", "").strip() or None,
            egress_interval_seconds=max(60, _as_int(os.getenv("EGRESS_INTERVAL_SECONDS"), 300)),
            enable_background_jobs=_as_bool(os.getenv("ENABLE_BACKGROUND_JOBS"), True),
            extra={
                key: value
                for key, value in os.environ.items()
                if key.startswith("CT_")
            },
        )

    @property
    def has_coc(self) -> bool:
        return bool(self.coc_api_token)

    @property
    def has_shared_ai(self) -> bool:
        return bool(self.nvidia_api_key or self.openrouter_api_key)

    def is_admin(self, telegram_id: int) -> bool:
        return telegram_id in self.admin_ids

"""Typed application errors.

Handlers translate these into friendly Arabic messages instead of leaking
stack traces to users.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for expected, user-facing errors."""

    def __init__(self, message: str = "", *, reason: str | None = None) -> None:
        super().__init__(message or reason or self.__class__.__name__)
        self.reason = reason or message


class ConfigurationError(AppError):
    """Raised when required configuration is missing or invalid."""


class CocError(AppError):
    """Base error for Clash of Clans API problems."""


class CocAuthError(CocError):
    """Invalid or IP-restricted developer token (HTTP 403)."""


class CocNotFound(CocError):
    """Requested player/clan/war does not exist (HTTP 404)."""


class CocUnavailable(CocError):
    """Upstream is down, throttled or timed out."""


class CocDisabled(CocError):
    """No CoC API token is configured."""


class AiError(AppError):
    """Base error for AI provider problems."""


class AiAuthError(AiError):
    """Provider rejected the API key."""


class AiUnavailable(AiError):
    """Provider is down, throttled or timed out."""


class AiUnsupported(AiError):
    """Selected model cannot handle the requested input (e.g. images)."""


class AiNotConfigured(AiError):
    """No personal key and no shared key are available."""


class PlanError(AppError):
    """The model returned a plan we could not parse or validate."""


class ImageError(AppError):
    """The supplied image is invalid or too large."""

"""Fernet-based encryption for user AI keys."""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import ConfigurationError

logger = logging.getLogger(__name__)


class KeyVault:
    """Encrypt and decrypt user API keys with a process-wide master key."""

    def __init__(self, master_key: str | None) -> None:
        self._fernet: Fernet | None = None
        if master_key:
            try:
                self._fernet = Fernet(master_key.encode())
            except (ValueError, TypeError) as exc:
                raise ConfigurationError(
                    "AI_KEY_ENCRYPTION_KEY is not a valid Fernet key."
                ) from exc

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()

    def encrypt(self, value: str) -> str:
        if not self._fernet:
            raise ConfigurationError(
                "AI_KEY_ENCRYPTION_KEY is missing; personal AI keys cannot be stored."
            )
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str | None:
        if not self._fernet:
            return None
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken:
            logger.warning("Stored AI key could not be decrypted (master key changed?)")
            return None

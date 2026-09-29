from cryptography.fernet import Fernet, InvalidToken

OPENAI_MODEL = "gpt-4.1-mini"
GEMINI_MODEL = "gemini-2.5-flash"
MODEL = OPENAI_MODEL


class AIProviderError(Exception):
    """A safe, user-facing AI provider failure."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class KeyVault:
    def __init__(self, encryption_key: str | None) -> None:
        if not encryption_key:
            raise ValueError("AI_KEY_ENCRYPTION_KEY is not configured")
        try:
            self._fernet = Fernet(encryption_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise ValueError("AI_KEY_ENCRYPTION_KEY must be a valid Fernet key") from exc

    def encrypt(self, api_key: str) -> str:
        return self._fernet.encrypt(api_key.encode("utf-8")).decode("ascii")

    def decrypt(self, encrypted_key: str) -> str:
        try:
            return self._fernet.decrypt(encrypted_key.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError) as exc:
            raise ValueError("Stored AI key cannot be decrypted") from exc

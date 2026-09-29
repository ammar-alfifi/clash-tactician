import pytest
from cryptography.fernet import Fernet

from app.ai import KeyVault


def test_key_vault_encrypts_and_decrypts_without_storing_plaintext():
    secret = "sk-test-user-secret-value"
    vault = KeyVault(Fernet.generate_key().decode())

    encrypted = vault.encrypt(secret)

    assert encrypted != secret
    assert secret not in encrypted
    assert vault.decrypt(encrypted) == secret


def test_key_vault_requires_a_valid_encryption_key():
    with pytest.raises(ValueError):
        KeyVault("not-a-fernet-key")

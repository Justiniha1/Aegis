import os
import pytest
from cryptography.fernet import Fernet

def _set_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("AEGIS_ENCRYPTION_KEY", key)
    return key

def test_encrypt_decrypt_roundtrip(monkeypatch):
    _set_key(monkeypatch)
    from dashboard_api.encryption import encrypt, decrypt
    plaintext = "postgresql://user:pass@host:5432/mydb"
    assert decrypt(encrypt(plaintext)) == plaintext

def test_encrypt_produces_different_ciphertext_each_time(monkeypatch):
    _set_key(monkeypatch)
    from dashboard_api.encryption import encrypt
    a = encrypt("same-string")
    b = encrypt("same-string")
    assert a != b  # Fernet uses random IV

def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("AEGIS_ENCRYPTION_KEY", raising=False)
    import importlib
    import dashboard_api.encryption as enc_mod
    importlib.reload(enc_mod)  # re-evaluate module-level code without the env var
    with pytest.raises(RuntimeError, match="AEGIS_ENCRYPTION_KEY"):
        from dashboard_api.encryption import encrypt
        encrypt("anything")

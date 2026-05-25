import os
from cryptography.fernet import Fernet

def _get_fernet() -> Fernet:
    key = os.environ.get("AEGIS_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "AEGIS_ENCRYPTION_KEY env var is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())

def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()

def decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()

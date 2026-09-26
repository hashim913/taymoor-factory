
from cryptography.fernet import Fernet, InvalidToken
from config import TOKEN_ENCRYPTION_KEY

def _fernet():
    if not TOKEN_ENCRYPTION_KEY:
        return None
    return Fernet(TOKEN_ENCRYPTION_KEY.encode())

def encrypt_token(token: str) -> str:
    f = _fernet()
    if not f:
        # V5 intentionally requires a key for new encrypted storage.
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is required.")
    return f.encrypt(token.encode()).decode()

def decrypt_token(value: str) -> str:
    f = _fernet()
    if not f:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is required.")
    try:
        return f.decrypt(value.encode()).decode()
    except InvalidToken:
        # Helps migrate legacy plaintext tokens only if explicitly used.
        return value

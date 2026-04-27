from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
import os

load_dotenv()

_key = os.getenv("ENCRYPTION_KEY")
if not _key:
    raise RuntimeError("ENCRYPTION_KEY is not set in environment. Add it to .env")

_cipher = Fernet(_key.encode() if isinstance(_key, str) else _key)


def encrypt_pii(text: str) -> str:
    if not text:
        return ""
    return _cipher.encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt_pii(encrypted_text: str) -> str:
    if not encrypted_text:
        return ""
    try:
        return _cipher.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        return ""

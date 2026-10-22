import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.low_level import Type

password_hasher = PasswordHasher(type=Type.ID)
# Hash pembanding untuk mengurangi perbedaan waktu akun yang tidak ditemukan.
dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))


def digest(value: str, pepper: str = "") -> str:
    return hmac.new(pepper.encode(), value.encode(), hashlib.sha256).hexdigest()


def new_key():
    return "CLP-" + secrets.token_hex(20).upper()


def normalize_key(value):
    return value.strip().upper()

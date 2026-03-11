"""
Authentication service — JWT token generation and verification.
Credentials stored as env vars (AUTH_EMAIL, AUTH_PASS_HASH, AUTH_PASS_SALT).
"""

import hashlib
import os
import time
from typing import Optional

import jwt
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production")
ALGORITHM = "HS256"
TOKEN_TTL = 60 * 60 * 24  # 24 hours

AUTH_EMAIL = os.getenv("AUTH_EMAIL", "")
AUTH_PASS_HASH = os.getenv("AUTH_PASS_HASH", "")
AUTH_PASS_SALT = os.getenv("AUTH_PASS_SALT", "")


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def verify_credentials(email: str, password: str) -> bool:
    if not AUTH_EMAIL or not AUTH_PASS_HASH or not AUTH_PASS_SALT:
        return False
    if email.lower().strip() != AUTH_EMAIL.lower().strip():
        return False
    return _hash_password(password, AUTH_PASS_SALT) == AUTH_PASS_HASH


def create_token(email: str) -> str:
    payload = {
        "sub": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

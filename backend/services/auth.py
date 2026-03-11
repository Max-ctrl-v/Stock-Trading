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

ALGORITHM = "HS256"
TOKEN_TTL = 60 * 60 * 24  # 24 hours


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def verify_credentials(email: str, password: str) -> bool:
    auth_email = os.environ.get("AUTH_EMAIL", "").strip()
    auth_hash = os.environ.get("AUTH_PASS_HASH", "").strip()
    auth_salt = os.environ.get("AUTH_PASS_SALT", "").strip()
    if not auth_email or not auth_hash or not auth_salt:
        return False
    if email.lower().strip() != auth_email.lower().strip():
        return False
    return _hash_password(password, auth_salt) == auth_hash


def create_token(email: str) -> str:
    secret = os.environ.get("JWT_SECRET", "change-me-in-production").strip()
    payload = {
        "sub": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    secret = os.environ.get("JWT_SECRET", "change-me-in-production").strip()
    try:
        return jwt.decode(token, secret, algorithms=[ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

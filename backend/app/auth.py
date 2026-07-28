"""Authentication — local users, bcrypt password hashing, JWT sessions.

Fit for an on-prem product (no external auth service); can later federate to
company SSO/AD. Passwords are stored only as bcrypt hashes. Sessions are stateless
JWTs signed with JWT_SECRET (from .env).
"""
from __future__ import annotations

import datetime as dt
import os

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import execute, query_one

JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGO = "HS256"
TOKEN_TTL_HOURS = 8
ROLES = ("viewer", "engineer", "supervisor", "administrator")

_bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_token(email: str, role: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": email,
        "role": role,
        "iat": now,
        "exp": now + dt.timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def authenticate(email: str, password: str) -> dict | None:
    row = query_one(
        "SELECT id, email, role, password_hash FROM users WHERE email = %s",
        (email.lower().strip(),),
    )
    if not row or not verify_password(password, row["password_hash"]):
        return None
    try:  # best-effort last-login stamp; never block login on it
        execute("UPDATE users SET last_login_at = now() WHERE id = %s", (row["id"],))
    except Exception:
        pass
    return {"id": row["id"], "email": row["email"], "role": row["role"]}


def require_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """FastAPI dependency: validates the Bearer JWT and returns the current user."""
    if cred is None:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(cred.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired — please sign in again")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid authentication token")
    user = query_one(
        "SELECT id, email, role FROM users WHERE email = %s", (payload.get("sub"),)
    )
    if not user:
        raise HTTPException(401, "User no longer exists")
    return user


def user_from_token(token: str) -> dict | None:
    """Validate a raw JWT (used for WebSocket auth, where headers are awkward)."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        return None
    return query_one("SELECT id, email, role FROM users WHERE email = %s", (payload.get("sub"),))


def require_role(*allowed: str):
    """Dependency factory for role-gated endpoints (scaffolded for later use)."""
    def _dep(user: dict = Depends(require_user)) -> dict:
        if user["role"] not in allowed:
            raise HTTPException(403, "Insufficient permissions for this action")
        return user
    return _dep

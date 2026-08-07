"""
Per-user authentication for the translation server.

Uses HMAC-SHA256 signed JWTs so the server does NOT need a token database to
validate tokens — only a shared AUTH_SECRET. Claims include:
  sub   : user id
  role  : 'user' | 'admin'
  quota : dict of per-user usage caps (see quotas.py)
  jti   : unique token id (for revocation)
  iat   / exp

The server FAILS CLOSED: if AUTH_SECRET is not set, no connection is accepted
and the /auth/token endpoint refuses to issue tokens.
"""
import os
import time
import uuid
import threading
import logging
from typing import Any, Dict, Optional, Tuple

import jwt
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("AuthEngine")

_AUTH_SECRET = os.getenv("AUTH_SECRET", "").strip()
_ISSUER = os.getenv("AUTH_ISSUER", "speech-translator").strip()
_ALGO = "HS256"
_DEFAULT_TTL_SECONDS = int(os.getenv("AUTH_MAX_TOKEN_TTL", "86400"))  # 24h default
_MIN_TTL = 60
_MAX_TTL = 60 * 60 * 24 * 30  # 30 days

# In-memory revocation set (token jti values). Resets on restart.
_revoked: set = set()
_revoked_lock = threading.Lock()


def is_auth_configured() -> bool:
    """Auth is only functional when AUTH_SECRET is set and not a placeholder."""
    return bool(_AUTH_SECRET) and _AUTH_SECRET not in ("", "your_auth_secret_here")


def create_token(
    user_id: str,
    role: str = "user",
    quota: Optional[Dict[str, Any]] = None,
    ttl_seconds: Optional[int] = None,
) -> str:
    """Issue a signed JWT for a user. Raises RuntimeError if auth is not configured."""
    if not is_auth_configured():
        raise RuntimeError(
            "Auth is not configured: set AUTH_SECRET in server/.env before issuing tokens."
        )
    if not user_id or not user_id.strip():
        raise ValueError("user_id must be a non-empty string.")

    ttl = ttl_seconds or _DEFAULT_TTL_SECONDS
    ttl = max(_MIN_TTL, min(int(ttl), _MAX_TTL))

    now = int(time.time())
    claims = {
        "sub": user_id.strip(),
        "role": role if role in ("user", "admin") else "user",
        "quota": quota or {},
        "jti": str(uuid.uuid4()),
        "iss": _ISSUER,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(claims, _AUTH_SECRET, algorithm=_ALGO)


def verify_token(token: str) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Validate a token. Returns (ok, claims, error_reason).
    Rejects bad signature, expired, wrong issuer, and revoked (jti) tokens.
    """
    if not is_auth_configured():
        return False, {}, "auth_not_configured"
    if not token:
        return False, {}, "missing_token"

    try:
        claims = jwt.decode(
            token,
            _AUTH_SECRET,
            algorithms=[_ALGO],
            issuer=_ISSUER,
            options={"require": ["sub", "exp", "iat", "jti"]},
        )
    except jwt.ExpiredSignatureError:
        return False, {}, "token_expired"
    except jwt.InvalidIssuerError:
        return False, {}, "invalid_issuer"
    except jwt.InvalidTokenError as e:
        return False, {}, f"invalid_token: {e}"

    with _revoked_lock:
        if claims.get("jti") in _revoked:
            return False, {}, "token_revoked"

    return True, claims, None


def revoke_token(token: str) -> bool:
    """Revoke a token by its jti. Returns True if a valid token was revoked."""
    ok, claims, _ = verify_token(token)
    if not ok:
        return False
    with _revoked_lock:
        _revoked.add(claims["jti"])
    logger.info(f"Revoked token jti={claims['jti']} for user {claims['sub']}")
    return True

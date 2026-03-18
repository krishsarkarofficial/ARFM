"""
ARFM Backend — Security Utilities
Encrypted cookie management for zero-knowledge stateless sessions.
"""

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, HTTPException, status
from google.oauth2.credentials import Credentials

from config import get_settings

COOKIE_NAME = "arfm_session"
MAX_AGE_SECONDS = 86400  # 24 hours


def _get_serializer() -> URLSafeTimedSerializer:
    """Create a timed serializer using the app secret key."""
    settings = get_settings()
    return URLSafeTimedSerializer(settings.SECRET_KEY)


def encrypt_tokens(tokens: dict) -> str:
    """
    Sign and serialize an OAuth token payload into a URL-safe string.
    This string is stored in an HTTP-only cookie — no DB required.
    """
    serializer = _get_serializer()
    return serializer.dumps(tokens)


def decrypt_tokens(cookie_value: str) -> dict:
    """
    Verify the signature and deserialize the cookie back to a token dict.
    Raises HTTPException if the cookie is expired or tampered with.
    """
    serializer = _get_serializer()
    try:
        return serializer.loads(cookie_value, max_age=MAX_AGE_SECONDS)
    except SignatureExpired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
        )
    except BadSignature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session. Please log in again.",
        )


def set_session_cookie(response, encrypted_value: str):
    """Set the session cookie with environment-appropriate security flags."""
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=encrypted_value,
        httponly=True,
        secure=settings.is_production,
        samesite="none" if settings.is_production else "lax",
        max_age=MAX_AGE_SECONDS,
        path="/",
    )


def get_credentials(request: Request) -> Credentials:
    """
    FastAPI dependency — extracts Google OAuth credentials from the
    encrypted session cookie. Returns a ready-to-use Credentials object.
    """
    cookie_value = request.cookies.get(COOKIE_NAME)
    if not cookie_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please connect your Google account.",
        )

    token_data = decrypt_tokens(cookie_value)
    settings = get_settings()

    return Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=settings.GOOGLE_SCOPES,
    )

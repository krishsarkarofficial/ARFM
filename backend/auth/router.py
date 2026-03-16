"""
ARFM Backend — Auth Router
Google OAuth 2.0 login flow with encrypted cookie sessions.
"""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

from config import get_settings
from auth.security import encrypt_tokens, COOKIE_NAME

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _build_flow(settings) -> Flow:
    """Construct a Google OAuth2 Flow from app settings."""
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.OAUTH_REDIRECT_URI],
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=settings.GOOGLE_SCOPES,
        redirect_uri=settings.OAUTH_REDIRECT_URI,
    )
    return flow


@router.get("/login")
async def login():
    """
    Generate a Google OAuth2 authorization URL.
    The frontend redirects the user's browser to this URL.
    """
    settings = get_settings()
    flow = _build_flow(settings)

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    return {"auth_url": auth_url}


@router.get("/callback")
async def callback(request: Request, code: str):
    """
    Handle the OAuth2 callback from Google.
    Exchanges the authorization code for tokens, encrypts them into
    an HTTP-only cookie, and redirects to the frontend dashboard.
    """
    settings = get_settings()
    flow = _build_flow(settings)

    # Exchange the authorization code for credentials
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Serialize token data for cookie storage
    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes) if credentials.scopes else [],
    }

    encrypted = encrypt_tokens(token_data)

    # Redirect to frontend with the session cookie set
    response = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/dashboard.html",
        status_code=302,
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=encrypted,
        httponly=True,
        secure=False,  # Set to True in production (HTTPS)
        samesite="lax",
        max_age=86400,  # 24 hours
        path="/",
    )

    return response


@router.get("/logout")
async def logout():
    """Clear the session cookie and redirect to the frontend."""
    settings = get_settings()
    response = RedirectResponse(
        url=settings.FRONTEND_URL,
        status_code=302,
    )
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return response


@router.get("/status")
async def auth_status(request: Request):
    """Check if the user has a valid session (non-expired cookie)."""
    cookie_value = request.cookies.get(COOKIE_NAME)
    if not cookie_value:
        return {"authenticated": False}

    try:
        from auth.security import decrypt_tokens
        decrypt_tokens(cookie_value)
        return {"authenticated": True}
    except Exception:
        return {"authenticated": False}

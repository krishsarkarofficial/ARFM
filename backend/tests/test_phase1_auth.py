"""
ARFM Backend — Phase 1 Tests
Tests for Core Scaffolding & Stateless Security.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment variables BEFORE importing app modules
os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
os.environ["FRONTEND_URL"] = "http://localhost:5173"
os.environ["SECRET_KEY"] = "test-secret-key-for-signing"

from fastapi.testclient import TestClient
from config import Settings, get_settings
from auth.security import encrypt_tokens, decrypt_tokens, COOKIE_NAME


# ── Override settings for tests ─────────────────────────────────
def get_test_settings():
    return Settings(
        GOOGLE_CLIENT_ID="test-client-id",
        GOOGLE_CLIENT_SECRET="test-client-secret",
        FRONTEND_URL="http://localhost:5173",
        SECRET_KEY="test-secret-key-for-signing",
    )


# Clear the lru_cache to use test settings
get_settings.cache_clear()


from main import app

app.dependency_overrides[get_settings] = get_test_settings

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════
#  1. CORS Middleware
# ═══════════════════════════════════════════════════════════════

class TestCORS:
    def test_cors_headers_present(self):
        """CORS should allow the configured frontend origin."""
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_cors_credentials_allowed(self):
        """CORS should allow credentials (cookies)."""
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_rejects_unknown_origin(self):
        """CORS should NOT set allow-origin for unknown origins."""
        response = client.options(
            "/",
            headers={
                "Origin": "http://evil-site.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") != "http://evil-site.com"


# ═══════════════════════════════════════════════════════════════
#  2. Root & Health Endpoints
# ═══════════════════════════════════════════════════════════════

class TestRootEndpoints:
    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "ARFM Backend"
        assert data["status"] == "operational"

    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_api_ping(self):
        response = client.get("/api/ping")
        assert response.status_code == 200
        assert response.json()["message"] == "pong"


# ═══════════════════════════════════════════════════════════════
#  3. Cookie Encryption Round-Trip
# ═══════════════════════════════════════════════════════════════

class TestCookieSecurity:
    def test_encrypt_decrypt_roundtrip(self):
        """Tokens encrypted via itsdangerous should decrypt back to the same data."""
        original = {
            "token": "ya29.test-access-token",
            "refresh_token": "1//test-refresh-token",
            "scopes": ["openid", "email"],
        }
        encrypted = encrypt_tokens(original)
        decrypted = decrypt_tokens(encrypted)

        assert decrypted["token"] == original["token"]
        assert decrypted["refresh_token"] == original["refresh_token"]
        assert decrypted["scopes"] == original["scopes"]

    def test_encrypted_value_is_opaque(self):
        """The encrypted cookie should not contain plaintext tokens."""
        original = {"token": "ya29.super-secret"}
        encrypted = encrypt_tokens(original)
        assert "ya29.super-secret" not in encrypted

    def test_tampered_cookie_raises(self):
        """A tampered cookie should raise an HTTP 401 error."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decrypt_tokens("tampered.invalid.cookie")
        assert exc_info.value.status_code == 401


# ═══════════════════════════════════════════════════════════════
#  4. Auth Login Endpoint
# ═══════════════════════════════════════════════════════════════

class TestAuthLogin:
    @patch("auth.router._build_flow")
    def test_login_returns_auth_url(self, mock_build_flow):
        """GET /auth/login should return a Google OAuth authorization URL."""
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/auth?client_id=test&scope=openid+email",
            "state_token",
        )
        mock_build_flow.return_value = mock_flow

        response = client.get("/auth/login")
        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "accounts.google.com" in data["auth_url"]

    @patch("auth.router._build_flow")
    def test_login_url_contains_correct_scopes(self, mock_build_flow):
        """The auth URL should request the correct Google API scopes."""
        mock_flow = MagicMock()
        auth_url = (
            "https://accounts.google.com/o/oauth2/auth?"
            "scope=openid+email+"
            "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.readonly+"
            "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.send"
        )
        mock_flow.authorization_url.return_value = (auth_url, "state")
        mock_build_flow.return_value = mock_flow

        response = client.get("/auth/login")
        url = response.json()["auth_url"]
        assert "gmail.readonly" in url
        assert "gmail.send" in url


# ═══════════════════════════════════════════════════════════════
#  5. Auth Callback Endpoint
# ═══════════════════════════════════════════════════════════════

class TestAuthCallback:
    @patch("auth.router._build_flow")
    def test_callback_sets_httponly_cookie(self, mock_build_flow):
        """GET /auth/callback should exchange the code and set an HTTP-only cookie."""
        mock_credentials = MagicMock()
        mock_credentials.token = "ya29.test-access-token"
        mock_credentials.refresh_token = "1//test-refresh-token"
        mock_credentials.token_uri = "https://oauth2.googleapis.com/token"
        mock_credentials.client_id = "test-client-id"
        mock_credentials.client_secret = "test-client-secret"
        mock_credentials.scopes = {"openid", "email"}

        mock_flow = MagicMock()
        mock_flow.credentials = mock_credentials
        mock_build_flow.return_value = mock_flow

        response = client.get(
            "/auth/callback?code=test-auth-code",
            follow_redirects=False,
        )

        # Should redirect to dashboard
        assert response.status_code == 302
        assert "dashboard.html" in response.headers["location"]

        # Should set the session cookie
        set_cookie = response.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie
        assert "httponly" in set_cookie.lower()

    @patch("auth.router._build_flow")
    def test_callback_cookie_is_decryptable(self, mock_build_flow):
        """The cookie set by callback should be decryptable to valid token data."""
        mock_credentials = MagicMock()
        mock_credentials.token = "ya29.real-token"
        mock_credentials.refresh_token = "1//real-refresh"
        mock_credentials.token_uri = "https://oauth2.googleapis.com/token"
        mock_credentials.client_id = "test-client-id"
        mock_credentials.client_secret = "test-client-secret"
        mock_credentials.scopes = {"openid", "email"}

        mock_flow = MagicMock()
        mock_flow.credentials = mock_credentials
        mock_build_flow.return_value = mock_flow

        response = client.get(
            "/auth/callback?code=test-code",
            follow_redirects=False,
        )

        # Extract cookie value and decrypt
        cookie_value = response.cookies.get(COOKIE_NAME)
        assert cookie_value is not None

        decrypted = decrypt_tokens(cookie_value)
        assert decrypted["token"] == "ya29.real-token"
        assert decrypted["refresh_token"] == "1//real-refresh"


# ═══════════════════════════════════════════════════════════════
#  6. Auth Status & Logout
# ═══════════════════════════════════════════════════════════════

class TestAuthStatus:
    def test_status_unauthenticated(self):
        """GET /auth/status without a cookie should return authenticated=false."""
        # Use a fresh client to ensure no cookies from previous tests
        fresh_client = TestClient(app)
        response = fresh_client.get("/auth/status")
        assert response.status_code == 200
        assert response.json()["authenticated"] is False

    @patch("auth.router._build_flow")
    def test_status_authenticated(self, mock_build_flow):
        """After login, /auth/status should return authenticated=true."""
        mock_credentials = MagicMock()
        mock_credentials.token = "ya29.token"
        mock_credentials.refresh_token = "1//refresh"
        mock_credentials.token_uri = "https://oauth2.googleapis.com/token"
        mock_credentials.client_id = "test-client-id"
        mock_credentials.client_secret = "test-client-secret"
        mock_credentials.scopes = {"openid"}

        mock_flow = MagicMock()
        mock_flow.credentials = mock_credentials
        mock_build_flow.return_value = mock_flow

        # Simulate login
        cb_response = client.get(
            "/auth/callback?code=code",
            follow_redirects=False,
        )
        cookie_value = cb_response.cookies.get(COOKIE_NAME)

        # Check status with cookie
        response = client.get(
            "/auth/status",
            cookies={COOKIE_NAME: cookie_value},
        )
        assert response.json()["authenticated"] is True

    def test_logout_clears_cookie(self):
        """GET /auth/logout should redirect and clear the session cookie."""
        response = client.get("/auth/logout", follow_redirects=False)
        assert response.status_code == 302
        set_cookie = response.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie

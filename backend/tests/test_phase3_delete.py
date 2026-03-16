"""
ARFM Backend — Phase 3 Tests
Tests for the Deletion Engine (legal templates + email dispatch).
"""

import os
import sys
import base64
import pytest
from unittest.mock import patch, MagicMock
from email import message_from_bytes

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment variables
os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
os.environ["FRONTEND_URL"] = "http://localhost:5173"
os.environ["SECRET_KEY"] = "test-secret-key-for-signing"

from services.legal import DeletionTemplateEngine
from services.email_sender import build_rfc2822_message
from config import get_settings

get_settings.cache_clear()

from fastapi.testclient import TestClient
from main import app
from auth.security import encrypt_tokens, COOKIE_NAME


# ═══════════════════════════════════════════════════════════════
#  1. GDPR Template
# ═══════════════════════════════════════════════════════════════

class TestGDPRTemplate:
    def test_gdpr_populates_company(self):
        result = DeletionTemplateEngine.populate("Facebook", "user@gmail.com", "gdpr")
        assert "Facebook" in result["body"]

    def test_gdpr_populates_email(self):
        result = DeletionTemplateEngine.populate("Facebook", "test@example.com", "gdpr")
        assert "test@example.com" in result["body"]

    def test_gdpr_subject_contains_article_17(self):
        result = DeletionTemplateEngine.populate("Facebook", "user@gmail.com", "gdpr")
        assert "Article 17" in result["subject"]

    def test_gdpr_body_mentions_gdpr(self):
        result = DeletionTemplateEngine.populate("Facebook", "user@gmail.com", "gdpr")
        assert "GDPR" in result["body"]

    def test_gdpr_body_mentions_one_month(self):
        result = DeletionTemplateEngine.populate("Facebook", "user@gmail.com", "gdpr")
        assert "one calendar month" in result["body"]


# ═══════════════════════════════════════════════════════════════
#  2. CCPA Template
# ═══════════════════════════════════════════════════════════════

class TestCCPATemplate:
    def test_ccpa_populates_company(self):
        result = DeletionTemplateEngine.populate("Amazon", "user@gmail.com", "ccpa")
        assert "Amazon" in result["body"]

    def test_ccpa_populates_email(self):
        result = DeletionTemplateEngine.populate("Amazon", "test@example.com", "ccpa")
        assert "test@example.com" in result["body"]

    def test_ccpa_subject_contains_section(self):
        result = DeletionTemplateEngine.populate("Amazon", "user@gmail.com", "ccpa")
        assert "1798.105" in result["subject"]

    def test_ccpa_body_mentions_ccpa(self):
        result = DeletionTemplateEngine.populate("Amazon", "user@gmail.com", "ccpa")
        assert "CCPA" in result["body"]

    def test_ccpa_body_mentions_45_days(self):
        result = DeletionTemplateEngine.populate("Amazon", "user@gmail.com", "ccpa")
        assert "45 calendar days" in result["body"]


# ═══════════════════════════════════════════════════════════════
#  3. Template Edge Cases
# ═══════════════════════════════════════════════════════════════

class TestTemplateEdgeCases:
    def test_unsupported_jurisdiction_raises(self):
        with pytest.raises(ValueError, match="Unsupported jurisdiction"):
            DeletionTemplateEngine.populate("Facebook", "user@gmail.com", "hipaa")

    def test_case_insensitive_jurisdiction(self):
        """Jurisdiction should be case-insensitive."""
        result = DeletionTemplateEngine.populate("Facebook", "user@gmail.com", "GDPR")
        assert "Article 17" in result["subject"]

    def test_supported_jurisdictions(self):
        supported = DeletionTemplateEngine.get_supported_jurisdictions()
        assert "gdpr" in supported
        assert "ccpa" in supported

    def test_result_has_subject_and_body(self):
        result = DeletionTemplateEngine.populate("Test Co", "a@b.com", "gdpr")
        assert "subject" in result
        assert "body" in result
        assert len(result["body"]) > 100  # Non-trivial content


# ═══════════════════════════════════════════════════════════════
#  4. RFC 2822 Message Construction
# ═══════════════════════════════════════════════════════════════

class TestRFC2822Message:
    def test_message_is_base64_encoded(self):
        raw = build_rfc2822_message(
            to="dpo@facebook.com",
            from_email="user@gmail.com",
            subject="GDPR Deletion Request",
            body="Please delete my data.",
        )
        # Should be valid base64
        decoded = base64.urlsafe_b64decode(raw + "==")
        assert b"dpo@facebook.com" in decoded

    def test_message_has_correct_headers(self):
        raw = build_rfc2822_message(
            to="privacy@amazon.com",
            from_email="test@gmail.com",
            subject="CCPA Deletion Request",
            body="Delete my data please.",
        )
        decoded = base64.urlsafe_b64decode(raw + "==")
        msg = message_from_bytes(decoded)

        assert msg["to"] == "privacy@amazon.com"
        assert msg["from"] == "test@gmail.com"
        assert msg["subject"] == "CCPA Deletion Request"

    def test_message_body_content(self):
        body_text = "This is the deletion request body."
        raw = build_rfc2822_message(
            to="a@b.com",
            from_email="c@d.com",
            subject="Test",
            body=body_text,
        )
        decoded = base64.urlsafe_b64decode(raw + "==")
        msg = message_from_bytes(decoded)
        assert body_text in msg.get_payload()


# ═══════════════════════════════════════════════════════════════
#  5. POST /api/send-request Endpoint (Mocked Gmail)
# ═══════════════════════════════════════════════════════════════

class TestSendRequestEndpoint:
    def _get_auth_cookie(self):
        token_data = {
            "token": "ya29.test",
            "refresh_token": "1//test",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "scopes": ["openid", "email"],
        }
        return encrypt_tokens(token_data)

    def test_send_request_requires_auth(self):
        """POST /api/send-request without a cookie should return 401."""
        fresh_client = TestClient(app)
        response = fresh_client.post("/api/send-request", json={
            "company": "Facebook",
            "to_email": "dpo@facebook.com",
            "jurisdiction": "gdpr",
        })
        assert response.status_code == 401

    @patch("api.router.send_via_gmail")
    @patch("api.router.build_rfc2822_message")
    @patch("googleapiclient.discovery.build")
    def test_send_request_with_custom_body(self, mock_build, mock_msg, mock_send):
        """POST /api/send-request with a custom body should use it."""
        # Mock oauth2 service for userinfo
        mock_oauth_service = MagicMock()
        mock_oauth_service.userinfo().get().execute.return_value = {"email": "user@gmail.com"}
        mock_build.return_value = mock_oauth_service

        mock_msg.return_value = "base64_encoded_raw"
        mock_send.return_value = {"id": "msg123", "threadId": "thread456"}

        cookie = self._get_auth_cookie()
        fresh_client = TestClient(app)
        fresh_client.cookies.set(COOKIE_NAME, cookie)
        response = fresh_client.post("/api/send-request", json={
            "company": "Facebook",
            "to_email": "dpo@facebook.com",
            "jurisdiction": "gdpr",
            "body": "Custom deletion request text.",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        assert data["company"] == "Facebook"

    @patch("api.router.send_via_gmail")
    @patch("googleapiclient.discovery.build")
    def test_send_request_auto_generates_body(self, mock_build, mock_send):
        """POST /api/send-request without a body should auto-generate from template."""
        mock_oauth_service = MagicMock()
        mock_oauth_service.userinfo().get().execute.return_value = {"email": "user@gmail.com"}
        mock_build.return_value = mock_oauth_service

        mock_send.return_value = {"id": "msg789", "threadId": "thread012"}

        cookie = self._get_auth_cookie()
        fresh_client = TestClient(app)
        fresh_client.cookies.set(COOKIE_NAME, cookie)
        response = fresh_client.post("/api/send-request", json={
            "company": "Amazon",
            "to_email": "privacy@amazon.com",
            "jurisdiction": "ccpa",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        assert data["jurisdiction"] == "ccpa"

    def test_send_request_invalid_jurisdiction(self):
        """Unsupported jurisdiction should return 400 (when no custom body)."""
        cookie = self._get_auth_cookie()
        fresh_client = TestClient(app)
        fresh_client.cookies.set(COOKIE_NAME, cookie)

        # Mock the Google APIs to avoid real API calls
        with patch("googleapiclient.discovery.build") as mock_build:
            mock_oauth = MagicMock()
            mock_oauth.userinfo().get().execute.return_value = {"email": "u@g.com"}
            mock_build.return_value = mock_oauth

            response = fresh_client.post("/api/send-request", json={
                "company": "Test",
                "to_email": "test@test.com",
                "jurisdiction": "hipaa",
            })
            assert response.status_code == 400
            assert "Unsupported jurisdiction" in response.json()["detail"]

    @patch("api.router.send_via_gmail")
    @patch("googleapiclient.discovery.build")
    def test_send_request_returns_correct_shape(self, mock_build, mock_send):
        """Response should include status, message_id, thread_id, to, company, jurisdiction."""
        mock_oauth = MagicMock()
        mock_oauth.userinfo().get().execute.return_value = {"email": "u@g.com"}
        mock_build.return_value = mock_oauth
        mock_send.return_value = {"id": "abc", "threadId": "def"}

        cookie = self._get_auth_cookie()
        fresh_client = TestClient(app)
        fresh_client.cookies.set(COOKIE_NAME, cookie)
        response = fresh_client.post("/api/send-request", json={
            "company": "GitHub",
            "to_email": "privacy@github.com",
            "jurisdiction": "gdpr",
            "body": "Delete my data.",
        })

        data = response.json()
        expected_fields = ["status", "message_id", "thread_id", "to", "company", "jurisdiction"]
        for field in expected_fields:
            assert field in data, f"Missing field '{field}'"

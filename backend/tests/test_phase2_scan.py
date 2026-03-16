"""
ARFM Backend — Phase 2 Tests
Tests for the Scanning Pipeline (Regex Engine).
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment variables
os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
os.environ["FRONTEND_URL"] = "http://localhost:5173"
os.environ["SECRET_KEY"] = "test-secret-key-for-signing"

from services.scanner import RegexScanner, BaseScanner, load_company_map
from config import get_settings

get_settings.cache_clear()

from fastapi.testclient import TestClient
from main import app
from auth.security import encrypt_tokens, COOKIE_NAME

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════
#  1. Regex Pattern Matching
# ═══════════════════════════════════════════════════════════════

class TestRegexPatterns:
    scanner = RegexScanner()

    POSITIVE_SUBJECTS = [
        "Welcome to Spotify!",
        "Verify your email address",
        "Confirm your account registration",
        "Account created successfully",
        "Thanks for signing up!",
        "Registration complete - get started",
        "Activate your account now",
        "You've registered for GitHub",
        "Your new account is ready",
        "Getting started with Notion",
        "WELCOME TO DISCORD",
        "Please verify your email",
        "Thank for signing up to our service",
    ]

    NEGATIVE_SUBJECTS = [
        "Your order has been shipped",
        "Monthly newsletter - March 2026",
        "Invoice #12345 attached",
        "Meeting at 3pm tomorrow",
        "RE: Project update",
        "50% off sale this weekend!",
        "Password reset request",
    ]

    def test_positive_matches(self):
        """All signup-related subjects should be detected."""
        for subject in self.POSITIVE_SUBJECTS:
            assert self.scanner._matches_signup(subject), f"Failed to match: {subject}"

    def test_negative_matches(self):
        """Non-signup subjects should NOT be detected."""
        for subject in self.NEGATIVE_SUBJECTS:
            assert not self.scanner._matches_signup(subject), f"False positive: {subject}"

    def test_case_insensitive(self):
        """Pattern matching should be case-insensitive."""
        assert self.scanner._matches_signup("WELCOME TO GITHUB")
        assert self.scanner._matches_signup("welcome to github")
        assert self.scanner._matches_signup("Welcome To GitHub")


# ═══════════════════════════════════════════════════════════════
#  2. Domain Extraction
# ═══════════════════════════════════════════════════════════════

class TestDomainExtraction:
    scanner = RegexScanner()

    def test_extract_simple_email(self):
        assert self.scanner._extract_domain("noreply@github.com") == "github.com"

    def test_extract_from_display_name(self):
        assert self.scanner._extract_domain("GitHub <noreply@github.com>") == "github.com"

    def test_extract_subdomain(self):
        result = self.scanner._extract_domain("no-reply@accounts.google.com")
        assert result == "accounts.google.com"

    def test_extract_returns_none_for_invalid(self):
        assert self.scanner._extract_domain("not-an-email") is None

    def test_extract_lowercase(self):
        assert self.scanner._extract_domain("Team@GitHub.Com") == "github.com"


# ═══════════════════════════════════════════════════════════════
#  3. Company Map
# ═══════════════════════════════════════════════════════════════

class TestCompanyMap:
    def test_company_map_loads(self):
        """The company_map.json should load as a valid dict."""
        data = load_company_map()
        assert isinstance(data, dict)
        assert len(data) > 40  # We have 50+ entries

    def test_company_map_has_required_fields(self):
        """Each entry should have name, category, risk, and deletion_email."""
        data = load_company_map()
        for domain, info in data.items():
            assert "name" in info, f"Missing 'name' for {domain}"
            assert "category" in info, f"Missing 'category' for {domain}"
            assert "risk" in info, f"Missing 'risk' for {domain}"
            assert "deletion_email" in info, f"Missing 'deletion_email' for {domain}"

    def test_risk_values_in_range(self):
        """Risk values should be between 0 and 1."""
        data = load_company_map()
        for domain, info in data.items():
            assert 0 <= info["risk"] <= 1, f"Invalid risk for {domain}: {info['risk']}"

    def test_known_domains_exist(self):
        """Key domains from the frontend ai-engine.js should be present."""
        data = load_company_map()
        expected_domains = ["facebook.com", "github.com", "spotify.com", "amazon.com", "paypal.com"]
        for domain in expected_domains:
            assert domain in data, f"Missing expected domain: {domain}"


# ═══════════════════════════════════════════════════════════════
#  4. Full Scan Pipeline
# ═══════════════════════════════════════════════════════════════

class TestFullScanPipeline:
    def test_scan_detects_accounts(self):
        """The scanner should detect accounts from signup-like messages."""
        scanner = RegexScanner()
        messages = [
            {"subject": "Welcome to Spotify!", "from": "no-reply@spotify.com", "date": "2026-01-01"},
            {"subject": "Your order shipped", "from": "orders@amazon.com", "date": "2026-01-02"},
            {"subject": "Verify your email", "from": "noreply@github.com", "date": "2026-01-03"},
            {"subject": "Meeting tomorrow", "from": "boss@company.com", "date": "2026-01-04"},
            {"subject": "Account created", "from": "hello@discord.com", "date": "2026-01-05"},
        ]
        results = scanner.scan(messages)
        domains = [r["domain"] for r in results]

        assert "spotify.com" in domains
        assert "github.com" in domains
        assert "discord.com" in domains
        assert len(results) == 3

    def test_scan_deduplicates_domains(self):
        """Multiple emails from the same domain should produce only one result."""
        scanner = RegexScanner()
        messages = [
            {"subject": "Welcome to GitHub!", "from": "noreply@github.com", "date": "2026-01-01"},
            {"subject": "Verify your GitHub email", "from": "noreply@github.com", "date": "2026-01-02"},
        ]
        results = scanner.scan(messages)
        assert len(results) == 1

    def test_scan_maps_company_info(self):
        """Detected accounts should include company metadata from the map."""
        scanner = RegexScanner()
        messages = [
            {"subject": "Welcome to Spotify!", "from": "no-reply@spotify.com", "date": "2026-01-01"},
        ]
        results = scanner.scan(messages)
        assert len(results) == 1
        assert results[0]["company"] == "Spotify"
        assert results[0]["category"] == "media"
        assert results[0]["deletion_email"] == "privacy@spotify.com"

    def test_scan_handles_unknown_domains(self):
        """Unknown domains should still be detected with fallback values."""
        scanner = RegexScanner()
        messages = [
            {"subject": "Welcome to MyApp!", "from": "hello@unknown-service.io", "date": "2026-01-01"},
        ]
        results = scanner.scan(messages)
        assert len(results) == 1
        assert results[0]["domain"] == "unknown-service.io"
        assert results[0]["category"] == "other"


# ═══════════════════════════════════════════════════════════════
#  5. BaseScanner Interface
# ═══════════════════════════════════════════════════════════════

class TestBaseScannerInterface:
    def test_cannot_instantiate_abstract(self):
        """BaseScanner should not be directly instantiable."""
        with pytest.raises(TypeError):
            BaseScanner()

    def test_custom_scanner_works(self):
        """A custom scanner implementing BaseScanner should work."""
        class AlwaysDetectScanner(BaseScanner):
            def scan(self, messages):
                return [{"domain": "test.com", "company": "Test"}]

        scanner = AlwaysDetectScanner()
        result = scanner.scan([])
        assert len(result) == 1
        assert result[0]["domain"] == "test.com"


# ═══════════════════════════════════════════════════════════════
#  6. GET /api/scan Endpoint (Mocked Gmail)
# ═══════════════════════════════════════════════════════════════

class TestScanEndpoint:
    def _get_auth_cookie(self):
        """Create a valid auth cookie for testing."""
        token_data = {
            "token": "ya29.test",
            "refresh_token": "1//test",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "scopes": ["openid", "email"],
        }
        return encrypt_tokens(token_data)

    @patch("api.router.GmailFetcher")
    def test_scan_endpoint_returns_accounts(self, MockFetcher):
        """GET /api/scan should return detected accounts."""
        mock_instance = MagicMock()
        mock_instance.fetch_headers.return_value = [
            {"subject": "Welcome to Spotify!", "from": "no-reply@spotify.com", "date": "2026-01-01"},
            {"subject": "Verify your email", "from": "noreply@github.com", "date": "2026-01-03"},
        ]
        MockFetcher.return_value = mock_instance

        cookie = self._get_auth_cookie()
        fresh_client = TestClient(app)
        fresh_client.cookies.set(COOKIE_NAME, cookie)
        response = fresh_client.get("/api/scan")

        assert response.status_code == 200
        data = response.json()
        assert data["total_emails_scanned"] == 2
        assert data["accounts_found"] == 2
        assert len(data["accounts"]) == 2

    def test_scan_endpoint_requires_auth(self):
        """GET /api/scan without a cookie should return 401."""
        fresh_client = TestClient(app)
        response = fresh_client.get("/api/scan")
        assert response.status_code == 401

    @patch("api.router.GmailFetcher")
    def test_scan_endpoint_returns_correct_shape(self, MockFetcher):
        """Each account in the response should have the expected fields."""
        mock_instance = MagicMock()
        mock_instance.fetch_headers.return_value = [
            {"subject": "Welcome to Facebook!", "from": "notification@facebook.com", "date": "2026-02-01"},
        ]
        MockFetcher.return_value = mock_instance

        cookie = self._get_auth_cookie()
        fresh_client = TestClient(app)
        fresh_client.cookies.set(COOKIE_NAME, cookie)
        response = fresh_client.get("/api/scan")

        data = response.json()
        account = data["accounts"][0]
        expected_fields = ["domain", "company", "subject", "date", "category", "risk", "deletion_email"]
        for field in expected_fields:
            assert field in account, f"Missing field '{field}' in account response"

"""
ARFM Backend — Email Scanner Service
Modular scanning pipeline with pluggable detection strategies.
The RegexScanner can be swapped for an AI inference model in the future.
"""

import re
import json
import os
import logging
from abc import ABC, abstractmethod
from typing import Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

# ── Load Company Mapping ────────────────────────────────────────
_COMPANY_MAP_PATH = os.path.join(os.path.dirname(__file__), "company_map.json")

def load_company_map() -> dict:
    """Load the domain → company metadata mapping from the JSON file."""
    with open(_COMPANY_MAP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════
#  Abstract Base Scanner — swap this for AI in the future
# ═══════════════════════════════════════════════════════════════

class BaseScanner(ABC):
    """
    Interface for email scanning strategies.
    Subclass and implement `scan()` to create a new detection engine
    (e.g., AI-based classification, NLP pipelines, etc.).
    """

    @abstractmethod
    def scan(self, messages: list[dict]) -> list[dict]:
        """
        Analyze a list of email header dicts and return detected accounts.

        Args:
            messages: List of dicts with keys like 'subject', 'from', 'date', 'snippet'.

        Returns:
            List of dicts with keys: 'domain', 'company', 'subject', 'date',
            'category', 'risk', 'deletion_email'.
        """
        pass


# ═══════════════════════════════════════════════════════════════
#  Regex Scanner — Pattern-based account detection
# ═══════════════════════════════════════════════════════════════

class RegexScanner(BaseScanner):
    """
    Detects account creation emails using regex pattern matching.
    Matches subject lines AND snippet content containing common signup phrases.
    """

    # ── Subject-line patterns ────────────────────────────────────
    SIGNUP_PATTERNS = [
        # Welcome / onboarding
        re.compile(r"(?i)(welcome\s+to)\b", re.UNICODE),
        re.compile(r"(?i)\bwelcome[,!]?\s", re.UNICODE),
        re.compile(r"(?i)(getting\s+started\s+with)", re.UNICODE),
        re.compile(r"(?i)(thanks?\s+for\s+(signing\s+up|joining|registering|creating))", re.UNICODE),

        # Verification
        re.compile(r"(?i)(verify\s+your\s+(email|account|address))", re.UNICODE),
        re.compile(r"(?i)(confirm\s+your\s+(email|account|registration|address|sign[\s-]?up))", re.UNICODE),
        re.compile(r"(?i)(email\s+(verification|confirmation))", re.UNICODE),
        re.compile(r"(?i)(please\s+confirm)", re.UNICODE),
        re.compile(r"(?i)(verification\s+(code|link|email))", re.UNICODE),
        re.compile(r"(?i)(confirm(ation)?\s+link)", re.UNICODE),

        # Account creation
        re.compile(r"(?i)(account\s+(created|activated|ready|confirmed|setup|set\s+up))", re.UNICODE),
        re.compile(r"(?i)(new\s+account)", re.UNICODE),
        re.compile(r"(?i)(activate\s+your\s+account)", re.UNICODE),
        re.compile(r"(?i)(complete\s+(your\s+)?registration)", re.UNICODE),
        re.compile(r"(?i)(registration\s+(complete|confirm|successful|success))", re.UNICODE),
        re.compile(r"(?i)(sign[\s-]?up\s+(confirm|complet|success))", re.UNICODE),
        re.compile(r"(?i)(you('ve|'re|\s+have)\s+(registered|signed\s+up|joined|created))", re.UNICODE),
        re.compile(r"(?i)(your\s+account\s+is\s+ready)", re.UNICODE),
        re.compile(r"(?i)(set\s+up\s+your\s+(account|profile|password))", re.UNICODE),

        # Password / security setup
        re.compile(r"(?i)(set\s+your\s+password)", re.UNICODE),
        re.compile(r"(?i)(create\s+your\s+password)", re.UNICODE),
        re.compile(r"(?i)(reset\s+your\s+password)", re.UNICODE),
        re.compile(r"(?i)(one[\s-]?time\s+(password|code|pin|otp))", re.UNICODE),
        re.compile(r"(?i)\botp\b", re.UNICODE),
        re.compile(r"(?i)(security\s+code)", re.UNICODE),
        re.compile(r"(?i)(login\s+code)", re.UNICODE),
        re.compile(r"(?i)(two[\s-]?factor)", re.UNICODE),

        # Subscription / trial
        re.compile(r"(?i)(subscription\s+(confirm|activated|started))", re.UNICODE),
        re.compile(r"(?i)(trial\s+(started|activated|begun|begins))", re.UNICODE),
        re.compile(r"(?i)(free\s+trial)", re.UNICODE),
        re.compile(r"(?i)(your\s+(subscription|membership|plan)\b)", re.UNICODE),

        # Order / purchase (first-time)
        re.compile(r"(?i)(first\s+order)", re.UNICODE),
        re.compile(r"(?i)(order\s+confirm)", re.UNICODE),

        # Profile
        re.compile(r"(?i)(complete\s+your\s+profile)", re.UNICODE),
        re.compile(r"(?i)(update\s+your\s+profile)", re.UNICODE),
    ]

    # ── Snippet patterns (email body preview) ────────────────────
    SNIPPET_PATTERNS = [
        re.compile(r"(?i)(verify\s+your\s+email)", re.UNICODE),
        re.compile(r"(?i)(welcome\s+to)", re.UNICODE),
        re.compile(r"(?i)(account\s+has\s+been\s+created)", re.UNICODE),
        re.compile(r"(?i)(thanks?\s+for\s+(signing\s+up|joining|registering))", re.UNICODE),
        re.compile(r"(?i)(confirm(ation)?\s+(code|link|email))", re.UNICODE),
        re.compile(r"(?i)(click\s+(here|the\s+link|below)\s+to\s+(verify|confirm|activate))", re.UNICODE),
        re.compile(r"(?i)(your\s+account\s+is\s+(ready|active|set\s+up))", re.UNICODE),
    ]

    # Regex to extract email address from "From" header
    EMAIL_REGEX = re.compile(r"[\w.+-]+@([\w-]+\.[\w.-]+)")

    # Domains to SKIP — these are email providers, not services the user signed up for
    SKIP_DOMAINS = {
        "gmail.com", "googlemail.com", "yahoo.com", "outlook.com", "hotmail.com",
        "live.com", "msn.com", "aol.com", "icloud.com", "mail.com", "protonmail.com",
        "yandex.com", "zoho.com", "rediffmail.com", "gmx.com", "tutanota.com",
        "fastmail.com", "posteo.de", "pm.me", "proton.me",
        # Google internal
        "google.com", "accounts.google.com", "youtube.com",
        # Generic notification domains
        "noreply.com", "no-reply.com", "mailer-daemon.com",
    }

    # Noreply sender patterns (indicates automated/signup email — matches broadly)
    NOREPLY_PATTERNS = re.compile(
        r"(?i)(no[\s._-]?reply|noreply|notification|info@|support@|hello@|signup@|welcome@|"
        r"verify@|confirm@|account@|register@|team@|admin@|security@|alert@|updates@|"
        r"mailer@|do[\s._-]?not[\s._-]?reply)",
        re.UNICODE,
    )

    def scan(self, messages: list[dict]) -> list[dict]:
        """
        Scan email headers for account creation patterns.
        Returns a deduplicated list of detected accounts.
        """
        company_map = load_company_map()
        detected = {}

        for msg in messages:
            subject = msg.get("subject", "")
            sender = msg.get("from", "")
            date = msg.get("date", "")
            snippet = msg.get("snippet", "")

            # Extract domain from sender
            domain = self._extract_domain(sender)
            if not domain or domain in self.SKIP_DOMAINS:
                continue

            # Skip if we've already detected this domain
            if domain in detected:
                continue

            # Check if this looks like a signup email:
            # 1. Subject matches a signup pattern, OR
            # 2. Snippet matches a signup pattern, OR
            # 3. Domain is in our known company map AND sender is noreply-ish
            is_signup = False
            confidence = 0.0

            if self._matches_signup(subject):
                is_signup = True
                confidence = 0.9
            elif self._matches_snippet(snippet):
                is_signup = True
                confidence = 0.75
            elif domain in company_map and self.NOREPLY_PATTERNS.search(sender):
                is_signup = True
                confidence = 0.6

            if not is_signup:
                continue

            # Look up company info from our mapping
            company_info = company_map.get(domain, None)
            company_name = company_info["name"] if company_info else domain.split(".")[0].title()
            category = company_info["category"] if company_info else "other"
            risk = company_info.get("risk", 0.5) if company_info else 0.5
            deletion_email = company_info.get("deletion_email", "") if company_info else ""

            # Boost confidence if domain is in known company map
            if company_info:
                confidence = min(confidence + 0.05, 1.0)

            detected[domain] = {
                "domain": domain,
                "company": company_name,
                "from_email": sender,
                "subject": subject,
                "signup_date": self._normalize_date(date),
                "date": date,
                "category": category,
                "risk": risk,
                "risk_score": self._risk_label(risk),
                "confidence": round(confidence, 2),
                "deletion_email": deletion_email,
            }

        return list(detected.values())

    def _matches_signup(self, subject: str) -> bool:
        """Check if a subject line matches any signup pattern."""
        return any(pattern.search(subject) for pattern in self.SIGNUP_PATTERNS)

    def _matches_snippet(self, snippet: str) -> bool:
        """Check if a snippet matches any signup pattern."""
        if not snippet:
            return False
        return any(pattern.search(snippet) for pattern in self.SNIPPET_PATTERNS)

    def _extract_domain(self, sender: str) -> Optional[str]:
        """Extract the root domain from a sender email address."""
        match = self.EMAIL_REGEX.search(sender)
        if match:
            domain = match.group(1).lower()
            # Normalize subdomains: mail.company.com → company.com
            parts = domain.split(".")
            if len(parts) > 2:
                # Keep the last 2 parts (e.g., company.com) unless it's a country TLD
                country_tlds = {"co", "com", "org", "net", "ac", "gov"}
                if parts[-2] in country_tlds and len(parts) > 2:
                    return ".".join(parts[-3:])
                return ".".join(parts[-2:])
            return domain
        return None

    @staticmethod
    def _risk_label(risk: float) -> str:
        """Convert numeric risk to a label."""
        if risk >= 0.8:
            return "High"
        elif risk >= 0.5:
            return "Medium"
        return "Low"

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """Try to extract YYYY-MM from a date header."""
        if not date_str:
            return "Unknown"
        # Try common patterns
        import re as _re
        # RFC 2822: "Mon, 15 Jan 2024 10:30:00 +0000"
        m = _re.search(r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})", date_str, _re.IGNORECASE)
        if m:
            months = {"jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
                       "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12"}
            month = months.get(m.group(2).lower()[:3], "01")
            return f"{m.group(3)}-{month}"
        # ISO format: "2024-01-15T..."
        m = _re.search(r"(\d{4})-(\d{2})", date_str)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        return "Unknown"


# ═══════════════════════════════════════════════════════════════
#  Gmail Fetcher — Retrieves email headers via Gmail API
# ═══════════════════════════════════════════════════════════════

class GmailFetcher:
    """
    Fetches email headers from Gmail API.
    Uses targeted search queries to find signup emails efficiently,
    then batch-fetches headers with minimal API calls.
    """

    BATCH_SIZE = 500  # Messages per page
    HEADERS_TO_FETCH = ["Subject", "From", "Date"]

    # Gmail search queries targeting signup emails
    # We run multiple targeted queries to maximize coverage
    SIGNUP_QUERIES = [
        'subject:(welcome OR "welcome to" OR "getting started")',
        'subject:(verify OR "verify your" OR "confirm your" OR verification)',
        'subject:("account created" OR "account activated" OR "account is ready")',
        'subject:("sign up" OR "signed up" OR "signing up" OR "registration")',
        'subject:("thank you for joining" OR "thanks for signing up" OR "thanks for joining")',
        'subject:(activate OR "activation" OR "complete registration")',
        'subject:(OTP OR "one time" OR "security code" OR "login code")',
        'subject:("set your password" OR "create password" OR "reset password")',
        'subject:("free trial" OR "subscription" OR "your plan" OR "your membership")',
        'subject:("first order" OR "order confirmation")',
        'from:(noreply OR no-reply OR notification OR donotreply)',
    ]

    def __init__(self, credentials: Credentials, max_results: int = 5000):
        self.service = build("gmail", "v1", credentials=credentials)
        self.max_results = max_results

    def fetch_headers(self) -> list[dict]:
        """
        Fetch email headers from the user's Gmail using targeted search queries.
        Returns a list of dicts with 'subject', 'from', 'date', 'snippet' keys.
        """
        # Collect unique message IDs from all queries
        all_ids = set()
        per_query_limit = self.max_results // len(self.SIGNUP_QUERIES)

        for query in self.SIGNUP_QUERIES:
            try:
                ids = self._search_messages(query, max_per_query=per_query_limit)
                all_ids.update(ids)
                logger.info(f"Query '{query[:50]}...' returned {len(ids)} messages")
            except Exception as e:
                logger.warning(f"Query failed: {query[:50]}... — {e}")
                continue

        logger.info(f"Total unique message IDs collected: {len(all_ids)}")

        # Fetch headers for all collected IDs
        headers = []
        for msg_id in list(all_ids)[:self.max_results]:
            header_data = self._get_message_headers(msg_id)
            if header_data:
                headers.append(header_data)

        logger.info(f"Fetched {len(headers)} message headers")
        return headers

    def _search_messages(self, query: str, max_per_query: int = 500) -> list[str]:
        """Search Gmail with a specific query and return message IDs."""
        ids = []
        page_token = None

        while len(ids) < max_per_query:
            batch_size = min(self.BATCH_SIZE, max_per_query - len(ids))
            try:
                request = self.service.users().messages().list(
                    userId="me",
                    q=query,
                    maxResults=batch_size,
                    pageToken=page_token,
                )
                response = request.execute()
            except Exception as e:
                logger.warning(f"Gmail list API error: {e}")
                break

            messages = response.get("messages", [])
            if not messages:
                break

            ids.extend(msg["id"] for msg in messages)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return ids

    def _get_message_headers(self, message_id: str) -> Optional[dict]:
        """Fetch metadata-format headers for a single message."""
        try:
            msg = self.service.users().messages().get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=self.HEADERS_TO_FETCH,
            ).execute()

            headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

            return {
                "subject": headers.get("subject", ""),
                "from": headers.get("from", ""),
                "date": headers.get("date", ""),
                "snippet": msg.get("snippet", ""),
            }
        except Exception:
            return None

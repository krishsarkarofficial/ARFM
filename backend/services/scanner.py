"""
ARFM Backend — Email Scanner Service
Modular scanning pipeline with pluggable detection strategies.
The RegexScanner can be swapped for an AI inference model in the future.
"""

import re
import json
import os
from abc import ABC, abstractmethod
from typing import Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


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
    Matches subject lines containing common signup/welcome phrases.
    """

    # Patterns that indicate an account was created
    SIGNUP_PATTERNS = [
        re.compile(r"(?i)(welcome\s+to)", re.UNICODE),
        re.compile(r"(?i)(verify\s+your)", re.UNICODE),
        re.compile(r"(?i)(confirm\s+your\s+(email|account|registration))", re.UNICODE),
        re.compile(r"(?i)(account\s+created)", re.UNICODE),
        re.compile(r"(?i)(thanks?\s+for\s+signing\s+up)", re.UNICODE),
        re.compile(r"(?i)(registration\s+(complete|confirm|success))", re.UNICODE),
        re.compile(r"(?i)(activate\s+your\s+account)", re.UNICODE),
        re.compile(r"(?i)(you('ve|'re|\s+have)\s+(registered|signed\s+up|joined))", re.UNICODE),
        re.compile(r"(?i)(new\s+account)", re.UNICODE),
        re.compile(r"(?i)(getting\s+started\s+with)", re.UNICODE),
    ]

    # Regex to extract email address from "From" header
    EMAIL_REGEX = re.compile(r"[\w.+-]+@([\w-]+\.[\w.-]+)")

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

            # Check if subject matches any signup pattern
            if not self._matches_signup(subject):
                continue

            # Extract domain from sender
            domain = self._extract_domain(sender)
            if not domain:
                continue

            # Skip if we've already detected this domain
            if domain in detected:
                continue

            # Look up company info from our mapping
            company_info = company_map.get(domain, None)
            company_name = company_info["name"] if company_info else domain.split(".")[0].title()
            category = company_info["category"] if company_info else "other"
            risk = company_info.get("risk", 0.5) if company_info else 0.5
            deletion_email = company_info.get("deletion_email", "") if company_info else ""

            detected[domain] = {
                "domain": domain,
                "company": company_name,
                "subject": subject,
                "date": date,
                "category": category,
                "risk": risk,
                "deletion_email": deletion_email,
            }

        return list(detected.values())

    def _matches_signup(self, subject: str) -> bool:
        """Check if a subject line matches any signup pattern."""
        return any(pattern.search(subject) for pattern in self.SIGNUP_PATTERNS)

    def _extract_domain(self, sender: str) -> Optional[str]:
        """Extract the root domain from a sender email address."""
        match = self.EMAIL_REGEX.search(sender)
        if match:
            return match.group(1).lower()
        return None


# ═══════════════════════════════════════════════════════════════
#  Gmail Fetcher — Retrieves email headers via Gmail API
# ═══════════════════════════════════════════════════════════════

class GmailFetcher:
    """
    Fetches email headers from Gmail API.
    Retrieves up to `max_results` message headers with pagination.
    """

    BATCH_SIZE = 500  # Messages per page
    HEADERS_TO_FETCH = ["Subject", "From", "Date"]

    def __init__(self, credentials: Credentials, max_results: int = 5000):
        self.service = build("gmail", "v1", credentials=credentials)
        self.max_results = max_results

    def fetch_headers(self) -> list[dict]:
        """
        Fetch email headers from the user's Gmail inbox.
        Returns a list of dicts with 'subject', 'from', 'date', 'snippet' keys.
        """
        message_ids = self._list_message_ids()
        headers = []

        for msg_id in message_ids:
            header_data = self._get_message_headers(msg_id)
            if header_data:
                headers.append(header_data)

        return headers

    def _list_message_ids(self) -> list[str]:
        """Paginate through messages().list to collect up to max_results IDs."""
        ids = []
        page_token = None

        while len(ids) < self.max_results:
            batch_size = min(self.BATCH_SIZE, self.max_results - len(ids))
            request = self.service.users().messages().list(
                userId="me",
                maxResults=batch_size,
                pageToken=page_token,
            )
            response = request.execute()

            messages = response.get("messages", [])
            ids.extend(msg["id"] for msg in messages)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return ids[:self.max_results]

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

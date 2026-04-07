"""
ARFM Backend — Email Verifier & DPO Discovery
Verifies email addresses via MX records and discovers DPO contacts
by scraping company privacy policy pages.
"""

import re
import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  MX Record Validation
# ═══════════════════════════════════════════════════════════════

def verify_email_domain(email: str) -> dict:
    """
    Check if an email domain has valid MX records (can receive mail).

    Returns:
        Dict with 'valid' (bool), 'domain', 'mx_records' (list), 'error' (str|None)
    """
    try:
        domain = email.split("@")[1].lower()
    except (IndexError, AttributeError):
        return {"valid": False, "domain": "", "mx_records": [], "error": "Invalid email format"}

    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "MX")
        mx_records = sorted(
            [(r.preference, str(r.exchange).rstrip(".")) for r in answers],
            key=lambda x: x[0],
        )
        return {
            "valid": True,
            "domain": domain,
            "mx_records": [mx[1] for mx in mx_records],
            "error": None,
        }
    except Exception as e:
        error_type = type(e).__name__
        logger.warning(f"MX lookup failed for {domain}: {error_type}")
        return {
            "valid": False,
            "domain": domain,
            "mx_records": [],
            "error": f"No MX records found ({error_type})",
        }


# ═══════════════════════════════════════════════════════════════
#  Privacy Page Scraper — Discovers DPO emails from websites
# ═══════════════════════════════════════════════════════════════

# Common privacy page URL patterns
PRIVACY_PATHS = [
    "/privacy",
    "/privacy-policy",
    "/privacy-policy.html",
    "/legal/privacy",
    "/en/privacy",
    "/about/privacy",
    "/pages/privacy-policy",
    "/terms/privacy",
]

# Regex for extracting email addresses from HTML
EMAIL_EXTRACT_RE = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+",
    re.UNICODE,
)

# Keywords that indicate a DPO / privacy contact (ranked by relevance)
DPO_KEYWORDS = [
    "dpo", "data protection officer", "data protection",
    "privacy officer", "privacy team", "privacy",
    "grievance officer", "grievance",
    "data privacy", "dataprotection",
    "gdpr", "dpdpa", "ccpa",
    "deletion", "erasure", "right to be forgotten",
]

# Email prefixes that are likely DPO/privacy contacts
DPO_PREFIXES = {
    "dpo", "privacy", "dataprotection", "data-protection",
    "dataprivacy", "data-privacy", "gdpr", "grievance",
    "grievanceofficer", "grievance-officer", "privacyoffice",
    "privacyofficer", "privacy-officer", "legal",
    "datarequests", "data-requests",
}

# Skip these — they're generic, not DPO-specific
SKIP_PREFIXES = {
    "support", "help", "info", "contact", "hello", "team",
    "sales", "marketing", "careers", "jobs", "press", "media",
    "admin", "webmaster", "postmaster", "abuse", "billing",
    "noreply", "no-reply", "donotreply",
}


async def discover_dpo_email(domain: str, timeout: float = 8.0) -> dict:
    """
    Attempt to find the actual DPO/privacy email from a company's website.

    Strategy:
    1. Fetch privacy policy page(s)
    2. Extract all email addresses from the page
    3. Score emails by DPO-relevance
    4. Return the best candidate + all found emails

    Returns:
        Dict with:
          - found: bool
          - dpo_email: str (best candidate) or None
          - all_emails: list[str] (all emails found on privacy pages)
          - source_url: str (page where email was found)
          - verified: bool (MX record valid)
    """
    all_emails = set()
    best_email = None
    best_score = -1
    source_url = None

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "ARFM-DPO-Resolver/1.0 (privacy-tool)"},
    ) as client:
        for path in PRIVACY_PATHS:
            for scheme in ["https", "http"]:
                url = f"{scheme}://{domain}{path}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue

                    # Parse page
                    content_type = resp.headers.get("content-type", "")
                    if "html" not in content_type and "text" not in content_type:
                        continue

                    text = resp.text
                    soup = BeautifulSoup(text, "html.parser")

                    # Remove scripts/styles
                    for tag in soup(["script", "style", "noscript"]):
                        tag.decompose()

                    page_text = soup.get_text(separator=" ", strip=True)

                    # Extract emails from full HTML (catches mailto: links too)
                    emails_in_page = EMAIL_EXTRACT_RE.findall(text)
                    # Also extract from visible text
                    emails_in_text = EMAIL_EXTRACT_RE.findall(page_text)

                    found = set(emails_in_page + emails_in_text)
                    # Filter out image/file extensions
                    found = {
                        e.lower() for e in found
                        if not e.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js"))
                    }

                    if not found:
                        continue

                    all_emails.update(found)

                    # Score each email
                    for email in found:
                        score = _score_dpo_email(email, page_text)
                        if score > best_score:
                            best_score = score
                            best_email = email
                            source_url = url

                    # If we found a high-confidence DPO email, stop searching
                    if best_score >= 5:
                        break

                except httpx.HTTPError:
                    continue
                except Exception as e:
                    logger.debug(f"Error scraping {url}: {e}")
                    continue

            if best_score >= 5:
                break

    # Verify MX records of the best candidate
    verified = False
    if best_email:
        mx_result = verify_email_domain(best_email)
        verified = mx_result["valid"]

    return {
        "found": best_email is not None,
        "dpo_email": best_email,
        "all_emails": sorted(list(all_emails)),
        "source_url": source_url,
        "score": best_score,
        "verified": verified,
    }


def _score_dpo_email(email: str, page_context: str) -> int:
    """
    Score an email address for DPO relevance.
    Higher score = more likely to be the actual DPO contact.
    """
    score = 0
    prefix = email.split("@")[0].lower()

    # Skip generic emails
    if prefix in SKIP_PREFIXES:
        return -1

    # Strong signal: prefix matches known DPO prefixes
    if prefix in DPO_PREFIXES:
        score += 5

    # Partial match on prefix
    for dpo_prefix in DPO_PREFIXES:
        if dpo_prefix in prefix or prefix in dpo_prefix:
            score += 2
            break

    # Context: email appears near DPO keywords in the page text
    email_lower = email.lower()
    page_lower = page_context.lower()
    for keyword in DPO_KEYWORDS:
        # Check if keyword appears within 200 chars of the email mention
        idx = page_lower.find(email_lower)
        if idx >= 0:
            surrounding = page_lower[max(0, idx - 200):idx + len(email_lower) + 200]
            if keyword in surrounding:
                score += 1

    return score

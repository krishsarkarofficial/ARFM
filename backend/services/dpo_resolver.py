"""
ARFM Backend — DPO Resolver
Finds the Data Protection Officer / Privacy contact email for a given company.

Resolution order:
  1. Known DPO from company_map.json (verified entries)
  2. Privacy page scraper (crawls company privacy pages for real emails)
  3. MX-validated pattern generation (tries dpo@, privacy@, etc. and validates)
  4. Fallback: privacy@{domain} (unverified)
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Load Company Map ─────────────────────────────────────────────
_COMPANY_MAP_PATH = Path(__file__).parent / "company_map.json"

def _load_company_map() -> dict:
    try:
        with open(_COMPANY_MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.warning("Could not load company_map.json")
        return {}

COMPANY_MAP = _load_company_map()


# ── Common DPO Email Patterns ────────────────────────────────────
# Ordered by likelihood (most common first)
DPO_EMAIL_PATTERNS = [
    "dpo@{domain}",
    "privacy@{domain}",
    "dataprotection@{domain}",
    "data-protection@{domain}",
    "gdpr@{domain}",
    "dataprivacy@{domain}",
    "grievance@{domain}",
    "grievanceofficer@{domain}",
    "privacyoffice@{domain}",
    "legal@{domain}",
    "support@{domain}",
]


class DPOResolver:
    """
    Resolves the best DPO / privacy contact email for a given domain.
    Uses a multi-tier lookup strategy with verification.
    """

    @staticmethod
    def resolve(domain: str) -> dict:
        """
        Find the DPO contact for a domain (synchronous, no scraping).
        For full resolution with scraping, use resolve_deep().

        Args:
            domain: The company's domain (e.g., 'facebook.com')

        Returns:
            Dict with dpo_email, company, source, confidence, all_candidates
        """
        domain = domain.lower().strip()

        # ── Tier 1: Known DPO from company map ──────────────────
        if domain in COMPANY_MAP:
            entry = COMPANY_MAP[domain]
            known_email = entry.get("deletion_email", "")
            if known_email:
                return {
                    "dpo_email": known_email,
                    "company": entry.get("name", domain),
                    "source": "known_map",
                    "confidence": 0.95,
                    "category": entry.get("category", "unknown"),
                    "verified": True,
                    "all_candidates": [known_email],
                }

        # ── Tier 2: Generate candidates from patterns ───────────
        candidates = [p.format(domain=domain) for p in DPO_EMAIL_PATTERNS]
        company_name = COMPANY_MAP.get(domain, {}).get("name", "")
        if not company_name:
            company_name = domain.split(".")[0].capitalize()

        primary = f"privacy@{domain}"

        return {
            "dpo_email": primary,
            "company": company_name,
            "source": "pattern_generated",
            "confidence": 0.4,
            "category": COMPANY_MAP.get(domain, {}).get("category", "unknown"),
            "verified": False,
            "all_candidates": candidates,
        }

    @staticmethod
    async def resolve_deep(domain: str) -> dict:
        """
        Full DPO resolution with privacy page scraping and MX validation.
        This is the async version that does real discovery.

        Resolution order:
          1. Known DPO from company map
          2. Scrape privacy policy pages for real DPO emails
          3. MX-validate generated patterns
          4. Fallback

        Returns:
            Dict with dpo_email, company, source, confidence, verified,
            all_candidates, scraped_emails
        """
        from services.email_verifier import discover_dpo_email, verify_email_domain

        domain = domain.lower().strip()

        # ── Tier 1: Known DPO from company map ──────────────────
        if domain in COMPANY_MAP:
            entry = COMPANY_MAP[domain]
            known_email = entry.get("deletion_email", "")
            if known_email:
                # Verify the known email's MX records
                mx_result = verify_email_domain(known_email)
                return {
                    "dpo_email": known_email,
                    "company": entry.get("name", domain),
                    "source": "known_map",
                    "confidence": 0.95 if mx_result["valid"] else 0.7,
                    "category": entry.get("category", "unknown"),
                    "verified": mx_result["valid"],
                    "mx_valid": mx_result["valid"],
                    "all_candidates": [known_email],
                    "scraped_emails": [],
                }

        # ── Tier 2: Scrape privacy pages ────────────────────────
        company_name = domain.split(".")[0].capitalize()

        try:
            scrape_result = await discover_dpo_email(domain)
            if scrape_result["found"] and scrape_result["dpo_email"]:
                return {
                    "dpo_email": scrape_result["dpo_email"],
                    "company": company_name,
                    "source": "privacy_page_scraper",
                    "confidence": 0.85 if scrape_result["verified"] else 0.65,
                    "category": "unknown",
                    "verified": scrape_result["verified"],
                    "mx_valid": scrape_result["verified"],
                    "all_candidates": scrape_result["all_emails"][:10],
                    "scraped_emails": scrape_result["all_emails"][:10],
                    "source_url": scrape_result.get("source_url", ""),
                }
        except Exception as e:
            logger.warning(f"Privacy page scraping failed for {domain}: {e}")

        # ── Tier 3: MX-validated pattern generation ─────────────
        candidates = [p.format(domain=domain) for p in DPO_EMAIL_PATTERNS]

        # Check which patterns have valid MX records
        for candidate in candidates[:5]:  # Check top 5 patterns
            mx_result = verify_email_domain(candidate)
            if mx_result["valid"]:
                return {
                    "dpo_email": candidate,
                    "company": company_name,
                    "source": "mx_validated_pattern",
                    "confidence": 0.6,
                    "category": "unknown",
                    "verified": True,
                    "mx_valid": True,
                    "all_candidates": candidates,
                    "scraped_emails": [],
                }

        # ── Tier 4: Fallback (unverified) ───────────────────────
        return {
            "dpo_email": f"privacy@{domain}",
            "company": company_name,
            "source": "unverified_fallback",
            "confidence": 0.3,
            "category": "unknown",
            "verified": False,
            "mx_valid": False,
            "all_candidates": candidates,
            "scraped_emails": [],
        }

    @staticmethod
    def resolve_batch(domains: list[str]) -> list[dict]:
        """Resolve DPO contacts for multiple domains at once (sync only)."""
        return [DPOResolver.resolve(d) for d in domains]

    @staticmethod
    def get_known_count() -> int:
        """Return the number of companies with known DPO emails."""
        return sum(1 for v in COMPANY_MAP.values() if v.get("deletion_email"))

"""
ARFM Backend — DPO Resolver
Finds the Data Protection Officer / Privacy contact email for a given company.

Resolution order:
  1. Known DPO from company_map.json
  2. Common privacy email patterns (dpo@, privacy@, dataprotection@, etc.)
  3. Generic fallback pattern: privacy@{domain}
"""

import json
import logging
from pathlib import Path

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
    "privacyoffice@{domain}",
    "legal@{domain}",
    "support@{domain}",
]


class DPOResolver:
    """
    Resolves the best DPO / privacy contact email for a given domain.
    Uses a multi-tier lookup strategy.
    """

    @staticmethod
    def resolve(domain: str) -> dict:
        """
        Find the DPO contact for a domain.

        Args:
            domain: The company's domain (e.g., 'facebook.com')

        Returns:
            Dict with:
              - dpo_email: str — the resolved email
              - company: str — company name
              - source: str — 'known_map', 'pattern_match', or 'fallback'
              - confidence: float — 0.0–1.0
              - all_candidates: list[str] — all possible emails
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
                    "all_candidates": [known_email],
                }

        # ── Tier 2: Generate candidates from patterns ───────────
        candidates = [p.format(domain=domain) for p in DPO_EMAIL_PATTERNS]
        company_name = COMPANY_MAP.get(domain, {}).get("name", "")
        if not company_name:
            # Capitalize domain name as fallback company name
            company_name = domain.split(".")[0].capitalize()

        # Primary pick: privacy@ is the most universal
        primary = f"privacy@{domain}"

        return {
            "dpo_email": primary,
            "company": company_name,
            "source": "pattern_generated",
            "confidence": 0.6,
            "category": COMPANY_MAP.get(domain, {}).get("category", "unknown"),
            "all_candidates": candidates,
        }

    @staticmethod
    def resolve_batch(domains: list[str]) -> list[dict]:
        """Resolve DPO contacts for multiple domains at once."""
        return [DPOResolver.resolve(d) for d in domains]

    @staticmethod
    def get_known_count() -> int:
        """Return the number of companies with known DPO emails."""
        return sum(1 for v in COMPANY_MAP.values() if v.get("deletion_email"))

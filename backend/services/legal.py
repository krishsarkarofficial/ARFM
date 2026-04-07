"""
ARFM Backend — Legal Template Engine
GDPR, CCPA, and DPDPA data deletion request templates.
"""

from datetime import datetime


# ═══════════════════════════════════════════════════════════════
#  Legal Deletion Templates
# ═══════════════════════════════════════════════════════════════

GDPR_TEMPLATE = """Dear Data Protection Officer,

I am writing to exercise my right to erasure (right to be forgotten) under Article 17 of the General Data Protection Regulation (GDPR) (EU) 2016/679.

I request that {company} erase all personal data you hold about me without undue delay. My personal data should be erased because:

- The data is no longer necessary for the purpose for which it was originally collected or processed.
- I withdraw my consent on which the processing is based, and there is no other legal ground for the processing.

My details for identification:
- Email address: {user_email}

Under GDPR Article 12, you are required to respond to this request within one calendar month. If you need to extend this period, you must inform me within the first month.

If you do not normally deal with these requests, please forward this email to the relevant person in your organization.

Please confirm in writing that you have erased my personal data.

Yours faithfully,
The account holder of {user_email}

Date: {date}"""

CCPA_TEMPLATE = """Dear Privacy Team,

I am writing to exercise my right to deletion under the California Consumer Privacy Act (CCPA), California Civil Code Section 1798.105.

I request that {company} delete any personal information you have collected about me. Under the CCPA, you are required to delete this information from your records and direct any service providers to delete my personal information from their records.

My details for identification:
- Email address: {user_email}

Under the CCPA, you must respond to this request within 45 calendar days. If you need additional time (up to 45 more days), you must notify me of the extension.

Please confirm completion of the deletion via email response.

Sincerely,
The account holder of {user_email}

Date: {date}"""

DPDPA_TEMPLATE = """Dear Data Protection Officer / Grievance Officer,

I am writing to exercise my right to erasure of personal data under Section 12(3) of the Digital Personal Data Protection Act, 2023 (DPDPA) of India.

I hereby request that {company} erase all personal data that you have collected, stored, or processed about me. I withdraw my consent for the processing of my personal data, and I request that you:

1. Permanently erase all personal data associated with my account and the email address listed below from all your systems, databases, and records;

2. Direct any data processors or third parties with whom you have shared my personal data to erase it as well;

3. Cease all processing of my personal data immediately upon receipt of this request;

4. Provide me with a written confirmation that the erasure has been completed.

My details for identification:
- Email address: {user_email}

Under the DPDPA 2023, Data Fiduciaries are required to comply with erasure requests within a reasonable timeframe. Failure to comply may result in a complaint to the Data Protection Board of India under Section 27 of the Act.

If you require any additional information to verify my identity, please inform me of the same.

Yours faithfully,
The account holder of {user_email}

Date: {date}

This request is made pursuant to the Digital Personal Data Protection Act, 2023 (Act No. 22 of 2023), Government of India.
Non-compliance may be reported to the Data Protection Board of India."""


class DeletionTemplateEngine:
    """
    Generates legally-compliant data deletion request emails.
    Supports GDPR (EU), CCPA (California), and DPDPA (India) jurisdictions.
    """

    TEMPLATES = {
        "gdpr": GDPR_TEMPLATE,
        "ccpa": CCPA_TEMPLATE,
        "dpdpa": DPDPA_TEMPLATE,
    }

    SUBJECTS = {
        "gdpr": "GDPR Article 17 — Right to Erasure Request",
        "ccpa": "CCPA Section 1798.105 — Right to Deletion Request",
        "dpdpa": "DPDPA Section 12(3) — Right to Erasure of Personal Data",
    }

    @classmethod
    def get_supported_jurisdictions(cls) -> list[str]:
        """Return the list of supported legal jurisdictions."""
        return list(cls.TEMPLATES.keys())

    @classmethod
    def populate(cls, company: str, user_email: str, jurisdiction: str) -> dict:
        """
        Generate a deletion request for the given jurisdiction.

        Args:
            company: Name of the target company.
            user_email: The user's email address.
            jurisdiction: Legal framework — 'gdpr', 'ccpa', or 'dpdpa'.

        Returns:
            Dict with 'subject' and 'body' populated from the template.

        Raises:
            ValueError: If the jurisdiction is not supported.
        """
        jurisdiction = jurisdiction.lower().strip()
        if jurisdiction not in cls.TEMPLATES:
            supported = ", ".join(cls.TEMPLATES.keys())
            raise ValueError(
                f"Unsupported jurisdiction '{jurisdiction}'. Supported: {supported}"
            )

        template = cls.TEMPLATES[jurisdiction]
        body = template.format(
            company=company,
            user_email=user_email,
            date=datetime.utcnow().strftime("%B %d, %Y"),
        )

        return {
            "subject": cls.SUBJECTS[jurisdiction],
            "body": body,
        }

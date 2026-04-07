"""
ARFM Backend — API Router
Endpoints for email scanning, DPO lookup, and deletion request dispatch.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from google.oauth2.credentials import Credentials

from auth.security import get_credentials
from services.scanner import RegexScanner, GmailFetcher
from services.legal import DeletionTemplateEngine
from services.email_sender import build_rfc2822_message, send_via_gmail
from services.dpo_resolver import DPOResolver

router = APIRouter(prefix="/api", tags=["API"])


@router.get("/ping")
async def ping():
    """Simple connectivity check for the API layer."""
    return {"message": "pong"}


@router.get("/scan")
async def scan_emails(credentials: Credentials = Depends(get_credentials)):
    """
    Scan the authenticated user's Gmail for account creation emails.
    Fetches up to 5,000 email headers and runs regex-based detection.
    """
    fetcher = GmailFetcher(credentials, max_results=5000)
    messages = fetcher.fetch_headers()

    scanner = RegexScanner()
    accounts = scanner.scan(messages)

    return {
        "total_emails_scanned": len(messages),
        "accounts_found": len(accounts),
        "accounts": accounts,
    }


# ── DPO Lookup ──────────────────────────────────────────────────

@router.get("/dpo-lookup")
async def dpo_lookup(domain: str):
    """
    Look up the Data Protection Officer / privacy contact for a domain.

    Args:
        domain: Company domain (e.g., 'facebook.com')

    Returns:
        DPO email, company name, confidence score, and all candidate emails.
    """
    if not domain or "." not in domain:
        raise HTTPException(status_code=400, detail="Invalid domain. Provide a valid domain like 'example.com'.")

    result = DPOResolver.resolve(domain)
    return result


@router.post("/dpo-lookup-batch")
async def dpo_lookup_batch(domains: list[str]):
    """Look up DPO contacts for multiple domains at once."""
    if not domains or len(domains) > 100:
        raise HTTPException(status_code=400, detail="Provide 1-100 domains.")
    return {"results": DPOResolver.resolve_batch(domains)}


@router.get("/jurisdictions")
async def list_jurisdictions():
    """Return all supported legal jurisdictions."""
    return {
        "jurisdictions": DeletionTemplateEngine.get_supported_jurisdictions(),
        "known_companies": DPOResolver.get_known_count(),
    }


# ── Deletion Request ────────────────────────────────────────────

class DeletionRequest(BaseModel):
    """Request body for POST /api/send-request."""
    company: str
    to_email: str | None = None  # Optional; auto-resolved from DPO lookup if not set
    jurisdiction: str  # "gdpr", "ccpa", or "dpdpa"
    body: str | None = None  # Optional custom body; if not set, auto-generated
    user_email: str | None = None  # Optional; if not set, uses from credentials
    domain: str | None = None  # Domain for DPO auto-resolution


@router.post("/send-request")
async def send_deletion_request(
    request: DeletionRequest,
    credentials: Credentials = Depends(get_credentials),
):
    """
    Send a data deletion request email via the Gmail API.

    Accepts the company name, target email (or domain for auto-resolution),
    jurisdiction, and optionally a custom body.
    """
    # Determine user's email from the credential's token info
    from googleapiclient.discovery import build as gmail_build
    try:
        oauth_service = gmail_build("oauth2", "v2", credentials=credentials)
        user_info = oauth_service.userinfo().get().execute()
        sender_email = user_info.get("email", "")
    except Exception:
        sender_email = request.user_email or "user@gmail.com"

    # Auto-resolve DPO email if not provided
    to_email = request.to_email
    dpo_info = None
    if not to_email and request.domain:
        dpo_info = DPOResolver.resolve(request.domain)
        to_email = dpo_info["dpo_email"]
    elif not to_email:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'to_email' or 'domain' for DPO auto-resolution.",
        )

    # Generate legal body if not provided
    if request.body:
        email_body = request.body
        email_subject = f"Data Deletion Request — {request.company}"
    else:
        try:
            template = DeletionTemplateEngine.populate(
                company=request.company,
                user_email=sender_email,
                jurisdiction=request.jurisdiction,
            )
            email_body = template["body"]
            email_subject = template["subject"]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Build RFC 2822 message
    raw_message = build_rfc2822_message(
        to=to_email,
        from_email=sender_email,
        subject=email_subject,
        body=email_body,
    )

    # Send via Gmail API
    try:
        result = send_via_gmail(credentials, raw_message)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to send email via Gmail: {str(e)}",
        )

    return {
        "status": "sent",
        "message_id": result.get("id", ""),
        "thread_id": result.get("threadId", ""),
        "to": to_email,
        "company": request.company,
        "jurisdiction": request.jurisdiction,
        "dpo_source": dpo_info["source"] if dpo_info else "user_provided",
        "dpo_confidence": dpo_info["confidence"] if dpo_info else 1.0,
    }

"""
ARFM Backend — API Router
Endpoints for email scanning and deletion request dispatch.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from google.oauth2.credentials import Credentials

from auth.security import get_credentials
from services.scanner import RegexScanner, GmailFetcher
from services.legal import DeletionTemplateEngine
from services.email_sender import build_rfc2822_message, send_via_gmail

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

    Returns:
        JSON list of detected accounts with domain, company, category, risk, etc.
    """
    # Fetch headers from Gmail
    fetcher = GmailFetcher(credentials, max_results=5000)
    messages = fetcher.fetch_headers()

    # Run the regex scanner
    scanner = RegexScanner()
    accounts = scanner.scan(messages)

    return {
        "total_emails_scanned": len(messages),
        "accounts_found": len(accounts),
        "accounts": accounts,
    }


# ── Deletion Request ────────────────────────────────────────────

class DeletionRequest(BaseModel):
    """Request body for POST /api/send-request."""
    company: str
    to_email: str
    jurisdiction: str  # "gdpr" or "ccpa"
    body: str | None = None  # Optional custom body; if not set, auto-generated
    user_email: str | None = None  # Optional; if not set, uses from credentials


@router.post("/send-request")
async def send_deletion_request(
    request: DeletionRequest,
    credentials: Credentials = Depends(get_credentials),
):
    """
    Send a data deletion request email via the Gmail API.

    Accepts the company name, target email (DPO/privacy team), jurisdiction,
    and optionally a custom body. If no body is provided, the legal template
    is auto-populated.
    """
    # Determine user's email from the credential's token info
    from googleapiclient.discovery import build as gmail_build
    try:
        oauth_service = gmail_build("oauth2", "v2", credentials=credentials)
        user_info = oauth_service.userinfo().get().execute()
        sender_email = user_info.get("email", "")
    except Exception:
        sender_email = request.user_email or "user@gmail.com"

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
        to=request.to_email,
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
        "to": request.to_email,
        "company": request.company,
        "jurisdiction": request.jurisdiction,
    }


"""
ARFM Backend — Email Sender Service
RFC 2822 email construction and Gmail API dispatch.
"""

import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


def build_rfc2822_message(to: str, from_email: str, subject: str, body: str) -> str:
    """
    Construct a base64url-encoded RFC 2822 email message.

    Args:
        to: Recipient email address.
        from_email: Sender email address (the authenticated user).
        subject: Email subject line.
        body: Plain-text email body.

    Returns:
        Base64url-encoded raw message string for the Gmail API.
    """
    message = MIMEText(body, "plain")
    message["to"] = to
    message["from"] = from_email
    message["subject"] = subject

    # Gmail API expects base64url encoding (no padding)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return raw


def send_via_gmail(credentials: Credentials, raw_message: str) -> dict:
    """
    Send an email using the Gmail API users().messages().send method.

    Args:
        credentials: Google OAuth2 credentials with gmail.send scope.
        raw_message: Base64url-encoded RFC 2822 message.

    Returns:
        Gmail API response dict with message id, thread id, etc.
    """
    service = build("gmail", "v1", credentials=credentials)
    result = service.users().messages().send(
        userId="me",
        body={"raw": raw_message},
    ).execute()

    return result

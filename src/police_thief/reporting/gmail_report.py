"""Gmail OAuth reporting for league matches (league readiness Priority 5) --
the minimum production-safe path, not the full CLAUDE.md Sec 5 Gmail
integration.

OAuth only, never a password (E-39/E-40). This module never touches
credentials directly -- only the two local, gitignored files already
declared by ``config.models.EmailSettings`` (``credentials_path``,
``token_path``). If either is missing, or the optional google-api packages
are not installed, sending is skipped cleanly and the caller is told exactly
why: a missing mailer must never lose a match result, which is why
``send_report_email`` never raises and the JSON report is always written to
disk by the caller regardless of what this function returns.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from police_thief.reporting.match_report import MatchReport

NOT_CONFIGURED = "EMAIL NOT SENT -- OAUTH SETUP REQUIRED"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def send_report_email(
    report: MatchReport,
    report_path: Path,
    *,
    recipient: str,
    credentials_path: Path,
    token_path: Path,
) -> tuple[bool, str]:
    """Best-effort send. Returns ``(sent, status_message)``, never raises.

    Builds the email body from ``report`` in memory -- via
    ``report.to_email_dict()``, which never carries ``gmail_status`` -- never
    by re-reading ``report_path`` off disk. That file may have been written
    before this call (``write_report`` is called unconditionally so a result
    is never lost) and its ``gmail_status`` at that moment is necessarily a
    pre-send placeholder; reading it back here was the original bug (a
    since-fixed local copy could say "not attempted" or, after a later
    rewrite, something stale). Using the in-memory object sidesteps file
    timing entirely rather than choosing a value in the file and hoping the
    caller writes it in the right order.
    """
    credentials_path = Path(credentials_path)
    if not credentials_path.exists():
        return False, f"{NOT_CONFIGURED}: {credentials_path} not found"

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        return False, (
            f"{NOT_CONFIGURED}: install google-api-python-client "
            f"google-auth-httplib2 google-auth-oauthlib"
        )

    token_path = Path(token_path)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Interactive, one-time: opens a browser for consent. Never run
            # this on a headless CI box -- see the setup steps in the
            # league runbook.
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    try:
        service = build("gmail", "v1", credentials=creds)
        service.users().messages().send(
            userId="me", body=_build_message(report, report_path, recipient)
        ).execute()
    except Exception as exc:  # pragma: no cover - network/API failure
        return False, f"EMAIL NOT SENT -- send failed: {exc}"

    return True, "sent"


def _build_message(report: MatchReport, report_path: Path, recipient: str) -> dict:
    import base64
    from email.mime.text import MIMEText

    from police_thief.config.canonical import canonical_json_text

    # The emailed body must be the exact canonical bytes (interop-kit SPEC
    # section 6): a pretty-printed re-serialization is a DIFFERENT byte
    # string from what any hash was computed over, even when every value
    # agrees -- the EX06 near-miss this guards against.
    body = canonical_json_text(report.to_email_dict())
    message = MIMEText(body)
    message["to"] = recipient
    message["subject"] = f"Police-Thief league report: {Path(report_path).stem}"
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return {"raw": raw}

"""
PHASE 13 — Email Notification

Sends a real email via Gmail SMTP whenever Agent 3 flags a `notify` target.

Uses its OWN sender account (separate from the Jira EMAIL variable),
since Gmail requires an App Password for SMTP login, not a normal password.

New .env variables needed (in addition to the ones already there):
    SENDER_EMAIL=your_own_email@gmail.com
    SMTP_APP_PASSWORD=your16characterapppassword
    NOTIFY_RECIPIENT=your_own_email@gmail.com

Run standalone for a quick manual test:
    python notification.py
"""

import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")
NOTIFY_RECIPIENT = os.getenv("NOTIFY_RECIPIENT")


def send_notification(incident_id, subject_line, body_text, recipient=None):
    """
    Sends a plain-text email. Returns True on success, raises on failure
    so the pipeline can decide whether to log it as failed.
    """

    if not SENDER_EMAIL:
        raise ValueError("Missing environment variable: SENDER_EMAIL")

    if not SMTP_APP_PASSWORD:
        raise ValueError("Missing environment variable: SMTP_APP_PASSWORD")

    to_email = recipient or NOTIFY_RECIPIENT

    if not to_email:
        raise ValueError("No recipient set — check NOTIFY_RECIPIENT in .env")

    msg = MIMEText(body_text)
    msg["Subject"] = subject_line
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SMTP_APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())

    print(f"[EMAIL] Notification sent to {to_email} (incident {incident_id})")
    return True


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    send_notification(
        incident_id="INC-TEST-01",
        subject_line="[TEST] EnterpriseMind Lite — Notification Check",
        body_text=(
            "This is a test notification from EnterpriseMind Lite.\n\n"
            "If you're reading this, the SMTP setup is working correctly."
        )
    )
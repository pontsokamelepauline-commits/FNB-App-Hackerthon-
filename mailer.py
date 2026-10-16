import os, smtplib, logging
from email.message import EmailMessage
from urllib.parse import quote

log = logging.getLogger("mali_mode.mailer")

def send_verification(email: str, name: str, token: str):
    base = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    url = f"{base}/verify-email?token={quote(token)}"
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        log.warning("LOCAL DEVELOPMENT ONLY — verification link for %s: %s", email, url)
        return
    msg = EmailMessage()
    msg["Subject"] = "Verify your MALI MODE email"
    msg["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USERNAME", ""))
    msg["To"] = email
    msg.set_content(f"Hello {name},\n\nVerify your MALI MODE email by opening this link:\n{url}\n\nIf you did not create this account, ignore this email.")
    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=15) as server:
        if os.getenv("SMTP_TLS", "true").lower() == "true": server.starttls()
        username = os.getenv("SMTP_USERNAME", "")
        password = os.getenv("SMTP_PASSWORD", "")
        if username: server.login(username, password)
        server.send_message(msg)

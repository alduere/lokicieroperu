"""Brevo (ex-Sendinblue) transactional email client.

Sends an HTML email with the daily PDF as attachment to one or more
recipients. Used by scripts/notify_email.py.

Free tier: 300 emails/day. Auth via api-key header.
Docs: https://developers.brevo.com/reference/sendtransacemail
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Sequence

import requests

logger = logging.getLogger(__name__)

API_URL = "https://api.brevo.com/v3/smtp/email"
DEFAULT_FROM_EMAIL = "notirelevanteperu@noreply.brevo.com"
DEFAULT_FROM_NAME = "NotiRelevantePerú"


class BrevoClient:
    def __init__(
        self,
        api_key: str | None = None,
        from_email: str | None = None,
        from_name: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("BREVO_API_KEY")
        if not self.api_key:
            raise RuntimeError("BREVO_API_KEY env var not set")
        self.from_email = from_email or os.environ.get("EMAIL_FROM", DEFAULT_FROM_EMAIL)
        self.from_name = from_name or os.environ.get("EMAIL_FROM_NAME", DEFAULT_FROM_NAME)

    def send(
        self,
        to: Sequence[str],
        subject: str,
        html: str,
        text: str | None = None,
        attachment: Path | None = None,
    ) -> dict:
        body: dict = {
            "sender": {"email": self.from_email, "name": self.from_name},
            "to": [{"email": addr.strip()} for addr in to if addr.strip()],
            "subject": subject[:200],
            "htmlContent": html,
        }
        if text:
            body["textContent"] = text
        if attachment and attachment.exists():
            data = base64.b64encode(attachment.read_bytes()).decode("ascii")
            body["attachment"] = [{"name": attachment.name, "content": data}]

        r = requests.post(
            API_URL,
            headers={
                "api-key": self.api_key,
                "content-type": "application/json",
                "accept": "application/json",
            },
            json=body,
            timeout=60,
        )
        if r.status_code >= 300:
            logger.error("Brevo error %d: %s", r.status_code, r.text[:500])
            r.raise_for_status()
        logger.info("Brevo email sent to %d recipient(s)", len(body["to"]))
        return r.json() if r.text else {}

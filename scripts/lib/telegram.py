"""Minimal Telegram Bot API client for sending the daily PDF + caption."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"


class TelegramClient:
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        if not self.token or not self.chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID env var missing")

    def send_document(self, pdf_path: Path, caption: str) -> dict:
        url = f"{API_BASE}/bot{self.token}/sendDocument"
        with pdf_path.open("rb") as fh:
            r = requests.post(
                url,
                data={
                    "chat_id": self.chat_id,
                    "caption": caption[:1024],  # TG hard cap
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "false",
                },
                files={"document": (pdf_path.name, fh, "application/pdf")},
                timeout=60,
            )
        r.raise_for_status()
        logger.info("Telegram sendDocument %s ok", pdf_path.name)
        return r.json()

    def send_message(self, text: str) -> dict:
        url = f"{API_BASE}/bot{self.token}/sendMessage"
        r = requests.post(
            url,
            data={
                "chat_id": self.chat_id,
                "text": text[:4096],
                "parse_mode": "HTML",
                "disable_web_page_preview": "false",
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

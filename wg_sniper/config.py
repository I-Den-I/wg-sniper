from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Config:
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    imap_folder: str
    telegram_bot_token: str
    telegram_chat_id: int
    db_path: Path
    log_level: str
    wg_sender_filter: str


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def load_config() -> Config:
    load_dotenv()
    return Config(
        imap_host=os.environ.get("IMAP_HOST", "imap.gmail.com"),
        imap_port=int(os.environ.get("IMAP_PORT", "993")),
        imap_user=_require("IMAP_USER"),
        imap_password=_require("IMAP_PASSWORD"),
        imap_folder=os.environ.get("IMAP_FOLDER", "INBOX"),
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=int(_require("TELEGRAM_CHAT_ID")),
        db_path=Path(os.environ.get("DB_PATH", "./wg_sniper.db")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        wg_sender_filter=os.environ.get("WG_SENDER_FILTER", "wg-gesucht.de"),
    )

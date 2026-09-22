from __future__ import annotations

import asyncio
import email
import logging
from email.message import Message
from typing import Awaitable, Callable

from aioimaplib import aioimaplib

log = logging.getLogger(__name__)

EmailCallback = Callable[[Message], Awaitable[None]]

IDLE_TIMEOUT = 25 * 60
RECONNECT_DELAY = 30


async def _process_unseen(client: aioimaplib.IMAP4_SSL, on_email: EmailCallback,
                          sender_filter: str) -> None:
    search_key = f'(UNSEEN FROM "{sender_filter}")'
    status, data = await client.search(search_key)
    if status != "OK" or not data or not data[0]:
        return
    ids = data[0].split()
    if not ids:
        return
    log.info("processing %d new message(s) from %s", len(ids), sender_filter)
    for uid in ids:
        uid_str = uid.decode() if isinstance(uid, bytes) else uid
        status, msg_data = await client.fetch(uid_str, "(RFC822)")
        if status != "OK" or not msg_data:
            log.warning("fetch failed for uid=%s", uid_str)
            continue
        raw = None
        for item in msg_data:
            if isinstance(item, (bytes, bytearray)) and len(item) > 100:
                raw = bytes(item)
                break
        if raw is None:
            continue
        try:
            msg = email.message_from_bytes(raw)
            await on_email(msg)
        except Exception:
            log.exception("callback failed for uid=%s", uid_str)


async def _one_session(host: str, port: int, user: str, password: str,
                       folder: str, on_email: EmailCallback, sender_filter: str) -> None:
    client = aioimaplib.IMAP4_SSL(host=host, port=port, timeout=60)
    await client.wait_hello_from_server()
    await client.login(user, password)
    try:
        await client.select(folder)
        log.info("connected to %s as %s, folder=%s", host, user, folder)

        await _process_unseen(client, on_email, sender_filter)

        while True:
            idle = await client.idle_start(timeout=IDLE_TIMEOUT)
            try:
                await client.wait_server_push()
            except asyncio.TimeoutError:
                pass
            client.idle_done()
            try:
                await asyncio.wait_for(idle, timeout=10)
            except asyncio.TimeoutError:
                log.warning("idle task did not complete cleanly")
            await _process_unseen(client, on_email, sender_filter)
    finally:
        try:
            await client.logout()
        except Exception:
            pass


async def run_listener(host: str, port: int, user: str, password: str,
                       folder: str, on_email: EmailCallback, sender_filter: str) -> None:
    while True:
        try:
            await _one_session(host, port, user, password, folder, on_email, sender_filter)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("IMAP session failed, reconnect in %ds", RECONNECT_DELAY)
        await asyncio.sleep(RECONNECT_DELAY)

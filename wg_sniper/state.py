from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiosqlite

from . import db as dbmod
from .i18n import DEFAULT_LANG, Lang, normalize


@dataclass
class State:
    db_path: Path
    started_at: float = field(default_factory=time.time)
    git_sha: str = "unknown"
    git_branch: str = "unknown"
    _lang: Lang = DEFAULT_LANG
    _paused: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def load(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            self._lang = normalize(await dbmod.get_pref(db, "lang", DEFAULT_LANG))
            self._paused = (await dbmod.get_pref(db, "paused", "0")) == "1"

    @property
    def lang(self) -> Lang:
        return self._lang

    @property
    def paused(self) -> bool:
        return self._paused

    async def set_lang(self, lang: Lang) -> None:
        async with self._lock:
            self._lang = lang
            async with aiosqlite.connect(self.db_path) as db:
                await dbmod.set_pref(db, "lang", lang)

    async def toggle_lang(self) -> Lang:
        new_lang: Lang = "en" if self._lang == "uk" else "uk"
        await self.set_lang(new_lang)
        return new_lang

    async def set_paused(self, paused: bool) -> None:
        async with self._lock:
            self._paused = paused
            async with aiosqlite.connect(self.db_path) as db:
                await dbmod.set_pref(db, "paused", "1" if paused else "0")

    def uptime_str(self) -> str:
        secs = int(time.time() - self.started_at)
        d, r = divmod(secs, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)
        parts = []
        if d: parts.append(f"{d}d")
        if h: parts.append(f"{h}h")
        if m: parts.append(f"{m}m")
        parts.append(f"{s}s")
        return " ".join(parts)

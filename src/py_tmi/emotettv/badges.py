from __future__ import annotations

import asyncio
from typing import Dict, Iterable, List, Optional

from .clients.bttv import get_bttv_badges
from .clients.ffz import get_ffz_badges
from .clients.unttv import get_twitch_channel_badges, get_twitch_global_badges
from .models import (
    BadgesResult,
    BttvBadgeEntry,
    FfzBadgeEntry,
    ParsedBadge,
    TwitchBadgeEntry,
)
from .options import ParserOptions, load_options

BadgeVersions = Dict[str, str]


class BadgesParserProtocol:
    provider: str

    async def load(self, channel_id: Optional[str], force: bool = False) -> None:
        ...

    async def parse(
        self,
        badges: Optional[BadgeVersions],
        username: Optional[str],
        channel_id: Optional[str],
    ) -> List[ParsedBadge]:
        ...


class TwitchBadgesParser(BadgesParserProtocol):
    provider = "twitch"

    def __init__(self) -> None:
        self._cache: List[TwitchBadgeEntry] = []
        self._lock = asyncio.Lock()

    async def load(self, channel_id: Optional[str], force: bool = False) -> None:
        async with self._lock:
            if not force and self._has_cache(channel_id):
                return

            channel_entries: List[TwitchBadgeEntry] = []
            if channel_id:
                channel_entries = await get_twitch_channel_badges(channel_id)
            global_entries = await get_twitch_global_badges()

            self._cache = [
                entry
                for entry in self._cache
                if entry.channel_id not in {channel_id, None}
            ]
            self._cache.extend(channel_entries)
            self._cache.extend(global_entries)

    def _has_cache(self, channel_id: Optional[str]) -> bool:
        # Ensure both global and channel badges exist for the scope.
        has_global = any(entry.channel_id is None for entry in self._cache)
        if channel_id is None:
            return has_global
        has_channel = any(entry.channel_id == channel_id for entry in self._cache)
        return has_global and has_channel

    async def parse(
        self,
        badges: Optional[BadgeVersions],
        username: Optional[str],
        channel_id: Optional[str],
    ) -> List[ParsedBadge]:
        await self.load(channel_id, False)
        if not badges:
            return []

        parsed: List[ParsedBadge] = []
        for badge_id, version in badges.items():
            if not isinstance(version, str):
                continue
            entry = self._find_entry(badge_id, version, channel_id)
            if not entry:
                continue
            parsed.append(
                ParsedBadge(
                    id=entry.id,
                    title=entry.title,
                    images=list(entry.images),
                )
            )
        return parsed

    def _find_entry(
        self, badge_id: str, version_id: str, channel_id: Optional[str]
    ) -> Optional[TwitchBadgeEntry]:
        for scope in (channel_id, None):
            for entry in self._cache:
                if (
                    entry.id == badge_id
                    and entry.version_id == version_id
                    and entry.channel_id == scope
                ):
                    return entry
        return None


class BttvBadgesParser(BadgesParserProtocol):
    provider = "bttv"

    def __init__(self) -> None:
        self._cache: List[BttvBadgeEntry] = []
        self._lock = asyncio.Lock()

    async def load(self, channel_id: Optional[str], force: bool = False) -> None:
        async with self._lock:
            if self._cache and not force:
                return
            self._cache = await get_bttv_badges()

    async def parse(
        self,
        badges: Optional[BadgeVersions],
        username: Optional[str],
        channel_id: Optional[str],
    ) -> List[ParsedBadge]:
        await self.load(None, False)
        if not username:
            return []
        return [
            ParsedBadge(
                id=badge.id,
                title=badge.title,
                images=list(badge.images),
            )
            for badge in self._cache
            if badge.username == username
        ]


class FfzBadgesParser(BadgesParserProtocol):
    provider = "ffz"

    def __init__(self) -> None:
        self._badges: List[FfzBadgeEntry] = []
        self._badge_users: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()

    async def load(self, channel_id: Optional[str], force: bool = False) -> None:
        async with self._lock:
            if self._badges and self._badge_users and not force:
                return
            badges, users = await get_ffz_badges()
            self._badges = badges
            self._badge_users = users

    async def parse(
        self,
        badges: Optional[BadgeVersions],
        username: Optional[str],
        channel_id: Optional[str],
    ) -> List[ParsedBadge]:
        await self.load(None, False)
        if not username:
            return []

        parsed: List[ParsedBadge] = []
        for badge_id, users in self._badge_users.items():
            if username not in users:
                continue
            entry = self._find_badge(badge_id)
            if not entry:
                continue
            parsed.append(
                ParsedBadge(
                    id=entry.id,
                    title=entry.title,
                    images=list(entry.images),
                    slot=entry.slot,
                    replaces=entry.replaces,
                    color=entry.color,
                )
            )
        return parsed

    def _find_badge(self, badge_id: str) -> Optional[FfzBadgeEntry]:
        for badge in self._badges:
            if badge.id == badge_id:
                return badge
        return None


BADGE_PARSERS: List[BadgesParserProtocol] = [
    TwitchBadgesParser(),
    BttvBadgesParser(),
    FfzBadgesParser(),
]


async def parse_badges(
    badges: Optional[BadgeVersions],
    username: Optional[str] = None,
    options: Optional[object] = None,
) -> BadgesResult:
    opts = load_options(options)
    parsed: List[ParsedBadge] = []

    for parser in BADGE_PARSERS:
        if not opts.is_enabled(parser.provider):
            continue
        parsed.extend(await parser.parse(badges, username, opts.channel_id))

    return BadgesResult(_replace_badges(parsed))


async def reload_badges(options: Optional[object] = None) -> None:
    opts = load_options(options)
    for parser in BADGE_PARSERS:
        if not opts.is_enabled(parser.provider):
            continue
        await parser.load(opts.channel_id, True)


def _replace_badges(badges: List[ParsedBadge]) -> List[ParsedBadge]:
    result = list(badges)
    for idx, badge in enumerate(badges):
        if not badge.replaces:
            continue
        replace_idx = next(
            (i for i, existing in enumerate(result) if existing.id == badge.replaces),
            -1,
        )
        if replace_idx >= 0:
            result[replace_idx] = badge
            result = [item for i, item in enumerate(result) if i != idx]
    return result

from __future__ import annotations

from typing import List, Optional

from .._http import fetch_json
from ..models import BttvBadgeEntry, EmoteEntry

BASE_URL = "https://api.betterttv.net/3"


async def get_bttv_channel_emotes(channel_id: Optional[str]) -> List[EmoteEntry]:
    if not channel_id:
        return []

    data = await fetch_json(f"{BASE_URL}/cached/users/twitch/{channel_id}")
    if not isinstance(data, dict):
        return []

    emotes: List[EmoteEntry] = []
    for key in ("channelEmotes", "sharedEmotes"):
        for item in data.get(key, []) or []:
            emote_id = str(item.get("id") or "")
            code = item.get("code")
            if not emote_id or not isinstance(code, str):
                continue
            emotes.append(
                EmoteEntry(
                    id=emote_id,
                    code=code,
                    channel_id=channel_id,
                )
            )
    return emotes


async def get_bttv_global_emotes(_: Optional[str] = None) -> List[EmoteEntry]:
    data = await fetch_json(f"{BASE_URL}/cached/emotes/global")
    if not isinstance(data, list):
        return []

    emotes: List[EmoteEntry] = []
    for item in data:
        emote_id = str(item.get("id") or "")
        code = item.get("code")
        if not emote_id or not isinstance(code, str):
            continue
        emotes.append(
            EmoteEntry(
                id=emote_id,
                code=code,
                channel_id=None,
            )
        )
    return emotes


async def get_bttv_badges() -> List[BttvBadgeEntry]:
    data = await fetch_json(f"{BASE_URL}/cached/badges/twitch")
    if not isinstance(data, list):
        return []

    badges: List[BttvBadgeEntry] = []
    for item in data:
        badge_data = item.get("badge") if isinstance(item, dict) else None
        username = item.get("name") if isinstance(item, dict) else None
        if not isinstance(badge_data, dict) or not isinstance(username, str):
            continue
        svg = badge_data.get("svg")
        badge_type = badge_data.get("type")
        description = badge_data.get("description")
        if not svg or badge_type is None or not isinstance(description, str):
            continue
        badges.append(
            BttvBadgeEntry(
                id=str(badge_type),
                username=username,
                title=description,
                images=[svg],
            )
        )
    return badges

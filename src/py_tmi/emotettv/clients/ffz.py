from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .._http import fetch_json
from ..models import EmoteEntry, FfzBadgeEntry

BASE_URL = "https://api.frankerfacez.com/v1"


async def get_ffz_channel_emotes(channel_id: Optional[str]) -> List[EmoteEntry]:
    if not channel_id:
        return []

    data = await fetch_json(f"{BASE_URL}/room/id/{channel_id}")
    if not isinstance(data, dict):
        return []

    sets = data.get("sets")
    if not isinstance(sets, dict):
        return []

    emotes: List[EmoteEntry] = []
    for emote_set in sets.values():
        emoticons = emote_set.get("emoticons") if isinstance(emote_set, dict) else None
        if not isinstance(emoticons, list):
            continue
        for emote in emoticons:
            emote_id = emote.get("id") if isinstance(emote, dict) else None
            code = emote.get("name") if isinstance(emote, dict) else None
            if emote_id is None or not isinstance(code, str):
                continue
            emotes.append(
                EmoteEntry(
                    id=str(emote_id),
                    code=code,
                    channel_id=channel_id,
                )
            )
    return emotes


async def get_ffz_global_emotes(_: Optional[str] = None) -> List[EmoteEntry]:
    data = await fetch_json(f"{BASE_URL}/set/global")
    if not isinstance(data, dict):
        return []

    sets = data.get("sets")
    if not isinstance(sets, dict):
        return []

    emotes: List[EmoteEntry] = []
    for emote_set in sets.values():
        emoticons = emote_set.get("emoticons") if isinstance(emote_set, dict) else None
        if not isinstance(emoticons, list):
            continue
        for emote in emoticons:
            emote_id = emote.get("id") if isinstance(emote, dict) else None
            code = emote.get("name") if isinstance(emote, dict) else None
            if emote_id is None or not isinstance(code, str):
                continue
            emotes.append(
                EmoteEntry(
                    id=str(emote_id),
                    code=code,
                    channel_id=None,
                )
            )
    return emotes


async def get_ffz_badges() -> Tuple[List[FfzBadgeEntry], Dict[str, List[str]]]:
    data = await fetch_json(f"{BASE_URL}/badges")
    if not isinstance(data, dict):
        return [], {}

    badges_raw = data.get("badges")
    users_raw = data.get("users")

    badges: List[FfzBadgeEntry] = []
    if isinstance(badges_raw, list):
        for item in badges_raw:
            if not isinstance(item, dict):
                continue
            badge_id = item.get("id")
            title = item.get("title")
            color = item.get("color")
            slot = item.get("slot")
            replaces = item.get("replaces")
            urls = item.get("urls")
            if badge_id is None or not isinstance(title, str) or not isinstance(urls, dict):
                continue
            images = [
                str(url)
                for _, url in sorted(urls.items(), key=lambda pair: pair[0])
                if isinstance(url, str)
            ]
            badges.append(
                FfzBadgeEntry(
                    id=str(badge_id),
                    title=title,
                    images=images,
                    slot=int(slot) if isinstance(slot, int) else None,
                    replaces=str(replaces) if replaces else None,
                    color=str(color) if isinstance(color, str) else None,
                )
            )

    users: Dict[str, List[str]] = {}
    if isinstance(users_raw, dict):
        for badge_id, usernames in users_raw.items():
            if isinstance(usernames, list):
                users[str(badge_id)] = [
                    str(username) for username in usernames if isinstance(username, str)
                ]

    return badges, users

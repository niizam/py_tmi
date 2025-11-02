from __future__ import annotations

from typing import List, Optional

from .._http import fetch_json
from ..models import EmoteEntry

BASE_URL = "https://7tv.io/v3"


def _is_zero_width(flags: object) -> bool:
    try:
        return bool(int(flags) & 256)
    except (TypeError, ValueError):
        return False


async def get_seventv_channel_emotes(channel_id: Optional[str]) -> List[EmoteEntry]:
    if not channel_id:
        return []

    data = await fetch_json(f"{BASE_URL}/users/twitch/{channel_id}")
    if not isinstance(data, dict):
        return []

    emote_set = data.get("emote_set")
    if not isinstance(emote_set, dict):
        return []

    emote_list = emote_set.get("emotes")
    if not isinstance(emote_list, list):
        return []

    emotes: List[EmoteEntry] = []
    for item in emote_list:
        if not isinstance(item, dict):
            continue
        emote_id = item.get("id")
        code = item.get("name")
        if not isinstance(emote_id, str) or not isinstance(code, str):
            continue
        emotes.append(
            EmoteEntry(
                id=emote_id,
                code=code,
                channel_id=channel_id,
                is_zero_width=_is_zero_width(item.get("flags")),
            )
        )
    return emotes


async def get_seventv_global_emotes() -> List[EmoteEntry]:
    data = await fetch_json(f"{BASE_URL}/emote-sets/global")
    if not isinstance(data, dict):
        return []

    emote_list = data.get("emotes")
    if not isinstance(emote_list, list):
        return []

    emotes: List[EmoteEntry] = []
    for item in emote_list:
        if not isinstance(item, dict):
            continue
        emote_id = item.get("id")
        code = item.get("name")
        if not isinstance(emote_id, str) or not isinstance(code, str):
            continue
        emotes.append(
            EmoteEntry(
                id=emote_id,
                code=code,
                channel_id=None,
                is_zero_width=_is_zero_width(item.get("flags")),
            )
        )
    return emotes

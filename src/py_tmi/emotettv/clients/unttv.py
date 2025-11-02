from __future__ import annotations

from typing import List, Optional

from .._http import fetch_json
from ..models import TwitchBadgeEntry

BASE_URL = "https://unttv.vercel.app"


async def get_twitch_channel_badges(channel_id: Optional[str]) -> List[TwitchBadgeEntry]:
    if not channel_id:
        return []
    data = await fetch_json(f"{BASE_URL}/badges/channel/{channel_id}")
    return _format_badges(data, channel_id)


async def get_twitch_global_badges() -> List[TwitchBadgeEntry]:
    data = await fetch_json(f"{BASE_URL}/badges/global")
    return _format_badges(data, None)


def _format_badges(data: object, channel_id: Optional[str]) -> List[TwitchBadgeEntry]:
    if not isinstance(data, list):
        return []

    badges: List[TwitchBadgeEntry] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        badge_id = item.get("id")
        versions = item.get("versions")
        if not isinstance(badge_id, str) or not isinstance(versions, list):
            continue
        for version in versions:
            if not isinstance(version, dict):
                continue
            version_id = version.get("id")
            title = version.get("title")
            image_1x = version.get("image_url_1x")
            image_2x = version.get("image_url_2x")
            image_4x = version.get("image_url_4x")
            if not all(
                isinstance(val, str)
                for val in (version_id, title, image_1x, image_2x, image_4x)
            ):
                continue
            version_id_str = version_id
            title_str = title
            images = [image_1x, image_2x, image_4x]
            badges.append(
                TwitchBadgeEntry(
                    id=badge_id,
                    version_id=version_id_str,
                    channel_id=channel_id,
                    title=title_str,
                    images=images,
                )
            )
    return badges

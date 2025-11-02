import asyncio

import pytest

from py_tmi.emotettv import parse_badges, parse_emotes
from py_tmi.emotettv.badges import BADGE_PARSERS
from py_tmi.emotettv.emotes import EMOTE_PARSERS
from py_tmi.emotettv.models import EmoteEntry, FfzBadgeEntry, TwitchBadgeEntry


def _get_parser(parsers, provider):
    for parser in parsers:
        if getattr(parser, "provider", None) == provider:
            return parser
    raise AssertionError(f"Parser '{provider}' not found")


def test_parse_emotes_with_bttv(monkeypatch):
    bttv_parser = _get_parser(EMOTE_PARSERS, "bttv")
    original_cache = list(getattr(bttv_parser, "_cache", []))
    original_loaders = list(getattr(bttv_parser, "_loaders", []))

    async def fake_channel_loader(channel_id):
        return [
            EmoteEntry(
                id="bttv123",
                code="OMEGALUL",
                channel_id=channel_id,
            )
        ]

    async def fake_global_loader(channel_id):
        return []

    bttv_parser._cache = []
    bttv_parser._loaders = [fake_channel_loader, fake_global_loader]

    try:
        result = asyncio.run(
            parse_emotes(
                "OMEGALUL",
                options={
                    "channel_id": "12345",
                    "providers": {"ffz": False, "seventv": False},
                },
            )
        )
    finally:
        bttv_parser._cache = original_cache
        bttv_parser._loaders = original_loaders

    words = result.to_array()
    assert len(words) == 1
    assert words[0].emote is not None
    html = result.to_html(scale=2)
    assert "cdn.betterttv.net/emote/bttv123/3x" in html


def test_parse_emotes_seventv_overlays():
    seventv_parser = _get_parser(EMOTE_PARSERS, "seventv")
    original_cache = list(getattr(seventv_parser, "_cache", []))
    original_loaders = list(getattr(seventv_parser, "_loaders", []))

    async def fake_loader(channel_id):
        return [
            EmoteEntry(
                id="stv-base",
                code="BASE",
                channel_id=channel_id,
                is_zero_width=False,
            ),
            EmoteEntry(
                id="stv-overlay",
                code="OVERLAY",
                channel_id=channel_id,
                is_zero_width=True,
            ),
        ]

    seventv_parser._cache = []
    seventv_parser._loaders = [fake_loader]

    try:
        result = asyncio.run(
            parse_emotes(
                "BASE OVERLAY",
                options={
                    "channel_id": "777",
                    "providers": {
                        "twitch": False,
                        "bttv": False,
                        "ffz": False,
                        "seventv": True,
                    },
                },
            )
        )
    finally:
        seventv_parser._cache = original_cache
        seventv_parser._loaders = original_loaders

    words = result.to_array()
    assert len(words) == 1
    overlays = words[0].emote.overlays  # type: ignore[union-attr]
    assert overlays
    assert overlays[0].images[0].endswith("stv-overlay/1x.webp")


def test_parse_badges_with_replacement():
    twitch_parser = _get_parser(BADGE_PARSERS, "twitch")
    ffz_parser = _get_parser(BADGE_PARSERS, "ffz")

    original_twitch_cache = list(getattr(twitch_parser, "_cache", []))
    original_ffz_badges = list(getattr(ffz_parser, "_badges", []))
    original_ffz_users = dict(getattr(ffz_parser, "_badge_users", {}))

    twitch_parser._cache = [
        TwitchBadgeEntry(
            id="vip",
            version_id="1",
            channel_id=None,
            title="VIP",
            images=["vip1", "vip2", "vip4"],
        )
    ]
    ffz_parser._badges = [
        FfzBadgeEntry(
            id="ffz-special",
            title="Special",
            images=["ffz1", "ffz2"],
            slot=1,
            replaces="vip",
            color="#fff",
        )
    ]
    ffz_parser._badge_users = {"ffz-special": ["user1"]}

    try:
        result = asyncio.run(
            parse_badges(
                {"vip": "1"},
                username="user1",
                options={"providers": {"bttv": False}},
            )
        )
    finally:
        twitch_parser._cache = original_twitch_cache
        ffz_parser._badges = original_ffz_badges
        ffz_parser._badge_users = original_ffz_users

    badges = result.to_array()
    assert len(badges) == 1
    badge = badges[0]
    assert badge.id == "ffz-special"
    assert badge.replaces == "vip"
    html = result.to_html(scale=1)
    assert "ffz2" in html

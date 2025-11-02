from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .utils import escape_html, get_scale_value


@dataclass(slots=True)
class EmoteOverlay:
    images: List[str]
    alt: str


@dataclass(slots=True)
class EmoteRender:
    images: List[str]
    overlays: List[EmoteOverlay] = field(default_factory=list)
    is_zero_width: bool = False


@dataclass(slots=True)
class ParsedEmoteWord:
    content: str
    position: str
    emote: Optional[EmoteRender] = None


class EmotesResult:
    """Wrapper around the parsed message to match emotettv's API."""

    __slots__ = ("_message",)

    def __init__(self, message: List[ParsedEmoteWord]):
        self._message = message

    def to_array(self) -> List[ParsedEmoteWord]:
        return list(self._message)

    def to_html(
        self,
        scale: int = 1,
        inline_styles: bool = True,
        escape_html_content: bool = True,
    ) -> str:
        pieces: List[str] = []
        for word in self._message:
            if not word.emote:
                content = escape_html(word.content) if escape_html_content else word.content
                pieces.append(content)
                continue

            emote = word.emote
            url = get_scale_value(emote.images, scale)
            height = get_scale_value([24, 28, 32, 48], scale)
            offset = -get_scale_value([6, 8, 10, 20], scale)
            img_style = (
                f' style="height:{height}px;margin-bottom:{offset}px"'
                if inline_styles
                else ""
            )
            figure_style = (
                ' style="position:relative;display:inline-block;margin:0"'
                if inline_styles
                else ""
            )

            overlays_html = ""
            if emote.overlays:
                overlay_style = (
                    f' style="position:absolute;top:0;left:0;height:{height}px"'
                    if inline_styles
                    else ""
                )
                overlays_html = "".join(
                    f'<img class="emotettv-overlay"{overlay_style} src="{get_scale_value(overlay.images, scale)}" alt="{escape_html(overlay.alt)}" />'
                    for overlay in emote.overlays
                )

            pieces.append(
                f'<figure class="emotettv-emote"{figure_style}>'
                f'<img class="emotettv-img" src="{url}" alt="{escape_html(word.content)}"{img_style} />'
                f"{overlays_html}"
                "</figure>"
            )
        return " ".join(pieces)


@dataclass(slots=True)
class ParsedBadge:
    id: str
    title: str
    images: List[str]
    slot: Optional[int] = None
    replaces: Optional[str] = None
    color: Optional[str] = None


class BadgesResult:
    """Wrapper for parsed badges with HTML helper."""

    __slots__ = ("_badges",)

    def __init__(self, badges: List[ParsedBadge]):
        self._badges = badges

    def to_array(self) -> List[ParsedBadge]:
        return list(self._badges)

    def to_html(self, scale: int = 1, inline_styles: bool = True) -> str:
        pieces: List[str] = []
        for badge in self._badges:
            url = get_scale_value(badge.images, scale)
            height = get_scale_value([18, 20, 22], scale)
            offset = -get_scale_value([4, 5, 6], scale)
            style_components: List[str] = []
            if inline_styles:
                style_components.append(f"height:{height}px")
                style_components.append(f"margin-bottom:{offset}px")
                if badge.color:
                    style_components.append("border-radius:2px")
                    style_components.append(f"background-color:{badge.color}")
            style_attr = (
                f' style="{";".join(style_components)}"' if style_components else ""
            )
            pieces.append(
                f'<img class="emotettv-badge"{style_attr} src="{url}" alt="{escape_html(badge.title)}" />'
            )
        return " ".join(pieces)


@dataclass(slots=True)
class EmoteEntry:
    id: str
    code: str
    channel_id: Optional[str]
    is_zero_width: bool = False


@dataclass(slots=True)
class TwitchBadgeEntry:
    id: str
    version_id: str
    channel_id: Optional[str]
    title: str
    images: List[str]


@dataclass(slots=True)
class BttvBadgeEntry:
    id: str
    username: str
    title: str
    images: List[str]


@dataclass(slots=True)
class FfzBadgeEntry:
    id: str
    title: str
    images: List[str]
    slot: Optional[int] = None
    replaces: Optional[str] = None
    color: Optional[str] = None

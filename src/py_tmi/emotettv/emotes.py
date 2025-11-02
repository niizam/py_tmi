from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Dict, Iterable, List, Optional, Sequence

from .clients.bttv import get_bttv_channel_emotes, get_bttv_global_emotes
from .clients.ffz import get_ffz_channel_emotes, get_ffz_global_emotes
from .clients.seventv import get_seventv_channel_emotes, get_seventv_global_emotes
from .models import EmoteEntry, EmoteOverlay, EmoteRender, EmotesResult, ParsedEmoteWord
from .options import ParserOptions, load_options

EmotePositions = Dict[str, Sequence[str]]


class EmoteParserProtocol:
    provider: str

    async def load(self, channel_id: Optional[str], force: bool = False) -> None:
        ...

    async def parse(
        self,
        message: List[ParsedEmoteWord],
        emote_positions: EmotePositions,
        options: ParserOptions,
    ) -> List[ParsedEmoteWord]:
        ...


EmoteLoader = Callable[[Optional[str]], Awaitable[List[EmoteEntry]]]
URLBuilder = Callable[[str], List[str]]


class CachedEmoteParser(EmoteParserProtocol):
    def __init__(
        self,
        provider: str,
        loaders: Iterable[EmoteLoader],
        url_builder: URLBuilder,
    ) -> None:
        self.provider = provider
        self._loaders = list(loaders)
        self._url_builder = url_builder
        self._cache: List[EmoteEntry] = []
        self._lock = asyncio.Lock()

    async def load(self, channel_id: Optional[str], force: bool = False) -> None:
        async with self._lock:
            if not force and self._has_cache(channel_id):
                return
            fresh: List[EmoteEntry] = []
            for loader in self._loaders:
                fresh.extend(await loader(channel_id))
            # Drop old entries for the same scope before appending the refreshed list.
            self._cache = [
                entry
                for entry in self._cache
                if entry.channel_id != channel_id
            ]
            self._cache.extend(fresh)

    def _has_cache(self, channel_id: Optional[str]) -> bool:
        return any(entry.channel_id == channel_id for entry in self._cache)

    async def parse(
        self,
        message: List[ParsedEmoteWord],
        emote_positions: EmotePositions,
        options: ParserOptions,
    ) -> List[ParsedEmoteWord]:
        await self.load(options.channel_id, False)
        for word in message:
            if word.emote:
                continue
            entry = self._find_entry(word.content, options.channel_id)
            if not entry:
                continue
            word.emote = EmoteRender(
                images=self._url_builder(entry.id),
                is_zero_width=entry.is_zero_width,
            )
        return message

    def _find_entry(
        self, code: str, channel_id: Optional[str]
    ) -> Optional[EmoteEntry]:
        # Prefer channel specific entries, fall back to global.
        for scope in (channel_id, None):
            for entry in self._cache:
                if entry.code == code and entry.channel_id == scope:
                    return entry
        return None


class TwitchEmoteParser(EmoteParserProtocol):
    provider = "twitch"

    async def load(self, channel_id: Optional[str], force: bool = False) -> None:  # noqa: D401
        return None

    async def parse(
        self,
        message: List[ParsedEmoteWord],
        emote_positions: EmotePositions,
        options: ParserOptions,
    ) -> List[ParsedEmoteWord]:

        if not emote_positions:
            return message

        for word in message:
            if word.emote:
                continue
            emote_id = _find_emote_id_by_position(emote_positions, word.position)
            if not emote_id:
                continue
            word.emote = EmoteRender(
                images=[
                    f"https://static-cdn.jtvnw.net/emoticons/v2/{emote_id}/default/dark/{scale}"
                    for scale in ("1.0", "2.0", "3.0")
                ]
            )
        return message


class SeventvOverlayParser(EmoteParserProtocol):
    provider = "seventv"

    async def load(self, channel_id: Optional[str], force: bool = False) -> None:
        return None

    async def parse(
        self,
        message: List[ParsedEmoteWord],
        emote_positions: EmotePositions,
        options: ParserOptions,
    ) -> List[ParsedEmoteWord]:
        result: List[ParsedEmoteWord] = []
        i = 0
        total = len(message)
        while i < total:
            word = message[i]
            if word.emote and not word.emote.is_zero_width:
                overlays = list(word.emote.overlays)
                j = i + 1
                while j < total:
                    next_word = message[j]
                    if next_word.emote and next_word.emote.is_zero_width:
                        overlays.append(
                            EmoteOverlay(
                                images=list(next_word.emote.images),
                                alt=next_word.content,
                            )
                        )
                        j += 1
                    else:
                        break
                if overlays:
                    word.emote.overlays = overlays
                result.append(word)
                i = j
                continue
            result.append(word)
            i += 1
        return result


EMOTE_PARSERS: List[EmoteParserProtocol] = [
    TwitchEmoteParser(),
    CachedEmoteParser(
        "bttv",
        [get_bttv_channel_emotes, get_bttv_global_emotes],
        lambda emote_id: [
            f"https://cdn.betterttv.net/emote/{emote_id}/{scale}"
            for scale in ("1x", "2x", "3x")
        ],
    ),
    CachedEmoteParser(
        "ffz",
        [get_ffz_channel_emotes, get_ffz_global_emotes],
        lambda emote_id: [
            f"https://cdn.frankerfacez.com/emote/{emote_id}/{scale}"
            for scale in ("1", "2", "4")
        ],
    ),
    CachedEmoteParser(
        "seventv",
        [get_seventv_channel_emotes, get_seventv_global_emotes],
        lambda emote_id: [
            f"https://cdn.7tv.app/emote/{emote_id}/{scale}.webp"
            for scale in ("1x", "2x", "3x", "4x")
        ],
    ),
    SeventvOverlayParser(),
]


async def parse_emotes(
    message: str,
    emote_positions: Optional[EmotePositions] = None,
    options: Optional[object] = None,
) -> EmotesResult:
    parsed_message = _prepare_message(message)
    opts = load_options(options)
    positions = emote_positions or {}

    for parser in EMOTE_PARSERS:
        if not opts.is_enabled(parser.provider):
            continue
        parsed_message = await parser.parse(parsed_message, positions, opts)

    return EmotesResult(parsed_message)


async def reload_emotes(options: Optional[object] = None) -> None:
    opts = load_options(options)
    for parser in EMOTE_PARSERS:
        if not opts.is_enabled(parser.provider):
            continue
        await parser.load(opts.channel_id, True)


def _prepare_message(message: str) -> List[ParsedEmoteWord]:
    words: List[ParsedEmoteWord] = []
    current = 0
    for chunk in message.split(" "):
        end = current + len(chunk) - 1
        position = f"{current}-{end}"
        words.append(ParsedEmoteWord(content=chunk, position=position))
        current += len(chunk) + 1
    return words


def _find_emote_id_by_position(
    emote_positions: EmotePositions, position: str
) -> Optional[str]:
    for emote_id, positions in emote_positions.items():
        if position in positions:
            return emote_id
    return None

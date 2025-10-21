from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from . import utils

NONSPACE_REGEX = re.compile(r"\S+")


@dataclass(slots=True)
class IRCMessage:
    raw: str
    tags: Dict[str, object] = field(default_factory=dict)
    prefix: Optional[str] = None
    command: Optional[str] = None
    params: List[str] = field(default_factory=list)

    def param(self, index: int, default: Optional[str] = None) -> Optional[str]:
        try:
            return self.params[index]
        except IndexError:
            return default


def _parse_complex_tag(
    tags: Dict[str, object], key: str, separator_a: str = ",", separator_b: str = "/", separator_c: Optional[str] = None
) -> Dict[str, object]:
    raw = tags.get(key)
    if raw is None:
        return tags

    if raw is True:
        tags[key] = None
        tags[f"{key}-raw"] = None
        return tags

    if not isinstance(raw, str):
        tags[key] = {}
        tags[f"{key}-raw"] = None
        return tags

    tags[f"{key}-raw"] = raw
    parsed: Dict[str, object] = {}

    for part in raw.split(separator_a):
        segments = part.split(separator_b)
        key_segment = segments[0]
        value_segment = segments[1] if len(segments) > 1 else None
        if separator_c is not None and value_segment:
            parsed[key_segment] = value_segment.split(separator_c)
        else:
            parsed[key_segment] = value_segment or None
    tags[key] = parsed
    return tags


def parse_badges(tags: Dict[str, object]) -> Dict[str, object]:
    return _parse_complex_tag(tags, "badges")


def parse_badge_info(tags: Dict[str, object]) -> Dict[str, object]:
    return _parse_complex_tag(tags, "badge-info")


def parse_emotes(tags: Dict[str, object]) -> Dict[str, object]:
    return _parse_complex_tag(tags, "emotes", "/", ":", ",")


def emote_regex(message: str, code: str, emote_id: str, accumulator: Dict[str, List[Tuple[int, int]]]) -> None:
    pattern = re.compile(rf"(\b|^|\s){re.escape(utils.unescape_html(code))}(\b|$|\s)")
    for match in NONSPACE_REGEX.finditer(message):
        if pattern.search(match.group(0)):
            accumulator.setdefault(emote_id, []).append((match.start(), match.end() - 1))


def emote_string(message: str, code: str, emote_id: str, accumulator: Dict[str, List[Tuple[int, int]]]) -> None:
    for match in NONSPACE_REGEX.finditer(message):
        if match.group(0) == utils.unescape_html(code):
            accumulator.setdefault(emote_id, []).append((match.start(), match.end() - 1))


def transform_emotes(emotes: Dict[str, Iterable[Tuple[int, int]]]) -> str:
    parts: List[str] = []
    for emote_id, positions in emotes.items():
        joined = ",".join(f"{start}-{end}" for start, end in positions)
        parts.append(f"{emote_id}:{joined}")
    return "/".join(parts)


def form_tags(tags: Optional[Dict[str, object]]) -> Optional[str]:
    if not tags:
        return None
    components = []
    for key, value in tags.items():
        escaped_key = utils.escape_irc(str(key))
        escaped_value = utils.escape_irc("" if value is None else str(value))
        components.append(f"{escaped_key}={escaped_value}")
    return f"@{';'.join(components)}"


def parse_message(data: str) -> Optional[IRCMessage]:
    message = IRCMessage(raw=data)
    position = 0
    length = len(data)

    if length == 0:
        return None

    if data[0] == "@":
        next_space = data.find(" ")
        if next_space == -1:
            return None
        raw_tags = data[1:next_space].split(";")
        for tag in raw_tags:
            if "=" in tag:
                key, value = tag.split("=", 1)
                message.tags[key] = value or True
            else:
                message.tags[tag] = True
        position = next_space + 1

    while position < length and data[position] == " ":
        position += 1

    if position < length and data[position] == ":":
        next_space = data.find(" ", position)
        if next_space == -1:
            return None
        message.prefix = data[position + 1 : next_space]
        position = next_space + 1
        while position < length and data[position] == " ":
            position += 1

    if position >= length:
        return None

    next_space = data.find(" ", position)
    if next_space == -1:
        message.command = data[position:]
        return message

    message.command = data[position:next_space]
    position = next_space + 1

    while position < length:
        if data[position] == ":":
            message.params.append(data[position + 1 :])
            break
        next_space = data.find(" ", position)
        if next_space == -1:
            message.params.append(data[position:])
            break
        message.params.append(data[position:next_space])
        position = next_space + 1
        while position < length and data[position] == " ":
            position += 1

    return message


__all__ = [
    "IRCMessage",
    "parse_message",
    "parse_badges",
    "parse_badge_info",
    "parse_emotes",
    "transform_emotes",
    "form_tags",
    "emote_regex",
    "emote_string",
]

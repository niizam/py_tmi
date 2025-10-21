from __future__ import annotations

import asyncio
import random
import re
from typing import Any, Dict, Iterable, Optional

ACTION_MESSAGE_REGEX = re.compile(r"^\u0001ACTION ([^\u0001]+)\u0001$")
JUSTINFAN_REGEX = re.compile(r"^(justinfan)(\d+)$")
UNESCAPE_IRC_REGEX = re.compile(r"\\([sn:r\\])")
ESCAPE_IRC_REGEX = re.compile(r"([ \n;\r\\])")
TOKEN_REGEX = re.compile(r"^oauth:", re.IGNORECASE)
IRC_ESCAPED_CHARS: Dict[str, str] = {"s": " ", "n": "", ":": ";", "r": ""}
IRC_UNESCAPED_CHARS: Dict[str, str] = {" ": "s", "\n": "n", ";": ":", "\r": "r", "\\": "\\"}


def has_own(obj: Dict[str, Any], key: str) -> bool:
    return key in obj


async def promise_delay(delay: float) -> None:
    await asyncio.sleep(delay)


def is_integer(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return value.is_integer()
    if isinstance(value, str):
        try:
            int(value)
            return True
        except ValueError:
            return False
    return False


def justinfan() -> str:
    return f"justinfan{random.randint(1_000, 89_999)}"


def is_justinfan(username: str) -> bool:
    return bool(JUSTINFAN_REGEX.match(username or ""))


def channel(value: Optional[str]) -> str:
    normalized = (value or "").lower()
    return normalized if normalized.startswith("#") else f"#{normalized}"


def username(value: Optional[str]) -> str:
    normalized = (value or "").lower()
    return normalized[1:] if normalized.startswith("#") else normalized


def token(value: Optional[str]) -> str:
    if not value:
        return ""
    return TOKEN_REGEX.sub("", value)


def password(value: Optional[str]) -> str:
    tok = token(value)
    return f"oauth:{tok}" if tok else ""


def action_message(message: str) -> Optional[re.Match[str]]:
    return ACTION_MESSAGE_REGEX.match(message)


def unescape_html(value: str) -> str:
    return (
        value.replace("\\&amp\\;", "&")
        .replace("\\&lt\\;", "<")
        .replace("\\&gt\\;", ">")
        .replace("\\&quot\\;", '"')
        .replace("\\&#039\\;", "'")
    )


def unescape_irc(value: Optional[str]) -> Optional[str]:
    if not value or "\\" not in value:
        return value
    return UNESCAPE_IRC_REGEX.sub(lambda match: IRC_ESCAPED_CHARS.get(match.group(1), match.group(1)), value)


def escape_irc(value: Optional[str]) -> Optional[str]:
    if not value:
        return value

    def replacer(match: re.Match[str]) -> str:
        char = match.group(1)
        return f"\\{IRC_UNESCAPED_CHARS.get(char, char)}"

    return ESCAPE_IRC_REGEX.sub(replacer, value)


def paginate_message(message: str, limit: int = 500) -> Iterable[str]:
    text = message
    while len(text) > limit:
        split_at = text.rfind(" ", 0, limit)
        if split_at == -1:
            split_at = limit
        yield text[:split_at]
        text = text[split_at:].lstrip()
    yield text


__all__ = [
    "has_own",
    "promise_delay",
    "is_integer",
    "justinfan",
    "is_justinfan",
    "channel",
    "username",
    "token",
    "password",
    "action_message",
    "escape_irc",
    "unescape_irc",
    "unescape_html",
    "paginate_message",
]

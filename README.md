# py_tmi

`py_tmi` is a batteries-included Python port of the popular [tmi.js](https://github.com/tmijs/tmi.js) Twitch Messaging Interface client. The project aims to provide a maintainable and extensible foundation for building Twitch chat bots or automation tooling in Python while keeping the ergonomics of the original JavaScript project.

## Features

- Asyncio-first architecture with a thin event system inspired by Node.js `EventEmitter`.
- High-level Twitch chat helpers — `say`, `action`, `ban`, `timeout`, `mod`, `vip`, and more.
- Resilient connection handling with automatic reconnection backoff, ping tracking, and rate-limited command queues.
- Full IRCv3 tag parsing, badge helpers, and emote transformation utilities.
- Cross-provider emote and badge parsing powered by the emotettv project (Twitch, BTTV, FFZ, 7TV).
- Typed models and dataclasses to make the internal state explicit and easy to extend.

## Getting Started

```bash
python -m pip install git+https://github.com/niizam/py_tmi.git
```

```python
import asyncio
from py_tmi import (
    Client,
    ClientOptions,
    IdentityOptions,
    LoggingOptions,
    parse_badges,
    parse_emotes,
)

async def main() -> None:
    options = ClientOptions(
        identity=IdentityOptions(
            username="bot_name",
            password="oauth:my_bot_token",
        ),
        channels=["#my_channel"],
        logging=LoggingOptions(level="debug", messages_level="info"),
    )
    client = Client(options)

    async def handle_message(channel, userstate, message, self):
        if self:
            return
        badges = await parse_badges(userstate.get("badges"), userstate.get("username"))
        emotes = await parse_emotes(message, userstate.get("emotes"))
        print("Badges:", badges.to_array())
        print("HTML message:", emotes.to_html())
        if message.lower() == "!hello":
            username = userstate.get("username") or ""
            await client.say(channel, f"@{username}, heya!")

    client.on("message", handle_message)

    await client.connect()
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass
    finally:
        await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

> **Note:** `client.on(event, listener)` expects both arguments immediately. Decorator-style sugar (e.g., `@client.on("message")`) is not built in, so register callbacks explicitly as shown above.

## Emote & Badge Rendering

The helpers `parse_emotes`, `parse_badges`, `reload_emotes`, and `reload_badges` are ports of the [emotettv](https://github.com/doceazedo/emotettv) TypeScript project. They resolve Twitch, BetterTTV, FrankerFaceZ, and 7TV assets into simple Python objects with `.to_array()` or ready-to-embed HTML via `.to_html()`. Provider usage is configurable:

```python
parsed = await parse_emotes(
    "Hello OMEGALUL",
    options={"channel_id": "98776633", "providers": {"ffz": False}},
)
html = parsed.to_html(scale=2)
```

Call `reload_emotes` or `reload_badges` to force-refresh cached provider data when emote sets change.

> **Compatibility:** These helpers ship in development builds after `py_tmi` 0.1.0. Install from the Git repository (`pip install git+https://github.com/niizam/py_tmi.git`) or upgrade to the next tagged release to access them.

## Development

```bash
python -m pip install -e .[dev]
pytest
```

## License

MIT — see [LICENSE](LICENSE).

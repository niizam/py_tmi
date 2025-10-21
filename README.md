# py_tmi

`py_tmi` is a batteries-included Python port of the popular [tmi.js](https://github.com/tmijs/tmi.js) Twitch Messaging Interface client. The project aims to provide a maintainable and extensible foundation for building Twitch chat bots or automation tooling in Python while keeping the ergonomics of the original JavaScript project.

## Features

- Asyncio-first architecture with a thin event system inspired by Node.js `EventEmitter`.
- High-level Twitch chat helpers — `say`, `action`, `ban`, `timeout`, `mod`, `vip`, and more.
- Resilient connection handling with automatic reconnection backoff, ping tracking, and rate-limited command queues.
- Full IRCv3 tag parsing, badge helpers, and emote transformation utilities.
- Typed models and dataclasses to make the internal state explicit and easy to extend.

## Getting Started

```bash
python -m pip install git+https://github.com/niizam/py_tmi.git
```

```python
import asyncio
from py_tmi import Client, ClientOptions, IdentityOptions, LoggingOptions

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

## Development

```bash
python -m pip install -e .[dev]
pytest
```

## License

MIT — see [LICENSE](LICENSE).

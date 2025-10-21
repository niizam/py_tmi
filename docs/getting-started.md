# Getting Started with py_tmi

This guide walks you through installing `py_tmi`, configuring the client, and connecting to Twitch chat for the first time.

## Installation

`py_tmi` targets Python 3.9 and newer. Install the package (and optional development extras) with pip:

```bash
python -m pip install git+https://github.com/niizam/py_tmi.git
# or for local development / testing
python -m pip install -e .[dev]
```

## Quick Start

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

> **Note:** `client.on(event, listener)` requires both arguments at definition time. Decorator-style usage (e.g., `@client.on("message")`) is not provided; call `client.on` explicitly as shown.

### Authentication

- `username`: Your Twitch username (without `#`).
- `password`: OAuth token with chat scope, prefixed with `oauth:` (see [Twitch token generator](https://twitchtokengenerator.com/)). Anonymous connections automatically use a `justinfan` username, but cannot send messages or whispers.

### Selecting Channels

Channels can be provided when creating `ClientOptions.channels`. You may add/remove channels dynamically via `await client.join("#channel")` and `await client.part("#channel")`.

## Events

`ClientBase` inherits from an EventEmitter. Register callbacks via `.on(event, callback)` or `.once(event, callback)`:

| Event               | Description                                                           |
|---------------------|-----------------------------------------------------------------------|
| `connected`         | Triggered after a successful IRC connect.                             |
| `message`           | Fired for every chat message (including whispers if originated here). |
| `join` / `part`     | Emitted when the local client or others join/leave a channel.         |
| `moderator`, `ban`, `timeout`, `notice`, etc. | Mirror tmi.js semantics for server notices. |

Refer to the [API reference](api/client.md#events) for the full catalog.

## Sending Messages & Commands

- `await client.say("#channel", "Hello")` — send a chat message.
- `await client.action("#channel", "waves")` — send `/me` style action.
- `await client.ban("#channel", "user", "breaking rules")` — run chat commands.

Commands raise `CommandFailed` if Twitch returns a known failure message, and `CommandTimedOut` if no response arrives within the default timeout.

## Disconnection & Reconnects

`ClientBase` automatically reconnects with exponential backoff (configurable via `ConnectionOptions`). Register for `reconnected` or `disconnected` events if you want to react to dropped connections.

## Next Steps

- Explore the [Architecture Overview](architecture.md) for a mental model of the system.
- Dive into the [Client API](api/client.md) for full command/event coverage.
- Learn how to extend the project under [Contributing](contributing.md).

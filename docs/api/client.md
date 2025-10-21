# Client API Reference

The `Client` class extends `ClientBase` and offers an asyncio-friendly facade for Twitch chat commands, mirroring the tmi.js API. Each method returns a coroutine that resolves to structured data or raises a domain-specific exception.

```python
from py_tmi import Client, ClientOptions
client = Client(ClientOptions(channels=["#example"]))
```

## Construction

| Parameter        | Type                | Description                                                  |
|------------------|---------------------|--------------------------------------------------------------|
| `options`        | `ClientOptions`     | Channels, connection, identity, logging, behaviour flags.    |
| `loop` (optional)| `asyncio.AbstractEventLoop` | Custom loop (default: `asyncio.get_event_loop()`). |

## Connection & Lifecycle

| Method                      | Returns                  | Description                                                            |
|-----------------------------|--------------------------|------------------------------------------------------------------------|
| `await client.connect()`    | `(server, port)`         | Establish connection, login, join configured channels.                 |
| `await client.disconnect()` | `(server, port)`         | Gracefully close the socket and stop background tasks.                 |
| `client.is_connected`       | `bool` (property)        | True if the websocket is open.                                         |
| `client.ready_state()`      | `str`                    | `"OPEN"`, `"CLOSING"`, or `"CLOSED"`.                                  |
| `client.wait_for(event, …)` | tuple                    | Await the next occurrence of an event (see below).                     |

## Messaging & Commands

All commands raise `CommandFailed` when Twitch returns a known failure message, `CommandTimedOut` when no response arrives in time, and `AnonymousMessageError` when an anonymous user attempts a restricted command.

| Method                                        | Result                                                |
|-----------------------------------------------|-------------------------------------------------------|
| `await client.say("#chan", "hello")`          | `(channel, message)`                                  |
| `await client.action("#chan", "waves")`       | `(channel, message)`                                  |
| `await client.reply("#chan", "msg", id)`      | `(channel, message)`                                  |
| `await client.whisper("user", "secret")`      | `(username, message)`                                  |
| `await client.ban("#chan", "user", reason)`   | `(channel, username, reason)`                         |
| `await client.unban("#chan", "user")`         | `(channel, username)`                                 |
| `await client.timeout("#chan", "user", 600)`  | `(channel, username, seconds, reason)`                |
| `await client.mod("#chan", "user")`           | `(channel, username)`                                 |
| `await client.unmod("#chan", "user")`         | `(channel, username)`                                 |
| `await client.vip("#chan", "user")`           | `(channel, username)`                                 |
| `await client.unvip("#chan", "user")`         | `(channel, username)`                                 |
| `await client.mods("#chan")`                  | `Iterable[str]`                                       |
| `await client.vips("#chan")`                  | `Iterable[str]`                                       |
| `await client.slow("#chan", 120)`             | `(channel, seconds)`                                  |
| `await client.slowoff("#chan")`               | `(channel,)`                                          |
| `await client.followersonly("#chan", 30)`     | `(channel, minutes)`                                  |
| `await client.followersonlyoff("#chan")`      | `(channel,)`                                          |
| `await client.emoteonly("#chan")`             | `(channel,)`                                          |
| `await client.emoteonlyoff("#chan")`          | `(channel,)`                                          |
| `await client.subscribers("#chan")`           | `(channel,)`                                          |
| `await client.subscribersoff("#chan")`        | `(channel,)`                                          |
| `await client.clear("#chan")`                 | `(channel,)`                                          |
| `await client.deletemessage("#chan", uuid)`   | `(channel,)`                                          |
| `await client.commercial("#chan", 30)`        | `(channel, seconds)`                                  |
| `await client.host("#chan", "target")`        | `(channel, target, remaining_hosts)`                  |
| `await client.unhost("#chan")`                | `(channel,)`                                          |
| `await client.join("#chan")`                  | `(channel,)`                                          |
| `await client.part("#chan")`                  | `(channel,)`                                          |
| `await client.ping()`                         | `float (seconds)`                                     |
| `await client.raw("PRIVMSG #chan :hi")`       | `(command,)`                                          |

### Aliases

- `client.followersmode` ➝ `followersonly`
- `client.followersmodeoff` ➝ `followersonlyoff`
- `client.leave` ➝ `part`
- `client.slowmode` ➝ `slow`
- `client.slowmodeoff` ➝ `slowoff`
- `client.r9kmode` ➝ `r9kbeta`
- `client.r9kmodeoff` ➝ `r9kbetaoff`
- `client.uniquechat` ➝ `r9kbeta`
- `client.uniquechatoff` ➝ `r9kbetaoff`

## Events

Handlers receive data mirroring tmi.js but adapted to Python conventions.

| Event               | Payload                                                                                          |
|---------------------|--------------------------------------------------------------------------------------------------|
| `connected`         | `(server, port)`                                                                                 |
| `disconnected`      | `(reason,)`                                                                                      |
| `reconnected`       | `(server, port)`                                                                                 |
| `message`           | `(channel, userstate, message, self)`                                                            |
| `chat` / `action`   | `(channel, userstate, message, self)`                                                            |
| `whisper`           | `(username, userstate, message, self)`                                                           |
| `join` / `part`     | `(channel, username, self)`                                                                      |
| `ban`               | `(channel, username, reason, tags)`                                                              |
| `timeout`           | `(channel, username, reason, seconds, tags)`                                                     |
| `notice`            | `(channel, msgid, message)`                                                                      |
| `usernotice`        | Varies by `msg-id`; general form `(msgid, channel, tags, message)`                               |
| `roomstate`         | `(channel, tags)` with keys such as `slow`, `followers-only`, `subs-only`                        |
| `userstate`         | `(channel, tags)` (client info for the given channel)                                            |
| `globaluserstate`   | `(tags,)`                                                                                        |
| `mods` / `vips`     | `(channel, Iterable[str])`                                                                       |
| `hosting`           | `(channel, target, viewers)`                                                                     |
| `unhost`            | `(channel, viewers)`                                                                             |
| `cheer`             | `(channel, tags, message)` for bits donations                                                    |
| `redeem`            | `(channel, username, reward_id, tags, message)` for channel point redemptions                    |
| `_promise*` events  | Internal promise-like signals used by command helpers. Avoid relying on them directly.           |

See `client_base.py` for the complete list of emitted events.

## Error Handling

| Exception                 | Raised When                                                       |
|---------------------------|-------------------------------------------------------------------|
| `NotConnectedError`       | Command invoked while disconnected.                               |
| `AnonymousMessageError`   | Anonymous user sends privileged command (`say`, `whisper`, etc.). |
| `CommandTimedOut`         | Twitch does not answer within the configured timeout.             |
| `CommandFailed`           | Twitch returns a failure notice for the issued command.           |
| `ConnectionError`         | Underlying socket errors during connection establishment.         |

Wrap critical operations in `try/except` blocks to surface actionable messages to downstream callers.

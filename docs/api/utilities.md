# Utilities & Helper Modules

`py_tmi` ships with several helper modules that underpin the client runtime. Understanding them helps when extending the library or when you need lower-level functionality.

## `py_tmi.options`

Dataclasses representing the configuration surface:

| Class                  | Fields (defaults)                                                                                                   |
|------------------------|----------------------------------------------------------------------------------------------------------------------|
| `ConnectionOptions`    | `server="irc.chat.twitch.tv"`, `port=6697`, `secure=True`, `reconnect=True`, rate limits & backoff parameters.       |
| `IdentityOptions`      | `username=None`, `password=None`, `client_id=None`.                                                                  |
| `LoggingOptions`       | `level="error"`, `messages_level="info"`.                                                                            |
| `ClientOptions`        | `channels=[]`, `connection=ConnectionOptions()`, `identity=IdentityOptions()`, `logging=LoggingOptions()`, feature flags. |

All classes are `slots=True` dataclasses for reduced overhead and type-hinted ergonomics.

## `py_tmi.utils`

Key helpers:

- `channel(str) -> str`: Normalize channel names to lowercase `#channel`.
- `username(str) -> str`: Normalize usernames to lowercase without leading `#`.
- `justinfan()` / `is_justinfan(username)`: Helpers for anonymous accounts.
- `escape_irc` / `unescape_irc`: Encode/decode IRC tag values.
- `paginate_message(message, limit=500)`: Generator that splits long strings to avoid Twitch truncation.
- `promise_delay(delay)`: `asyncio.sleep` wrapper used in rate limiting.

## `py_tmi.parser`

Parses Twitch IRC messages and transforms tags.

- `parse_message(raw: str) -> IRCMessage | None`: Returns dataclass with `raw`, `tags`, `prefix`, `command`, and `params`.
- `parse_badges(tags)` / `parse_badge_info(tags)` / `parse_emotes(tags)`: Mutate `tags` dict into structured data.
- `form_tags(tags) -> str | None`: Assemble tags back into the IRC `@key=value` prefix.
- `transform_emotes(emotes_dict) -> str`: Convert emote index structure back to string form.

### `IRCMessage` dataclass

| Field   | Description                               |
|---------|-------------------------------------------|
| `raw`   | Original message.                         |
| `tags`  | Mutable dictionary of IRCv3 tags.         |
| `prefix`| Message prefix (e.g., `user!user@user`).   |
| `command` | IRC command (`PRIVMSG`, `NOTICE`, etc.). |
| `params` | List of parameters (channel, payload).    |
| `param(index, default=None)` | Convenience accessor. |

## `py_tmi.event_emitter`

Lightweight emitter modeled after Node.js:

- `.on(event, listener)` / `.off(event, listener)` / `.once(event, listener)`
- `.emit(event, *args)` automatically schedules coroutine listeners via `asyncio.create_task`.
- `.emit_many(events, payloads)` for emitting multiple events in sequence, mirroring tmi.js `emits`.

When writing listeners that perform async work, declare them with `async def`—the emitter wraps them in background tasks and logs unhandled failures via the event loop’s exception handler.

## `py_tmi.message_queue`

Async queue that spaces actions (JOINs, PRIVMSG, commands) to honour Twitch rate limits:

- `await queue.add(callback, delay=None)` schedules a coroutine callback.
- `default_delay` is applied when the callback does not override `delay`.
- `.join()` waits for queue to drain; `.stop()` cancels the worker task.

Used internally by `ClientBase` to throttle outgoing traffic.

## `py_tmi.logger`

Convenience logger around `logging`:

- Map tmi.js levels (`trace`, `debug`, `info`, `warn`, `error`, `fatal`) to Python levels.
- `set_level("info")` and `get_level()` to adjust runtime verbosity.
- Override or pass your own logger via `ClientOptions.logging` if needed.

## `py_tmi.exceptions`

| Exception              | Purpose                                                                           |
|------------------------|-----------------------------------------------------------------------------------|
| `PyTMIError`           | Base class for library errors.                                                    |
| `ConnectionError`      | Connection establishment or socket failure.                                       |
| `AuthenticationError`  | Login or capability negotiation failure.                                          |
| `CommandTimedOut`      | Awaited command did not receive a response.                                       |
| `CommandFailed`        | Twitch explicitly rejected a command (contains `command` and `reason`).           |
| `NotConnectedError`    | Command invoked when no active connection exists.                                 |
| `AnonymousMessageError`| Anonymous accounts attempted restricted operations.                               |

Use these exceptions to provide user-friendly diagnostics or retry logic.

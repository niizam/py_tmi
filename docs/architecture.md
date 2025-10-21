# Architecture Overview

`py_tmi` mirrors the structure and behaviour of the original tmi.js project while embracing Pythonic conventions and asyncio. This document outlines the main modules and execution flow so you can understand how the pieces fit together.

## Design Goals

- **API Parity:** Offer a familiar surface for tmi.js users with minimal migration friction.
- **Async-first:** Lean on `asyncio` primitives for non-blocking networking and task scheduling.
- **Extensibility:** Use small, composable modules (`options`, `utils`, `parser`, etc.) to keep contributions approachable.
- **Resilience:** Provide automatic reconnection, rate-limited command queues, and error-aware command helpers.

## Core Components

| Module                     | Responsibility                                                                                  |
|----------------------------|--------------------------------------------------------------------------------------------------|
| `client_base.py`           | IRC connection management, message parsing, event emission, reconnection, rate limiting.        |
| `client.py`                | High-level Twitch command wrappers (`ban`, `slow`, `whisper`, etc.) implemented as coroutines.  |
| `event_emitter.py`         | Minimal Node-style event system with async awareness.                                           |
| `message_queue.py`         | Async delay queue for spacing JOIN/PRIVMSG/command bursts.                                      |
| `parser.py`                | IRC message parsing, tag transformation, emote helpers.                                         |
| `utils.py`                 | Identifier normalization, escaping, throttling helpers, message pagination.                     |
| `options.py`               | Dataclass-backed configuration objects mirroring tmi.js option groups.                          |
| `exceptions.py`            | Custom exception hierarchy for richer error handling.                                           |

## Event Flow

1. **Connection:** `ClientBase.connect()` establishes a TCP/SSL connection with Twitch IRC (default `irc.chat.twitch.tv:6697`), sends PASS/NICK, and requests Twitch capabilities.
2. **Reader Loop:** `_reader_loop()` consumes lines, passing each through `parser.parse_message`. Server pings are answered automatically.
3. **Message Handling:** `_handle_user_message()` routes messages to specialized handlers (`_handle_notice`, `_handle_privmsg`, etc.), normalizing tags and emitting events akin to tmi.js.
4. **Queues & Rate Limits:** Outgoing commands and messages are funneled through `MessageQueue` instances to respect Twitch throughput limits.
5. **Events:** Listeners registered via `.on()` / `.once()` receive typed payloads. Async listeners are automatically scheduled via `asyncio.create_task`.
6. **Reconnects:** If the connection drops and `ConnectionOptions.reconnect` is enabled, `ClientBase` retries with exponential backoff until success or `max_reconnect_attempts` is hit.

## Differences from tmi.js

- **Coroutines instead of Promises:** All asynchronous operations are `async def`/`await`. Use `await client.say(...)`.
- **Dataclasses for Options:** Configuration structures are immutable-ish dataclasses with explicit type hints.
- **Python Logging:** `Logger` wraps `logging` with tmi.js-style levels but remains mutable for integration with existing loggers.
- **Event Loop Awareness:** Emitting from synchronous contexts schedules coroutine listeners onto the current running loop; ensure `.connect()` runs inside an active event loop.
- **Command Errors:** Known Twitch rejections raise `CommandFailed` with contextual information; timeouts raise `CommandTimedOut`.

## Extending the Library

- Add new events by following the pattern in `client_base.py`: handle IRC commands, normalize payloads, emit events.
- For new chat commands, implement a coroutine on `Client` that crafts the command string and calls `_await_success` with the appropriate promise event.
- Keep documentation in sync (see `docs/`), and update tests (under `tests/`) to cover new functionality.

Refer to the [Contributing guide](contributing.md) for coding standards and submission workflow.

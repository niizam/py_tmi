# Emote & Badge Parsing (`py_tmi.emotettv`)

`py_tmi` ships with an async port of the [emotettv](https://github.com/doceazedo/emotettv) renderer so you can resolve Twitch, BetterTTV, FrankerFaceZ, and 7TV assets directly from Python. The module lives under `py_tmi.emotettv` and mirrors the JavaScript API.

> **Compatibility:** The emotettv helpers are available in development builds after `py_tmi` 0.1.0. Install from the Git repository or upgrade to the first release that includes them.

## Quick Start

```python
from py_tmi import parse_badges, parse_emotes

user_tags = {
    "badges": {"vip": "1"},
    "username": "stream_fan",
    "emotes": {"25": ["0-4"]},
}

badges = await parse_badges(user_tags["badges"], user_tags["username"])
message = await parse_emotes("Kappa hello chat", user_tags["emotes"])

print(badges.to_array())
print(message.to_html(scale=2))
```

Both helpers return small wrapper objects with:

- `to_array()` – raw data structures suitable for custom rendering.
- `to_html(scale=...)` – HTML snippets that mimic emotettv defaults. `scale` ranges from `0` to `3` for emotes and `0` to `2` for badges.

## API Surface

| Function | Description |
|----------|-------------|
| `parse_emotes(message, emote_positions=None, options=None)` | Parse an IRC message body into emote-aware segments. `emote_positions` can be the tags provided by Twitch, or leave it empty to resolve third-party providers only. |
| `reload_emotes(options=None)` | Force-refresh provider caches (e.g., after a channel updates its emote set). |
| `parse_badges(badges, username=None, options=None)` | Resolve badge metadata for Twitch + third-party providers. Pass the `badges` IRC tag and the emitting username. |
| `reload_badges(options=None)` | Refresh badge caches for all enabled providers. |

`options` accepts either a `ParserOptions` instance or a dictionary. The following keys are recognised:

- `channel_id` / `channelId`: Twitch numeric channel ID for channel-scoped emotes.
- `providers`: mapping of `{"twitch": True, "bttv": True, "ffz": True, "seventv": True}`. Toggle values to enable/disable providers per call.

## Provider Coverage & Caching

- **Twitch** – base emotes (via provided `emote_positions`) and channel/global badges via the unttv mirror.
- **BetterTTV** – global + channel emotes and global badges.
- **FrankerFaceZ** – global + channel emotes and user-specific badges (with replacement handling).
- **7TV** – global + channel emotes, including zero-width overlays.

Network requests are cached in-memory per provider and channel. To reset the cache (for example in long-running bots), call the respective `reload_*` helper.

## HTML Output

`to_html()` emits simple `<figure>` / `<img>` markup with inline styles by default. Set `inline_styles=False` if you prefer to apply CSS yourself. Zero-width emotes (e.g., 7TV overlays) are layered automatically after parsing.

Badges return `<img>` tags with optional background colors when FFZ exposes them.

## Error Handling

All remote fetches are best-effort; failures are swallowed and result in missing entries rather than exceptions. This mirrors the TypeScript behaviour and keeps chat rendering resilient when provider APIs are unavailable.

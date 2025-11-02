from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, MutableMapping, Optional, Union

DEFAULT_PROVIDERS: Dict[str, bool] = {
    "twitch": True,
    "bttv": True,
    "ffz": True,
    "seventv": True,
}


@dataclass(slots=True)
class ParserOptions:
    """Options that control which providers are used when parsing emotes/badges."""

    channel_id: Optional[str] = None
    providers: Dict[str, bool] = field(
        default_factory=lambda: dict(DEFAULT_PROVIDERS)
    )

    def is_enabled(self, provider: str) -> bool:
        return self.providers.get(provider, False)


RawOptions = Union[ParserOptions, Mapping[str, object], MutableMapping[str, object]]


def load_options(options: Optional[RawOptions]) -> ParserOptions:
    """Normalise user supplied options with the defaults used by emotettv."""

    if isinstance(options, ParserOptions):
        merged = {**DEFAULT_PROVIDERS, **options.providers}
        return ParserOptions(channel_id=options.channel_id, providers=merged)

    channel_id: Optional[str] = None
    providers: Dict[str, bool] = dict(DEFAULT_PROVIDERS)

    if options:
        # Support both snake_case and camelCase keys.
        channel_id = (
            str(options.get("channel_id"))
            if isinstance(options.get("channel_id"), str)
            else options.get("channel_id")
        )  # type: ignore[assignment]
        if not channel_id and isinstance(options.get("channelId"), str):
            channel_id = str(options["channelId"])  # type: ignore[assignment]

        raw_providers = options.get("providers") if isinstance(options, Mapping) else None
        if isinstance(raw_providers, Mapping):
            providers.update(
                {key: bool(value) for key, value in raw_providers.items()}
            )

    return ParserOptions(channel_id=channel_id, providers=providers)

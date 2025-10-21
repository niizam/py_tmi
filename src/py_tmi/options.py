from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(slots=True)
class ConnectionOptions:
    """Connection related configuration."""

    server: str = "irc.chat.twitch.tv"
    port: int = 6697
    secure: bool = True
    reconnect: bool = True
    reconnect_interval: float = 1.0
    max_reconnect_interval: float = 30.0
    reconnect_decay: float = 1.5
    max_reconnect_attempts: Optional[int] = None
    ping_interval: float = 240.0
    ping_timeout: float = 10.0
    join_rate_limit: float = 1.6  # seconds between JOIN commands
    command_rate_limit: float = 1.6  # seconds between chat commands
    message_rate_limit: float = 1.0  # seconds between PRIVMSG when verified
    rate_limits: Dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class IdentityOptions:
    """Authentication options."""

    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None


@dataclass(slots=True)
class LoggingOptions:
    """Logger configuration."""

    level: str = "error"
    messages_level: str = "info"


@dataclass(slots=True)
class ClientOptions:
    """Top-level options replicating tmi.js configuration structure."""

    channels: List[str] = field(default_factory=list)
    connection: ConnectionOptions = field(default_factory=ConnectionOptions)
    identity: IdentityOptions = field(default_factory=IdentityOptions)
    logging: LoggingOptions = field(default_factory=LoggingOptions)
    request_membership: bool = True
    request_commands: bool = True
    request_tags: bool = True
    global_default_channel: str = "#tmijs"
    skip_membership: bool = False
    join_existing_channels: bool = True


"""Custom exceptions for the py_tmi package."""

from __future__ import annotations


class PyTMIError(Exception):
    """Base exception for the package."""


class ConnectionError(PyTMIError):
    """Raised when the client fails to connect or loses the connection."""


class AuthenticationError(PyTMIError):
    """Raised when Twitch rejects authentication credentials."""


class CommandTimedOut(PyTMIError):
    """Raised when Twitch does not respond to a command in time."""


class NotConnectedError(PyTMIError):
    """Raised when attempting to send a command while disconnected."""


class AnonymousMessageError(PyTMIError):
    """Raised when attempting to whisper or send a message anonymously."""


class CommandFailed(PyTMIError):
    """Raised when Twitch returns a known failure for a command."""

    def __init__(self, command: str, reason: str) -> None:
        super().__init__(f"Command '{command}' failed: {reason}")
        self.command = command
        self.reason = reason

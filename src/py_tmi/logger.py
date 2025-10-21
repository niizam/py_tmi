from __future__ import annotations

import logging
from typing import Dict


class Logger:
    """Thin wrapper around the standard logging module with tmi.js style levels."""

    _LEVELS: Dict[str, int] = {
        "trace": logging.DEBUG - 5,
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
        "error": logging.ERROR,
        "fatal": logging.CRITICAL,
    }

    def __init__(self, name: str = "py_tmi") -> None:
        logging.addLevelName(self._LEVELS["trace"], "TRACE")
        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
        self.set_level("error")

    def set_level(self, level: str) -> None:
        level_name = level.lower()
        if level_name not in self._LEVELS:
            raise ValueError(f"Unknown log level '{level}'")
        self._logger.setLevel(self._LEVELS[level_name])

    def get_level(self) -> str:
        current = self._logger.getEffectiveLevel()
        for name, value in self._LEVELS.items():
            if value == current:
                return name
        return logging.getLevelName(current)

    def trace(self, message: str, *args, **kwargs) -> None:
        self._logger.log(self._LEVELS["trace"], message, *args, **kwargs)

    def debug(self, message: str, *args, **kwargs) -> None:
        self._logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        self._logger.info(message, *args, **kwargs)

    def warn(self, message: str, *args, **kwargs) -> None:
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        self._logger.error(message, *args, **kwargs)

    def fatal(self, message: str, *args, **kwargs) -> None:
        self._logger.critical(message, *args, **kwargs)


__all__ = ["Logger"]

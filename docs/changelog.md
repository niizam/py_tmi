# Changelog

All notable changes to `py_tmi` will be documented here. The project adheres to semantic versioning (`MAJOR.MINOR.PATCH`).

## [0.1.0] - 2025-10-21

- Initial Python port of tmi.js core functionality.
- Implemented `ClientBase` with asyncio connection handling, reconnection, and event routing.
- Added high-level `Client` command API with error-aware helpers.
- Ported utilities (`utils`, `parser`, `logger`, `message_queue`, `event_emitter`) and configuration dataclasses.
- Introduced pytest suite covering utilities, parser behaviour, and event emitter.
- Established project metadata (`pyproject.toml`), README, license, and documentation set.

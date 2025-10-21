# Contributing Guide

Thank you for your interest in improving `py_tmi`! This document outlines how to set up your environment, coding standards, and workflow expectations.

## Environment Setup

```bash
git clone <your-fork-url>
cd py_tmi
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
python -m pip install -e .[dev]
```

Run the test suite to ensure everything is configured correctly:

```bash
python -m pytest
```

## Coding Standards

- **Python version**: 3.9+.
- **Formatting**: Follow PEP 8. Keep imports ordered (stdlib, third-party, local). Apply black/ruff if desired but do not reformat unrelated code.
- **Comments**: Only where necessary to explain non-obvious behaviour. Use docstrings for public APIs.
- **Types**: Prefer explicit type hints; dataclasses with `slots=True` for structured data.
- **Async**: Use `asyncio` conventions. Do not mix threads unless necessary.

## Git Workflow

1. Create a feature branch (`git checkout -b feature/my-change`).
2. Implement your changes with tests and documentation updates.
3. Run `python -m pytest`.
4. Submit a pull request describing the motivation and behaviour changes.

## Tests

- Unit tests live under `tests/`.
- Aim for coverage around new modules; mimic the existing style.
- For asynchronous code, use event-loop fixtures or explicit loop management as shown in `test_event_emitter.py`.

## Documentation

- Update the `docs/` section relevant to your change.
- Keep `README.md` succinct; detailed explanations belong in documentation pages.

## Reporting Issues

When filing an issue, include:

- Reproduction steps.
- Expected vs actual behaviour.
- Logs or stack traces if available.
- Python version and OS info.

## Releases

- Version bumping happens in `pyproject.toml` under `[project]`.
- Update `docs/changelog.md` with a summary of changes.

We appreciate every contribution, from typo fixes to major features. Happy hacking!

# AGENTS.md

Guidance for coding agents working in this repository.

## Scope

- Applies to the entire repository unless a deeper `AGENTS.md` overrides it.
- For project architecture, features, data model, and plugin specifications, see [`doc/architecture.md`](doc/architecture.md).

## Setup

- Required tools: `uv`, Python `3.14+`
- Sync dependencies: `uv sync --group dev`

## Common Commands

- CLI (preferred): `uv run time_plot ...`
- Dev fallback entrypoint: `uv run python main.py ...`
- Generate example files: `uv run python scripts/generate_example_data.py`
- Run tests: `uv run pytest`
- Add dependency: `uv add <package>`
- Add dev dependency: `uv add --dev <package>`

## Validation Checklist

- Run focused tests for changed modules first.
- Minimum useful commands:
  - `uv run pytest -q`
  - `uv run python scripts/generate_example_data.py`
  - `uv run time_plot example_data/sine.csv`
  - `uv run time_plot example_data/sine.csv 'sum:expr[sine+sine]' 'r:expr[ddt(sum)]'`
- If skipping validation, state why in handoff.

## Coding Standards

- Prefer clear names over clever abstractions.
- Update docs/comments when behavior changes.
- Keep Python code compatible with the version declared in `pyproject.toml`.
- Always use `pathlib` when possible.

## Testing Expectations

- Add or update tests for behavior changes when feasible.
- Prefer small focused tests first, then integration-style checks.
- If tests are skipped or unavailable, note that in the handoff.

## Change Safety

- Check for existing local changes before editing shared files.

## PR / Handoff Notes

- Summarize what changed and why.
- Note follow-up work, risks, or assumptions.
- Include commands run for validation and outcomes.

## Agent-Specific Instructions

- Prefer `uv` for dependency and command execution.
- If introducing tests, add test tooling to dev dependencies in `pyproject.toml`.
- `uv run pytest` should work against live workspace code after `uv sync --group dev` (editable install support is implemented in `local_build_backend.py`).

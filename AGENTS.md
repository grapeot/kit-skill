# Kit Skill

## Project Role

This repository provides an AI-first Kit API skill focused on broadcast publishing. It is a public-ready Python package, CLI, and Markdown skill contract for creating Kit broadcasts from local Markdown files with dry-run, draft-only, public/web-only, scheduled send, and tag/segment targeting support.

It is not a full Kit dashboard replacement, CRM, sales system, commerce integration, or generic API passthrough. Every command should serve a stable agent workflow with clear safety boundaries.

## Project Structure

- `README.md`: public installation and usage guide.
- `docs/prd.md`: product scope and success criteria.
- `docs/rfc.md`: architecture, CLI, configuration, and migration decisions.
- `docs/test.md`: unit, live integration, and manual test strategy.
- `docs/working.md`: changelog and lessons learned.
- `skills/skill_kit.md`: canonical agent skill document.
- `src/kit_skill/`: reusable Python package.
- `scripts/`: stable wrappers for humans and agents.
- `tests/`: default offline tests plus opt-in live tests.

## Environment Rules

- Use the project virtual environment: `uv venv .venv`, then `source .venv/bin/activate`.
- Install dependencies with `uv pip install -e '.[dev]'`; do not use bare `pip install`.
- Never commit real API keys, private 1Password vault paths, token files, generated newsletters, local `.env` files, logs, or private subscriber data.
- This repository is intended to be publishable. Public docs, examples, and fixtures must use fake addresses, fake domains, fake tag IDs, and fake 1Password references.
- Authentication supports direct `KIT_API_KEY` values and values resolved before Python starts. Prefer `op run --env-file=.env -- <command>` for private 1Password references.

## Safety Boundaries

- Network writes are disabled by default in tests.
- Real broadcast creation must be preceded by a dry-run unless the user has already explicitly approved the exact action.
- Live tests require `KIT_ENABLE_LIVE_TESTS=1` and should use throwaway test tags/subscribers.
- Do not send to real production audiences during migration tests; use `--draft` or a test tag.

## Maintenance

- Update `docs/working.md` after meaningful design or implementation changes.
- Keep `docs/rfc.md`, `docs/test.md`, and `skills/skill_kit.md` aligned with CLI contract changes.
- This directory is an independent git repository. Commit from this repository root, not from a parent workspace.

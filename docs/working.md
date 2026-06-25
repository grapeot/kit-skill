# Working Notes

## Changelog

### 2026-06-25

- Created Kit skill scaffold.
- Defined initial scope as broadcast publishing only.
- Captured migration requirements: tag targeting, draft-only mode, web-only compatibility, and public repo privacy constraints.
- Moved repository hygiene language out of the user-facing README and kept it in `AGENTS.md`, because public-readiness is an agent/operator constraint rather than product documentation.
- Implemented broadcast CLI package with dry-run, draft, web-only, tag targeting, segment targeting, stats, and configuration inspection.
- Added `--tag-name` support so private workspace overlays can refer to account-specific tag names without hard-coding tag IDs in public docs.
- Added offline tests for payload construction and CLI dry-run behavior.
- Replaced the legacy AI Heartbeat Kit script with a compatibility wrapper that routes to this package.
- Updated AI Heartbeat prompts to use the new CLI; daily newsletter now creates a Kit draft instead of scheduling an automatic send.
- Validation: `.venv/bin/python -m pytest -v` passed 9 tests; `.venv/bin/ruff check .` passed; legacy wrapper dry-run produced the expected tag-targeted payload.
- Privacy scan result: only fake `KIT_API_KEY` examples and the code path that rejects unresolved secret-manager references matched; no real secret, private path, or local `.env` was included in git status.

## Lessons Learned

- Keep product/payment concepts out of this skill. The current use case is email audience routing only.
- Do not assume Kit Link Triggers work in API-created broadcasts until tested with a real test subscriber.
- User-facing README should explain what the tool does and how to use it. Public-repo hygiene and “do not commit secrets” guidance belongs in `AGENTS.md`, `.gitignore`, and `.env.example`, not in README prose unless it directly affects the user workflow.

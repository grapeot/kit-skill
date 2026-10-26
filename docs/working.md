# Working Notes

## Changelog

### 2026-10-26

- Committed previously unimplemented-but-documented analytics features: `analytics subscriber-count --tag`, `analytics tags`, `find_tag`, and `tag_subscriber_count`, with their existing tests.
- Added `subscribers show` and `subscribers unsubscribe` (single-address consent mutation, dry-run default, `--execute` gate) backed by fresh ID re-reads; outcomes separate confirmed, succeeded-unverified, and unknown write states.
- Added read-only `analytics bounce-hygiene`: one-tag `POST /v4/subscribers/filter` scan with embedded account-level stats, cursor pagination via `per_page`/`after` query params, client-side bounce thresholds, null-safe ratios, and missing-stats aborts.
- Added `.gitignore` coverage for `.local/` with attempt logs under `.local/subscription_actions/` (exclusive create, 0600 files, 0700 directory, no PII in filenames); sanitized HTTP/transport error output for the new commands only (no raw bodies or query-string URLs).
- Extended `KitClient` with `find_subscribers_by_email`, `get_subscriber`, `unsubscribe_subscriber` (validates 204 explicitly), and `filter_subscribers`; `_post` now supports query params.
- Design record: independent design review with 5 must-fix items integrated (working document; not committed to the repository).
- Privacy review round 1: scrubbed account-style tag strings from public docs/tests in favor of `example:*`, removed the production tag default from `bounce-hygiene` (`--tag` now required), reduced sanitized HTTP error output to status codes only (including the generic CLI fallback), added input-privacy notes for shell history/process arguments, and removed subscriber IDs from attempt-log filenames.

### 2026-06-26

- Migrated legacy Kit analytics capabilities into the reusable `kit-skill` package.
- Added `kit-skill analytics` commands for account, growth, email stats, subscriber count/list, broadcasts, broadcast stats, sequences, sequence details, and snapshot output.
- Kept `broadcast stats` as the existing entry point and added `analytics broadcast-stats` for the read-only analytics group.
- Added default subscriber email redaction for list-style analytics commands; raw emails require `--show-emails`.
- Ported Kit sequence and analytics tests into the project test suite.
- Tightened live test gating so enabling live tests without a real `KIT_LIVE_SEQUENCE_ID` and `KIT_LIVE_TEST_EMAIL` skips instead of calling fake IDs against the real Kit API.
- Documented that `subscriber-count` is account-wide and should not be read as a tag or newsletter audience size.

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

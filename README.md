# Kit Skill

AI-first Kit broadcast publishing and read-only analytics. The CLI supports dry-runs, scheduled sends, draft-only creation, web publishing, web-only backfills, tag/segment-targeted broadcasts, subscriber growth metrics, email stats, broadcast stats, and sequence checks.

This repository is self-contained. It provides a plain Markdown skill contract at `skills/skill_kit.md` plus a Python package and CLI that agents can call.

## What It Does

- Convert a local Markdown newsletter into simple HTML.
- Create Kit broadcasts through the Kit API v4.
- Dry-run and print the exact payload before any network write.
- Target recipients by tag ID or segment ID using Kit `subscriber_filter`.
- Create draft-only broadcasts without scheduling a send.
- Publish web-only backfills without email delivery when Kit supports the account behavior.
- Read Kit account, growth, email, subscriber-count, broadcast, and sequence analytics.

## Install

From this repository root:

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[dev]'
```

## Configure

Copy `.env.example` to `.env` and set private values:

```bash
KIT_API_KEY=replace-with-your-kit-api-key
KIT_DEFAULT_EMAIL_ADDRESS="Example Sender <newsletter@example.com>"
KIT_DEFAULT_EMAIL_TEMPLATE_ID=123456
```

If your `.env` uses a private secret manager reference, resolve it before Python starts. For example:

```bash
op run --env-file=.env -- kit-skill doctor config --format json
```

## Use the CLI

Dry-run a normal scheduled broadcast:

```bash
kit-skill broadcast send newsletter.md --dry-run --format json
```

Create a draft only:

```bash
kit-skill broadcast send newsletter.md --draft --format json
```

Target one Kit tag:

```bash
kit-skill broadcast send newsletter.md --tag-id 123456 --dry-run --format json
```

Target one Kit tag by exact name:

```bash
kit-skill broadcast send newsletter.md --tag-name example:newsletter --dry-run --format json
```

Create a web-only backfill:

```bash
kit-skill broadcast send newsletter.md --web-only --format json
```

Get broadcast stats:

```bash
kit-skill broadcast stats 123456 --format json
```

Read analytics:

```bash
kit-skill analytics growth --start-date 2026-03-01 --end-date 2026-03-14 --format json
kit-skill analytics email-stats --format json
kit-skill analytics subscriber-count
kit-skill analytics broadcasts --limit 10 --format json
kit-skill analytics broadcast-stats 123456 --format json
kit-skill analytics snapshot --output /tmp/kit_snapshot.json
```

Subscriber list commands redact email addresses by default. Pass `--show-emails` only when the output destination is private.

## Install the Agent Skill

1. Put `skills/skill_kit.md` somewhere your agent can discover, usually a global or workspace `skills/` directory.
2. Look at the workspace's root guidance files such as `AGENTS.md`, `CLAUDE.md`, or equivalent.
3. If those files point to a skill index or discovery document, add this skill there.
4. If no discovery file exists, add a short note to the root guidance file telling the agent to read `skills/skill_kit.md` for Kit broadcast publishing tasks.

## Test

Default tests are offline:

```bash
.venv/bin/python -m pytest -v
```

Live tests are opt-in:

```bash
KIT_ENABLE_LIVE_TESTS=1 .venv/bin/python -m pytest -v -m live_integration
```

## Configuration Notes

Keep credentials in your local environment or `.env`. The CLI reads `KIT_API_KEY`, `KIT_DEFAULT_EMAIL_ADDRESS`, and `KIT_DEFAULT_EMAIL_TEMPLATE_ID` at runtime.

# Kit Skill

## Purpose

Use Kit API v4 for agent-controlled broadcast publishing from local Markdown files and read-only analytics. This file is the canonical agent contract for this repository.

This is a plain Markdown skill document, not a vendor-specific packaged skill format. Agents should read it when the user asks for Kit broadcast creation, draft creation, scheduled send, web-only backfill, tag/segment-targeted sending, subscriber growth, email stats, broadcast stats, or sequence checks.

## Project Setup

From the repository root:

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[dev]'
```

Configuration can be direct environment variables or values resolved before Python starts:

```bash
KIT_API_KEY=replace-with-your-kit-api-key
KIT_DEFAULT_EMAIL_ADDRESS="Example Sender <newsletter@example.com>"
KIT_DEFAULT_EMAIL_TEMPLATE_ID=123456
```

Do not commit `.env`, real API keys, private vault paths, generated newsletters, logs, or subscriber data.

## Broadcast Send

Always dry-run before creating a real broadcast unless the user has already explicitly approved the exact action.

```bash
.venv/bin/python -m kit_skill.cli broadcast send newsletter.md --dry-run --format json
```

Target a tag:

```bash
.venv/bin/python -m kit_skill.cli broadcast send newsletter.md \
  --tag-id 123456 \
  --dry-run \
  --format json
```

Target a tag by exact name when the account tag names are known:

```bash
.venv/bin/python -m kit_skill.cli broadcast send newsletter.md \
  --tag-name example:newsletter \
  --dry-run \
  --format json
```

Create a draft only:

```bash
.venv/bin/python -m kit_skill.cli broadcast send newsletter.md --draft --format json
```

Create a web-only backfill:

```bash
.venv/bin/python -m kit_skill.cli broadcast send newsletter.md --web-only --format json
```

## Broadcast Stats

```bash
.venv/bin/python -m kit_skill.cli broadcast stats 123456 --format json
```

## Read-Only Analytics

```bash
.venv/bin/python -m kit_skill.cli analytics growth --start-date 2026-03-01 --end-date 2026-03-14 --format json
.venv/bin/python -m kit_skill.cli analytics email-stats --format json
.venv/bin/python -m kit_skill.cli analytics subscriber-count
.venv/bin/python -m kit_skill.cli analytics broadcasts --limit 10 --format json
.venv/bin/python -m kit_skill.cli analytics broadcast-stats 123456 --format json
.venv/bin/python -m kit_skill.cli analytics snapshot --output /tmp/kit_snapshot.json
```

Subscriber list commands redact emails by default. Use `--show-emails` only when the terminal, log, and output file are private.

## Boundaries

- Do not create a real broadcast without first reviewing dry-run payload.
- Do not send to real production audiences during migration tests.
- Do not manage products, purchases, payments, or commerce in this skill.
- Do not build subscriber import or preference-center behavior into the first version.
- Treat Kit default unsubscribe and topic-level Link Trigger opt-out as separate product semantics.
- Keep analytics commands read-only except for explicit live e2e sequence tests.
- Do not print raw subscriber emails unless the user explicitly asks and the output destination is private.

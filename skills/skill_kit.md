# Kit Skill

## Purpose

Use Kit API v4 for agent-controlled broadcast publishing from local Markdown files. This file is the canonical agent contract for this repository.

This is a plain Markdown skill document, not a vendor-specific packaged skill format. Agents should read it when the user asks for Kit broadcast creation, draft creation, scheduled send, web-only backfill, or tag/segment-targeted sending.

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

## Boundaries

- Do not create a real broadcast without first reviewing dry-run payload.
- Do not send to real production audiences during migration tests.
- Do not manage products, purchases, payments, or commerce in this skill.
- Do not build subscriber import or preference-center behavior into the first version.
- Treat Kit default unsubscribe and topic-level Link Trigger opt-out as separate product semantics.

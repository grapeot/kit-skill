# Kit Skill

## Purpose

Use Kit API v4 for agent-controlled broadcast publishing from local Markdown files and read-only analytics. This file is the canonical agent contract for this repository.

This is a plain Markdown skill document, not a vendor-specific packaged skill format. Agents should read it when the user asks for Kit broadcast creation, draft creation, scheduled send, web-only backfill, tag/segment-targeted sending, subscriber growth, email stats, broadcast stats, or sequence checks.

## Routing Model

This is one Kit platform skill with three modes, not three separate skills:

1. **Publish mode**: broadcast creation, draft creation, scheduled send, web-only backfill, and tag/segment targeting.
2. **Analytics mode**: account info, subscriber growth, email stats, subscriber counts, recent broadcasts, broadcast stats, sequences, and snapshots.
3. **Subscriber state mode**: single-address consent mutations via `subscribers show` / `subscribers unsubscribe`, plus the read-only `analytics bounce-hygiene` scan.

Start in Analytics mode when the user asks to inspect performance, diagnose growth, compare broadcasts, or decide what happened. Switch to Publish mode only when the user asks to create or change a broadcast. Switch to Subscriber state mode only when the user names a concrete subscriber and an unsubscribe/state action for this round.

Safety boundary: Analytics mode is read-only and can run autonomously with local credentials. Publish mode can create real Kit objects; always dry-run before creation unless the user has already explicitly approved the exact write action. Subscriber state mode performs consent-revoking, effectively permanent, account-wide mutations: the default is dry-run, `--execute` requires an explicit per-action user instruction in the current round, and batch operations are not provided.

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

## Publish Mode

### Broadcast Send

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

### Broadcast Stats

```bash
.venv/bin/python -m kit_skill.cli broadcast stats 123456 --format json
```

## Analytics Mode

Use Analytics mode for read-only Kit state. These commands do not create broadcasts or modify subscriber state.

```bash
.venv/bin/python -m kit_skill.cli analytics growth --start-date 2026-03-01 --end-date 2026-03-14 --format json
.venv/bin/python -m kit_skill.cli analytics email-stats --format json
.venv/bin/python -m kit_skill.cli analytics subscriber-count
.venv/bin/python -m kit_skill.cli analytics subscriber-count --tag "example:newsletter"
.venv/bin/python -m kit_skill.cli analytics tags --format json
.venv/bin/python -m kit_skill.cli analytics broadcasts --limit 10 --format json
.venv/bin/python -m kit_skill.cli analytics broadcast-stats 123456 --format json
.venv/bin/python -m kit_skill.cli analytics snapshot --output /tmp/kit_snapshot.json
.venv/bin/python -m kit_skill.cli analytics bounce-hygiene --tag example:newsletter --since 2026-04-01
```

`analytics bounce-hygiene` scans the members of one tag for high account-level bounce counts in a stats window. The stats cover broadcasts, sequences, and templates on the account, so they are not attributable to the tag alone; the scan is investigative, not a hard-bounce verdict, and never unsubscribes on its own.

Subscriber list commands redact emails by default. Use `--show-emails` only when the terminal, log, and output file are private.

`analytics subscriber-count` returns account-wide active subscribers. Do not interpret it as a tag, segment, or newsletter audience count unless the account has only one audience. For a per-audience count, pass `--tag` with a tag name or numeric id; use `analytics tags` to discover tag names. An unknown tag name exits 1 with `Tag not found`.

## Subscriber State Mode

Single-address consent mutations:

```bash
.venv/bin/python -m kit_skill.cli subscribers show person@example.com
.venv/bin/python -m kit_skill.cli subscribers unsubscribe person@example.com
.venv/bin/python -m kit_skill.cli subscribers unsubscribe person@example.com --execute
```

`subscribers unsubscribe` defaults to dry-run. The flow resolves the subscriber by exact email, re-reads the current record by ID, and only `active` subscribers proceed to the POST when `--execute` is passed; `cancelled` reports `already_cancelled`, other known states report `skipped_non_active`, and the command exits 0 on these without writing. The unconfirmed-write outcomes (`write_succeeded_verification_failed`, `write_outcome_unknown`) exit 1 and are never retried automatically. Attempt logs land in `<repo>/.local/subscription_actions/` with no PII in filenames. Unsubscribing affects all future sends on the account, not just a tag.

Input privacy: the positional email goes into shell history, process arguments, and agent invocation logs; output masking does not sanitize those records. Attempt-log bodies contain the full email and subscriber ID — keep them in private run context and never paste them into public reports.

## Boundaries

- Do not create a real broadcast without first reviewing dry-run payload.
- Do not send to real production audiences during migration tests.
- Do not treat read-only analytics permission as permission to publish.
- Do not manage products, purchases, payments, or commerce in this skill.
- Do not build subscriber import or preference-center behavior into the first version.
- Treat Kit default unsubscribe and topic-level Link Trigger opt-out as separate product semantics.
- Keep analytics commands read-only except for explicit live e2e sequence tests.
- Consent mutations are single-address only and never automated; a dry-run alone never satisfies the `--execute` gate, which requires a fresh explicit user instruction naming the address.
- Do not print raw subscriber emails unless the user explicitly asks and the output destination is private.

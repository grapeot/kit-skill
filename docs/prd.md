# PRD: Kit Broadcast Skill

## Goal

Provide an AI-first Kit CLI skill for creating broadcast emails from local Markdown files with safe dry-run behavior and optional tag/segment recipient targeting.

## Users

- AI agents that need a stable contract for publishing Kit broadcasts.
- Humans who want a predictable CLI for newsletter publishing and migration tests.
- Existing internal workflows that need to move from a one-off script to a reusable skill.

## Non-Goals

- Managing products, purchases, payments, or commerce.
- Acting as a full Kit dashboard replacement.
- Building a subscriber preference center.
- Syncing subscriber lists in the background.
- Sending to production audiences during tests.

## Requirements

1. The CLI can create a Kit broadcast from a Markdown file.
2. Existing default behavior can be preserved by compatibility callers: public broadcast, scheduled send, sender address, template ID, and simple Markdown-to-HTML conversion.
3. The CLI supports explicit tag targeting with Kit `subscriber_filter`.
4. The CLI supports draft-only creation without scheduling a send.
5. The CLI supports web-only backfill behavior equivalent to the legacy script.
6. Dry-run prints the full payload that would be sent to Kit.
7. Offline tests cover payload construction and CLI parsing.
8. Live tests are opt-in and never run by default.

## Success Criteria

- `kit-skill broadcast send sample.md --dry-run --format json` returns a JSON payload without network writes.
- `--tag-id 123` adds a `subscriber_filter` with type `tag` and id `123`.
- `--draft` sets `public=false` and `send_at=null`.
- Running default tests passes without API credentials.
- Public files contain no real API keys, private vault paths, private domains, or subscriber data.

# RFC: Kit Skill Architecture

## Context

The existing Kit workflows lived in internal one-off scripts. One path created Kit API v4 broadcasts from Markdown, while another fetched account growth, email stats, subscriber counts, broadcasts, broadcast stats, and sequence metadata.

This project extracts both workflows into a reusable CLI while keeping write operations explicitly separate from read-only analytics.

## Scope

The skill covers broadcast publishing, read-only analytics, and limited subscriber state management. Subscriber import, tag creation, form automation, visual automation setup, custom unsubscribe link setup, and background syncing remain out of scope. Subscriber consent mutations are limited to single-address operations: batch unsubscribe, resubscribe, and import are out of scope.

## CLI Contract

Primary command:

```bash
kit-skill broadcast send <markdown_file> [options]
```

Important options:

- `--dry-run`: print payload without network writes.
- `--draft`: create a draft-only broadcast by setting `public=false` and `send_at=null`.
- `--web-only`: publish a web post without email delivery using the legacy backfill strategy.
- `--tag-id <id>`: target recipients with a Kit tag. Repeatable.
- `--tag-name <name>`: resolve an exact Kit tag name to its ID before creating the broadcast. Repeatable.
- `--segment-id <id>`: target recipients with a Kit segment. Repeatable.
- `--filter-mode all|any|none`: choose the Kit subscriber filter group; default `all`.
- `--publish` / `--no-publish`: control Kit `public` when not using `--draft`.
- `--schedule-minutes <n>`: schedule email delivery in N minutes; default 2.
- `--email-address <address>`: override sender address.
- `--email-template-id <id>`: override template ID.

Stats command:

```bash
kit-skill broadcast stats <broadcast_id>
```

Read-only analytics commands:

```bash
kit-skill analytics account
kit-skill analytics growth [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
kit-skill analytics email-stats
kit-skill analytics subscriber-count [--status active]
kit-skill analytics subscribers [--status active] [--limit 50] [--show-emails]
kit-skill analytics broadcasts [--limit 10]
kit-skill analytics broadcast-stats <broadcast_id>
kit-skill analytics sequences [--limit 50]
kit-skill analytics sequence <sequence_id> [--include-subscribers] [--show-emails]
kit-skill analytics snapshot [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--broadcasts-limit 10] [--output path]
```

`analytics subscribers` and `analytics sequence --include-subscribers` redact email addresses by default. `--show-emails` is an explicit private-output opt-in.

## Subscriber State Management

Consent-revoking single-address operations on subscriber state:

```bash
kit-skill subscribers show <email> [--show-emails]
kit-skill subscribers unsubscribe <email> [--execute]
```

- `unsubscribe` defaults to dry-run: it locates the subscriber by exact email (`GET /v4/subscribers?email_address=...&status=all`, cursor-paginated), re-reads the current record by ID (list reads are eventually consistent; ID reads are strongly consistent), and prints the outcome without writing.
- Only `active` subscribers proceed to the write; `cancelled` returns `already_cancelled` and other known states return `skipped_non_active`, all without POST and all exit 0.
- `--execute` creates a pre-write attempt log under `.local/subscription_actions/` (directory 0700, file exclusive-created 0600, filename without PII), refuses to write if that fails, then calls `POST /v4/subscribers/{id}/unsubscribe` and requires HTTP 204 as the only confirmed success signal. The read-back after 204 must report `state=cancelled`; any other read-back is reported as write-succeeded-but-unverified, and the flow never auto-retries the POST.
- Outcome field values: `dry_run`, `not_found`, `ambiguous`, `already_cancelled`, `skipped_non_active`, `confirmed_cancelled`, `write_succeeded_verification_failed`, `write_outcome_unknown`, `error`. Exit codes: 0 dry-run/expected skip/confirmed; 1 operational failure or unconfirmed write; 2 argument errors.
- Unsubscribing applies to all future sends on the account, not just a tag. It is consent-revoking and effectively permanent; resubscription is not provided.
- Error output is sanitized: status code, endpoint, and Kit's `errors` array only; response bodies and query-string URLs are not echoed raw.

## Bounce Hygiene Scan

Read-only scan of tag members with high account-level bounce counts:

```bash
kit-skill analytics bounce-hygiene --tag <name|id> --since YYYY-MM-DD [--until YYYY-MM-DD] [--min-bounced 3]
```

- Request shape: `POST /v4/subscribers/filter` with `all=[{subscriber_state: [active]}, {tags: any ids match}]` and `include=[{stats, range}]`, cursor-paginated via `per_page`/`after` query params (page size default 500, max 1000). The `after` query-parameter support for this endpoint is verified with a small two-page read-only probe before trusted use.
- Output embeds each member's account-level stats (broadcasts, sequences, and templates combined) for the requested window; it is not attributable to the tag alone and is not a hard-bounce verdict. Rows missing `stats` abort the scan. 429 or pagination failures exit nonzero with a scan-incomplete declaration.
- Emails are redacted by default; `--show-emails` is a private-output opt-in.

## Draft Semantics

Kit documentation states that a draft is saved by setting `public=false`; scheduled sends require `public=true` and `send_at`. The `--draft` flag therefore overrides `--publish`, `--web-only`, and scheduling fields.

The legacy script's `--no-email` behavior is preserved as `--web-only`: it sets `send_at` slightly in the past while keeping the broadcast public. This should be treated as a compatibility behavior and verified with a non-production broadcast before relying on it.

## Recipient Targeting

Kit API v4 uses `subscriber_filter`. For one tag:

```json
{
  "subscriber_filter": [
    {
      "all": [
        { "type": "tag", "ids": [123456] }
      ],
      "any": null,
      "none": null
    }
  ]
}
```

If no tag or segment options are passed, `subscriber_filter` is omitted so Kit defaults to all subscribers. This preserves legacy behavior.

`--tag-name` performs a live `GET /v4/tags` lookup, including during dry-run, because Kit broadcast filters require numeric IDs. Use `--tag-id` for fully offline payload construction.

## Configuration

The CLI loads `.env` from the current directory and parent directories. Public examples use fake values. Private users can run commands through `op run --env-file=.env -- ...` if their `.env` stores secret-manager references.

## Migration Strategy

1. Scaffold public project.
2. Port legacy Markdown conversion and broadcast creation logic.
3. Add tag-targeted payload support and draft behavior.
4. Port read-only analytics from the legacy metrics script.
5. Add offline tests.
6. Replace old internal scripts and docs with direct calls to this CLI.
7. Keep public repo creation and push as an explicit external step.

## Open Risks

- Kit link triggers may not fire for API-created broadcasts unless the API HTML preserves whatever tracking metadata Kit expects. This must be tested separately.
- Kit draft/public/send behavior should be verified with a non-production account or test broadcast before production cutover.
- Kit API response envelopes are not completely consistent across endpoints; analytics commands should keep tests around envelope unwrapping and count fallbacks.
- Repeated unsubscribe POSTs against already-cancelled subscribers are not documented as idempotent; the CLI short-circuits with no-op instead of relying on server behavior.
- Live write-path verification for the CLI unsubscribe command (POST to a throwaway active subscriber) is not part of the default suite; run only with a separate explicit authorization.
- Official docs disagree on whether filter stats ranges outside retention return 400 or are clamped; the CLI reports 400s verbatim and does not rely on silent clamping.

# RFC: Kit Skill Architecture

## Context

The existing Kit workflows lived in internal one-off scripts. One path created Kit API v4 broadcasts from Markdown, while another fetched account growth, email stats, subscriber counts, broadcasts, broadcast stats, and sequence metadata.

This project extracts both workflows into a reusable CLI while keeping write operations explicitly separate from read-only analytics.

## Scope

The skill covers broadcast publishing plus read-only analytics. Subscriber import, tag creation, form automation, visual automation setup, custom unsubscribe link setup, and background syncing remain out of scope.

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

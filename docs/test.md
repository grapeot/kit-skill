# Test Strategy

## Default Offline Tests

Offline tests must run without credentials and without network access.

Coverage goals:

1. Markdown title extraction and preview generation.
2. Broadcast payload construction with legacy defaults.
3. `--tag-id` payload construction.
4. Exact tag-name resolution with a mocked client.
5. `--segment-id` payload construction.
6. `--draft` payload construction.
7. `--web-only` payload construction.
8. CLI dry-run JSON output.
9. Analytics endpoint selection and query params.
10. Subscriber-count fallback logic.
11. Subscriber email redaction in CLI output.
12. Snapshot enrichment with recent broadcast stats.
13. Subscriber lookup by exact email including pagination and ambiguity/absence verdicts.
14. Unsubscribe state gating: stale-list protection via consistent ID re-read, identity mismatch aborts, non-active no-ops, dry-run writes nothing.
15. Unsubscribe write outcomes: 204 plus read-back confirmed, 204 with failed read-back, transport errors, and non-204 responses separated and logged.
16. Attempt-log creation and permissions (exclusive create, 0600, no PII in filename, 0700 directory).
17. Bounce-hygiene scan: request shape, cursor pagination, threshold filtering, null-safe ratios, missing-stats abort, redaction, and unknown-tag or reversed-window argument errors.

Run:

```bash
.venv/bin/python -m pytest -v
```

## Live Tests

Live tests are skipped unless `KIT_ENABLE_LIVE_TESTS=1`, `KIT_LIVE_SEQUENCE_ID`, and `KIT_LIVE_TEST_EMAIL` are set. They should use throwaway tags, test subscribers, and fake/non-production audience paths only.

Live tests must not send to a real production audience. Prefer `--draft`, read-only analytics commands, and a test tag. Consent mutations (`subscribers unsubscribe --execute`) are not part of the automated live suite; a live write-path check for unsubscribe requires its own throwaway active subscriber and a separate explicit authorization.

Run:

```bash
KIT_ENABLE_LIVE_TESTS=1 \
KIT_LIVE_SEQUENCE_ID=123456 \
KIT_LIVE_TEST_EMAIL=kit-e2e-probe@example.com \
.venv/bin/python -m pytest -v -m live_integration
```

## Manual Migration Tests

Before production cutover, verify manually:

1. A test newsletter tag receives a targeted draft.
2. A different test tag does not receive the targeted newsletter broadcast.
3. Kit Link Trigger removes the newsletter tag when clicked from a GUI-created email.
4. Kit Link Trigger removes the newsletter tag when clicked from an API-created broadcast, or the limitation is documented and a signed endpoint fallback is planned.
5. `--draft` creates a state that does not send email.
6. `analytics snapshot` returns growth stats, email stats, recent broadcasts, and per-broadcast stats without network writes beyond reads.

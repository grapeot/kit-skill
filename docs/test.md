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

Run:

```bash
.venv/bin/python -m pytest -v
```

## Live Tests

Live tests are skipped unless `KIT_ENABLE_LIVE_TESTS=1` is set. They should use throwaway tags and test subscribers only.

Live tests must not send to a real production audience. Prefer `--draft` and a test tag.

## Manual Migration Tests

Before production cutover, verify manually:

1. A test newsletter tag receives a targeted draft.
2. A different test tag does not receive the targeted newsletter broadcast.
3. Kit Link Trigger removes the newsletter tag when clicked from a GUI-created email.
4. Kit Link Trigger removes the newsletter tag when clicked from an API-created broadcast, or the limitation is documented and a signed endpoint fallback is planned.
5. `--draft` creates a state that does not send email.

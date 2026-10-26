from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from .broadcast import BroadcastOptions, build_broadcast_payload
from .client import KitClient
from .config import (
    get_api_key,
    get_base_url,
    get_default_email_address,
    get_default_template_id,
    get_timeout,
    load_dotenv,
)

UNSUBSCRIBE_SEMANTICS_NOTE = (
    "Unsubscribe is consent-revoking and effectively permanent; "
    "it applies to all future sends on the account, not just the targeted tag."
)


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def default_date_range() -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=14)
    return start.isoformat(), end.isoformat()


def redact_email(value: str | None) -> str | None:
    if not value or "@" not in value:
        return value
    name, domain = value.split("@", 1)
    if len(name) <= 2:
        masked = name[:1] + "*"
    else:
        masked = name[:2] + "***"
    return f"{masked}@{domain}"


def redact_subscriber_emails(data: Any) -> Any:
    if isinstance(data, list):
        return [redact_subscriber_emails(item) for item in data]
    if not isinstance(data, dict):
        return data
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if key in {"email_address", "email"} and isinstance(value, str):
            redacted[key] = redact_email(value)
        else:
            redacted[key] = redact_subscriber_emails(value)
    return redacted


def validate_single_email(value: str) -> str:
    stripped = value.strip()
    if stripped.count("@") != 1 or any(ch.isspace() or ch == "," for ch in stripped):
        raise ValueError("Expected a single bare email address (one '@', no spaces or commas)")
    return stripped


class PaginationError(Exception):
    pass


def locate_subscriber_by_email(client: KitClient, email: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    after: str | None = None
    seen_cursors: set[str] = set()
    while True:
        data = client.find_subscribers_by_email(email, after=after)
        for row in data.get("subscribers", []):
            if str(row.get("email_address", "")).lower() == email.lower():
                matches.append(row)
        if len(matches) > 1:
            return matches
        pagination = data.get("pagination") or {}
        if not pagination.get("has_next_page"):
            return matches
        cursor = pagination.get("end_cursor")
        if not cursor or str(cursor) in seen_cursors:
            raise PaginationError("pagination ended without a fresh cursor; results may be incomplete")
        seen_cursors.add(str(cursor))
        after = cursor


def subscription_log_dir() -> Path:
    return Path(__file__).resolve().parents[2] / ".local" / "subscription_actions"


def create_attempt_log(subscriber_id: int | str, email: str) -> Path:
    log_dir = subscription_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(log_dir, 0o700)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    body = json.dumps(
        {
            "created_at_utc": datetime.now(UTC).isoformat(),
            "subscriber_id": subscriber_id,
            "email": email,
            "phase": "pre_write",
        },
        ensure_ascii=False,
        indent=2,
    )
    for _ in range(3):
        path = log_dir / f"{stamp}-{uuid.uuid4().hex[:12]}.json"
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
        return path
    raise RuntimeError("Unable to create subscription attempt log")


def update_attempt_log(path: Path | None, record: dict[str, Any]) -> bool:
    if path is None:
        return False
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        existing.update(record)
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(path, 0o600)
        return True
    except (OSError, ValueError):
        print("Warning: subscription attempt log update failed", file=sys.stderr)
        return False


def print_sanitized_http_error(exc: requests.HTTPError) -> None:
    status = exc.response.status_code if exc.response is not None else None
    print(f"HTTP {status}" if status else "HTTP error", file=sys.stderr)


def print_sanitized_transport_error(exc: requests.RequestException) -> None:
    print(f"{type(exc).__name__}: transport error", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kit API v4 broadcast CLI")
    parser.add_argument("--env-file", help="Optional .env file path")

    sub = parser.add_subparsers(dest="cmd", required=True)

    doctor = sub.add_parser("doctor", help="Inspect local configuration")
    doctor_sub = doctor.add_subparsers(dest="doctor_cmd", required=True)
    doctor_config = doctor_sub.add_parser("config", help="Show configuration status")
    doctor_config.add_argument("--format", choices=["text", "json"], default="text")

    broadcast = sub.add_parser("broadcast", help="Broadcast commands")
    broadcast_sub = broadcast.add_subparsers(dest="broadcast_cmd", required=True)

    send = broadcast_sub.add_parser("send", help="Create a broadcast from Markdown")
    send.add_argument("markdown_file", help="Markdown file to publish")
    send.add_argument("--format", choices=["text", "json"], default="text")
    send.add_argument("--subject", "-s", help="Email subject; defaults to first Markdown H1")
    send.add_argument("--preview", "-p", help="Preview text; defaults to first content text")
    send.add_argument("--description", help="Internal Kit description; defaults to subject")
    send.add_argument("--email-address", "--email", "-e", help="Sender email address")
    send.add_argument("--email-template-id", type=int, help="Kit email template ID")
    send.add_argument("--schedule-minutes", "--schedule", "-t", type=int, default=2)
    send.add_argument("--draft", action="store_true", help="Create a draft only; do not schedule send")
    send.add_argument("--web-only", "--no-email", action="store_true", help="Publish web post only")
    send.add_argument("--publish", dest="publish", action="store_true", default=True)
    send.add_argument("--no-publish", dest="publish", action="store_false")
    send.add_argument("--tag-id", type=int, action="append", default=[], help="Target a Kit tag ID")
    send.add_argument("--tag-name", action="append", default=[], help="Target a Kit tag by exact name")
    send.add_argument("--segment-id", type=int, action="append", default=[], help="Target a Kit segment ID")
    send.add_argument("--filter-mode", choices=["all", "any", "none"], default="all")
    send.add_argument("--dry-run", "-n", action="store_true", help="Print payload without API write")

    stats = broadcast_sub.add_parser("stats", help="Get broadcast stats")
    stats.add_argument("broadcast_id", help="Broadcast ID")
    stats.add_argument("--format", choices=["text", "json"], default="text")

    subscribers_group = sub.add_parser("subscribers", help="Subscriber lookup and consent mutations")
    subscribers_sub = subscribers_group.add_subparsers(dest="subscribers_cmd", required=True)

    show = subscribers_sub.add_parser("show", help="Read one subscriber by exact email address")
    show.add_argument("email", help="Exact email address (single bare address)")
    show.add_argument("--show-emails", action="store_true", help="Print the raw subscriber email")
    show.add_argument("--format", choices=["text", "json"], default="json")

    unsubscribe = subscribers_sub.add_parser(
        "unsubscribe",
        help="Unsubscribe one subscriber (consent-revoking, account-wide, effectively permanent)",
    )
    unsubscribe.add_argument("email", help="Exact email address (single bare address)")
    unsubscribe.add_argument("--execute", action="store_true", help="Actually unsubscribe; default is dry-run")
    unsubscribe.add_argument("--show-emails", action="store_true", help="Print the raw subscriber email")
    unsubscribe.add_argument("--format", choices=["text", "json"], default="json")

    analytics = sub.add_parser("analytics", help="Read-only analytics and subscriber metrics")
    analytics_sub = analytics.add_subparsers(dest="analytics_cmd", required=True)

    analytics_account = analytics_sub.add_parser("account", help="Show account info")
    analytics_account.add_argument("--format", choices=["text", "json"], default="json")

    analytics_growth = analytics_sub.add_parser("growth", help="Subscriber growth stats")
    analytics_growth.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    analytics_growth.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    analytics_growth.add_argument("--format", choices=["text", "json"], default="json")

    analytics_email_stats = analytics_sub.add_parser("email-stats", help="Aggregated open/click stats")
    analytics_email_stats.add_argument("--format", choices=["text", "json"], default="json")

    subscriber_count = analytics_sub.add_parser("subscriber-count", help="Active subscriber count")
    subscriber_count.add_argument("--status", default="active")
    subscriber_count.add_argument(
        "--tag", help="Count subscribers with this tag name or id instead of the whole account"
    )
    subscriber_count.add_argument("--format", choices=["text", "json"], default="text")

    tags = analytics_sub.add_parser("tags", help="List tags")
    tags.add_argument("--format", choices=["text", "json"], default="text")

    subscribers = analytics_sub.add_parser("subscribers", help="Subscriber list or count")
    subscribers.add_argument("--status", default="active")
    subscribers.add_argument("--limit", type=int, default=50)
    subscribers.add_argument("--count", action="store_true")
    subscribers.add_argument("--show-emails", action="store_true", help="Print raw subscriber emails")
    subscribers.add_argument("--format", choices=["text", "json"], default="json")

    broadcasts = analytics_sub.add_parser("broadcasts", help="List recent broadcasts")
    broadcasts.add_argument("--limit", type=int, default=10)
    broadcasts.add_argument("--format", choices=["text", "json"], default="json")

    analytics_broadcast_stats = analytics_sub.add_parser("broadcast-stats", help="Stats for one broadcast")
    analytics_broadcast_stats.add_argument("broadcast_id", help="Broadcast ID")
    analytics_broadcast_stats.add_argument("--format", choices=["text", "json"], default="json")

    hygiene = analytics_sub.add_parser(
        "bounce-hygiene",
        help="Find members of a tag with high account-level bounce counts in a stats window",
    )
    hygiene.add_argument("--tag", required=True, help="Tag name or numeric id to scan")
    hygiene.add_argument("--since", required=True, help="Stats window start (YYYY-MM-DD, inclusive of retention rules)")
    hygiene.add_argument("--until", help="Stats window end (YYYY-MM-DD); defaults to today")
    hygiene.add_argument("--min-bounced", type=int, default=3, help="Candidate threshold on bounced count")
    hygiene.add_argument("--per-page", type=int, default=500, help="Filter page size (max 1000)")
    hygiene.add_argument("--show-emails", action="store_true", help="Print raw subscriber emails")
    hygiene.add_argument("--format", choices=["text", "json"], default="json")

    sequences = analytics_sub.add_parser("sequences", help="List email sequences")
    sequences.add_argument("--limit", type=int, default=50)
    sequences.add_argument("--format", choices=["text", "json"], default="json")

    sequence = analytics_sub.add_parser("sequence", help="Show one email sequence")
    sequence.add_argument("sequence_id", help="Sequence ID")
    sequence.add_argument("--include-subscribers", action="store_true")
    sequence.add_argument("--show-emails", action="store_true", help="Print raw subscriber emails")
    sequence.add_argument("--format", choices=["text", "json"], default="json")

    snapshot = analytics_sub.add_parser("snapshot", help="Fetch growth, email stats, and recent broadcasts")
    snapshot.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    snapshot.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    snapshot.add_argument("--broadcasts-limit", type=int, default=10)
    snapshot.add_argument("--output", help="Write JSON output to file")
    snapshot.add_argument("--format", choices=["text", "json"], default="json")

    return parser


def build_client() -> KitClient:
    return KitClient(api_key=get_api_key(), base_url=get_base_url(), timeout=get_timeout())


def resolve_tag_names(client: KitClient, tag_names: list[str]) -> list[int]:
    if not tag_names:
        return []
    data = client.list_tags()
    tags = data.get("tags", [])
    name_to_id = {tag.get("name"): tag.get("id") for tag in tags if tag.get("name")}
    missing = [name for name in tag_names if name not in name_to_id]
    if missing:
        available = ", ".join(sorted(str(name) for name in name_to_id))
        raise ValueError(f"Tag name(s) not found: {', '.join(missing)}. Available tags: {available}")
    return [int(name_to_id[name]) for name in tag_names]


def handle_doctor_config(format_name: str, loaded_env: Path | None) -> int:
    try:
        api_key = get_api_key()
        api_key_status = "configured" if api_key else "missing"
    except ValueError as exc:
        api_key_status = str(exc)
    data = {
        "loaded_env": str(loaded_env) if loaded_env else None,
        "base_url": get_base_url(),
        "timeout": get_timeout(),
        "api_key": api_key_status,
        "default_email_address": get_default_email_address(),
        "default_email_template_id": get_default_template_id(),
    }
    if format_name == "json":
        print_json(data)
    else:
        for key, value in data.items():
            print(f"{key}: {value}")
    return 0


def handle_broadcast_send(args: argparse.Namespace, format_name: str) -> int:
    markdown_path = Path(args.markdown_file)
    if not markdown_path.exists():
        raise SystemExit(f"Markdown file not found: {markdown_path}")

    tag_ids = list(args.tag_id)
    if args.tag_name:
        tag_ids.extend(resolve_tag_names(build_client(), args.tag_name))

    options = BroadcastOptions(
        subject=args.subject,
        preview_text=args.preview,
        description=args.description,
        email_address=args.email_address or get_default_email_address(),
        email_template_id=args.email_template_id or get_default_template_id(),
        publish=args.publish,
        schedule_minutes=args.schedule_minutes,
        draft=args.draft,
        web_only=args.web_only,
        tag_ids=tag_ids,
        segment_ids=args.segment_id,
        filter_mode=args.filter_mode,
    )
    payload = build_broadcast_payload(markdown_path, options)

    if args.dry_run:
        result = {"dry_run": True, "payload": payload}
        if format_name == "json":
            print_json(result)
        else:
            print("[DRY RUN] Would create broadcast:")
            print(f"  Subject: {payload.get('subject')}")
            print(f"  Public: {payload.get('public')}")
            print(f"  Send at: {payload.get('send_at')}")
            if payload.get("subscriber_filter"):
                print(f"  Subscriber filter: {payload['subscriber_filter']}")
        return 0

    client = build_client()
    broadcast = client.create_broadcast(payload)
    if format_name == "json":
        print_json({"broadcast": broadcast})
    else:
        print("Broadcast created!")
        print(f"  ID: {broadcast.get('id')}")
        print(f"  Subject: {broadcast.get('subject')}")
        print(f"  Public: {broadcast.get('public')}")
        print(f"  Public URL: {broadcast.get('public_url')}")
        print(f"  Send at: {broadcast.get('send_at')}")
    return 0


def handle_broadcast_stats(args: argparse.Namespace, format_name: str) -> int:
    client = build_client()
    data = client.broadcast_stats(args.broadcast_id)
    if format_name == "json":
        print_json(data)
    else:
        stats = data.get("broadcast", {}).get("stats", data.get("stats", {}))
        print(f"Broadcast {args.broadcast_id} stats:")
        print(f"  Status: {stats.get('status', 'unknown')}")
        print(f"  Recipients: {stats.get('recipients')}")
        print(f"  Open rate: {stats.get('open_rate')}")
        print(f"  Click rate: {stats.get('click_rate')}")
    return 0


def _resolved_subscriber(client: KitClient, email: str, format_name: str) -> tuple[dict[str, Any] | None, int]:
    try:
        matches = locate_subscriber_by_email(client, email)
    except PaginationError as exc:
        print(f"Locate incomplete: {exc}", file=sys.stderr)
        return None, 1
    except requests.HTTPError as exc:
        print_sanitized_http_error(exc)
        return None, 1
    except requests.RequestException as exc:
        print_sanitized_transport_error(exc)
        return None, 1
    if len(matches) != 1:
        outcome = "not_found" if not matches else "ambiguous"
        print_json({"outcome": outcome, "email_address": redact_email(email)})
        return None, 0
    return matches[0], 0


def _fresh_subscriber(client: KitClient, subscriber_id: int | str) -> dict[str, Any] | None:
    try:
        return client.get_subscriber(subscriber_id)
    except requests.HTTPError as exc:
        print_sanitized_http_error(exc)
        return None
    except requests.RequestException as exc:
        print_sanitized_transport_error(exc)
        return None


def _outcome_record(
    email: str,
    row: dict[str, Any],
    outcome: str,
    extra: dict[str, Any] | None = None,
    show_email: bool = False,
) -> dict[str, Any]:
    data = {
        "outcome": outcome,
        "subscriber_id": row.get("id"),
        "email_address": row.get("email_address") if show_email else redact_email(row.get("email_address") or email),
        "state": row.get("state"),
        "note": UNSUBSCRIBE_SEMANTICS_NOTE,
    }
    if extra:
        data.update(extra)
    return data


def handle_subscribers_show(args: argparse.Namespace, format_name: str) -> int:
    try:
        email = validate_single_email(args.email)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    client = build_client()
    row, code = _resolved_subscriber(client, email, format_name)
    if row is None:
        return code
    fresh = _fresh_subscriber(client, row.get("id"))
    if not isinstance(fresh, dict):
        return 1
    if str(fresh.get("id")) != str(row.get("id")) or str(fresh.get("email_address", "")).lower() != email.lower():
        print("Located subscriber identity mismatch on consistent re-read; aborting", file=sys.stderr)
        return 1
    data = {
        "id": fresh.get("id"),
        "state": fresh.get("state"),
        "created_at": fresh.get("created_at"),
        "email_address": fresh.get("email_address") if args.show_emails else redact_email(fresh.get("email_address")),
    }
    print_json(data)
    return 0


def handle_subscribers_unsubscribe(args: argparse.Namespace, format_name: str) -> int:
    try:
        email = validate_single_email(args.email)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    show_email = bool(args.show_emails)
    client = build_client()
    row, code = _resolved_subscriber(client, email, format_name)
    if row is None:
        return code
    subscriber_id = row.get("id")
    fresh = _fresh_subscriber(client, subscriber_id)
    if not isinstance(fresh, dict):
        return 1
    if str(fresh.get("id")) != str(subscriber_id) or str(
        fresh.get("email_address", "")
    ).lower() != email.lower():
        print_json(
            _outcome_record(
                email,
                {"id": subscriber_id, "email_address": redact_email(email)},
                "error",
                {"error": "identity mismatch on consistent re-read; aborting"},
                show_email=show_email,
            )
        )
        return 1
    fresh["id"] = subscriber_id
    fresh["email_address"] = fresh.get("email_address", email)
    state = fresh.get("state")
    if state == "active":
        if not args.execute:
            print_json(_outcome_record(email, fresh, "dry_run", show_email=show_email))
            return 0
    else:
        if state == "cancelled":
            outcome = "already_cancelled"
        elif state in {"inactive", "bounced", "complained"}:
            outcome = "skipped_non_active"
        else:
            print("Unknown or missing subscriber state; refusing to unsubscribe", file=sys.stderr)
            print_json(_outcome_record(email, fresh, "error", {"error": "unknown or missing state"}, show_email=show_email))
            return 1
        print_json(_outcome_record(email, fresh, outcome, show_email=show_email))
        return 0

    try:
        attempt_path: Path | None = create_attempt_log(subscriber_id, email)
    except (OSError, RuntimeError) as exc:
        print(f"Refusing to unsubscribe: cannot create local attempt log: {type(exc).__name__}", file=sys.stderr)
        return 1
    try:
        status = client.unsubscribe_subscriber(subscriber_id)
    except requests.RequestException as exc:
        audit_ok = update_attempt_log(attempt_path, {"outcome": "write_outcome_unknown", "error": type(exc).__name__})
        print_sanitized_transport_error(exc)
        print_json(
            _outcome_record(
                email,
                fresh,
                "write_outcome_unknown",
                {"error": type(exc).__name__, "attempt_log": str(attempt_path), "attempt_log_status": "updated" if audit_ok else "update_failed"},
                show_email=show_email,
            )
        )
        return 1
    if status != 204:
        audit_ok = update_attempt_log(attempt_path, {"outcome": "write_outcome_unknown", "http_status": status})
        print(
            f"Unsubscribe returned HTTP {status} instead of 204; outcome unknown", file=sys.stderr
        )
        print_json(
            _outcome_record(
                email,
                fresh,
                "write_outcome_unknown",
                {"http_status": status, "attempt_log": str(attempt_path), "attempt_log_status": "updated" if audit_ok else "update_failed"},
                show_email=show_email,
            )
        )
        return 1
    after = _fresh_subscriber(client, subscriber_id)
    if not isinstance(after, dict):
        audit_ok = update_attempt_log(
            attempt_path,
            {"outcome": "write_succeeded_verification_failed", "http_status": status},
        )
        print("Unsubscribe accepted but verification read failed; recheck later with subscribers show", file=sys.stderr)
        print_json(
            _outcome_record(
                email,
                fresh,
                "write_succeeded_verification_failed",
                {"http_status": status, "attempt_log": str(attempt_path), "attempt_log_status": "updated" if audit_ok else "update_failed"},
                show_email=show_email,
            )
        )
        return 1
    after_state = after.get("state")
    if after_state == "cancelled":
        audit_ok = update_attempt_log(
            attempt_path,
            {
                "outcome": "confirmed_cancelled",
                "state_before": state,
                "state_after": after_state,
                "http_status": status,
                "confirmed_at_utc": datetime.now(UTC).isoformat(),
            },
        )
        print_json(
            _outcome_record(
                email,
                after,
                "confirmed_cancelled",
                {
                    "state_before": state,
                    "state_after": after_state,
                    "http_status": status,
                    "attempt_log": str(attempt_path),
                    "attempt_log_status": "updated" if audit_ok else "update_failed",
                },
                show_email=show_email,
            )
        )
        return 0
    audit_ok = update_attempt_log(
        attempt_path,
        {"outcome": "write_succeeded_verification_failed", "http_status": status, "state_after": after_state},
    )
    print(f"Unsubscribe accepted but read-back state is {after_state!r}", file=sys.stderr)
    print_json(
        _outcome_record(
            email,
            after,
            "write_succeeded_verification_failed",
            {
                "http_status": status,
                "state_after": after_state,
                "attempt_log": str(attempt_path),
                "attempt_log_status": "updated" if audit_ok else "update_failed",
            },
            show_email=show_email,
        )
    )
    return 1


def handle_analytics_bounce_hygiene(args: argparse.Namespace, format_name: str) -> int:
    try:
        since = date.fromisoformat(str(args.since))
        until = date.fromisoformat(str(args.until)) if args.until else date.today()
    except ValueError:
        print("--since/--until must be YYYY-MM-DD dates", file=sys.stderr)
        return 2
    if since >= until:
        print("--since must be earlier than --until", file=sys.stderr)
        return 2
    per_page = min(int(args.per_page), 1000)
    client = build_client()
    tag_input = str(args.tag)
    try:
        tag_id: int | str
        if tag_input.isdigit():
            tag_id = int(tag_input)
        else:
            tags_data = client.list_tags()
            matching = [
                tag
                for tag in tags_data.get("tags", [])
                if str(tag.get("name", "")).lower() == tag_input.lower() and tag.get("id") is not None
            ]
            if len(matching) != 1:
                print(f"Tag not found or ambiguous: {tag_input!r}", file=sys.stderr)
                return 2
            tag_id = matching[0]["id"]
        payload = {
            "all": [
                {"type": "subscriber_state", "states": ["active"]},
                {"type": "tags", "any": [{"type": "ids", "matching": [tag_id]}]},
            ],
            "include": [
                {"type": "stats", "range": {"start": since.isoformat(), "end": until.isoformat()}}
            ],
        }
        candidates: list[dict[str, Any]] = []
        scanned: int | None = None
        seen = 0
        after: str | None = None
        seen_cursors: set[str] = set()
        while True:
            data = client.filter_subscribers(payload, per_page=per_page, after=after)
            page_rows = data.get("subscribers", [])
            seen += len(page_rows)
            if scanned is None:
                total = (data.get("pagination") or {}).get("total_count")
                if isinstance(total, int):
                    scanned = total
            for row in page_rows:
                stats = row.get("stats")
                if not isinstance(stats, dict):
                    print("Subscriber stats missing in filter response; scan aborted", file=sys.stderr)
                    return 1
                try:
                    bounced = int(stats.get("bounced") or 0)
                    sent = int(stats.get("sent") or 0)
                    opened = int(stats.get("opened") or 0)
                    clicked = int(stats.get("clicked") or 0)
                except (TypeError, ValueError):
                    print("Invalid stats value in filter response; scan aborted", file=sys.stderr)
                    return 1
                if bounced < int(args.min_bounced):
                    continue
                candidates.append(
                    {
                        "id": row.get("id"),
                        "created_at": row.get("created_at"),
                        "email_address": row.get("email_address")
                        if args.show_emails
                        else redact_email(row.get("email_address")),
                        "stats": {
                            "sent": sent,
                            "opened": opened,
                            "clicked": clicked,
                            "bounced": bounced,
                            "last_sent": stats.get("last_sent"),
                        },
                        "bounce_ratio": (bounced / sent) if sent else None,
                    }
                )
            pagination = data.get("pagination") or {}
            if not pagination.get("has_next_page"):
                break
            cursor = pagination.get("end_cursor")
            if not cursor or str(cursor) in seen_cursors:
                raise PaginationError("pagination ended without a fresh cursor; scan is incomplete")
            seen_cursors.add(str(cursor))
            after = cursor
    except PaginationError as exc:
        print(f"Scan incomplete: {exc}", file=sys.stderr)
        return 1
    except requests.HTTPError as exc:
        print_sanitized_http_error(exc)
        print("Scan incomplete; treating result as unreliable", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print_sanitized_transport_error(exc)
        print("Scan incomplete; treating result as unreliable", file=sys.stderr)
        return 1
    candidates.sort(key=lambda item: item["stats"]["bounced"], reverse=True)
    if scanned is None:
        scanned = seen
    output = {
        "tag": tag_input,
        "requested_states": ["active"],
        "window": {"start": since.isoformat(), "end": until.isoformat()},
        "scanned": scanned,
        "min_bounced": int(args.min_bounced),
        "candidates": candidates,
        "note": "Account-level email stats for current tag members; for manual investigation only. "
        "High bounce counts are not hard-bounce verdicts or auto-unsubscribe grounds.",
    }
    print_json(output)
    return 0


def handle_analytics(args: argparse.Namespace, format_name: str) -> int:
    client = build_client()
    default_start, default_end = default_date_range()
    start_date = getattr(args, "start_date", None) or default_start
    end_date = getattr(args, "end_date", None) or default_end

    if args.analytics_cmd == "account":
        data = client.account()
    elif args.analytics_cmd == "growth":
        data = client.growth_stats(start_date, end_date)
    elif args.analytics_cmd == "email-stats":
        data = client.email_stats()
    elif args.analytics_cmd == "subscriber-count":
        if args.tag:
            count = client.tag_subscriber_count(args.tag, status=args.status)
            data = {"tag": args.tag, "status": args.status, "count": count}
        else:
            count = client.subscriber_count(status=args.status)
            data = {"status": args.status, "count": count}
        if format_name == "text":
            print(count)
            return 0
    elif args.analytics_cmd == "tags":
        raw = client.list_tags().get("tags", [])
        data = [
            {"id": tag.get("id"), "name": tag.get("name"), "created_at": tag.get("created_at")}
            for tag in raw
        ]
    elif args.analytics_cmd == "subscribers":
        if args.count:
            count = client.subscriber_count(status=args.status)
            data = {"status": args.status, "count": count}
            if format_name == "text":
                print(count)
                return 0
        else:
            data = client.subscribers(status=args.status, per_page=args.limit)
            if not args.show_emails:
                data = redact_subscriber_emails(data)
    elif args.analytics_cmd == "broadcasts":
        raw = client.broadcasts(per_page=args.limit).get("broadcasts", [])
        data = [
            {
                "id": broadcast.get("id"),
                "subject": broadcast.get("subject"),
                "published_at": broadcast.get("published_at"),
                "recipients": broadcast.get("recipients"),
            }
            for broadcast in sorted(raw, key=lambda item: item.get("published_at") or "", reverse=True)
        ]
    elif args.analytics_cmd == "broadcast-stats":
        data = client.broadcast_stats(args.broadcast_id)
    elif args.analytics_cmd == "sequences":
        raw = client.sequences(per_page=args.limit).get("sequences", [])
        data = [
            {
                "id": sequence.get("id"),
                "name": sequence.get("name"),
                "active": sequence.get("active"),
                "email_count": sequence.get("email_count"),
                "subscriber_count": sequence.get("subscriber_count"),
                "created_at": sequence.get("created_at"),
            }
            for sequence in raw
        ]
    elif args.analytics_cmd == "sequence":
        sequence = client.sequence(args.sequence_id)
        data = {
            "id": sequence.get("id"),
            "name": sequence.get("name"),
            "active": sequence.get("active"),
            "email_count": sequence.get("email_count"),
            "subscriber_count": sequence.get("subscriber_count"),
            "send_hour": sequence.get("send_hour"),
            "time_zone": sequence.get("time_zone"),
        }
        if args.include_subscribers:
            subscribers = client.sequence_subscribers(args.sequence_id, status="active", per_page=50)
            data["active_subscribers"] = subscribers.get("subscribers", [])
            if not args.show_emails:
                data = redact_subscriber_emails(data)
    elif args.analytics_cmd == "snapshot":
        data = client.snapshot(start_date, end_date, broadcasts_limit=args.broadcasts_limit)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved to {output_path}")
            return 0
    else:
        raise ValueError(f"Unknown analytics command: {args.analytics_cmd}")

    if format_name == "json":
        print_json(data)
    else:
        print_json(data)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    loaded_env = load_dotenv(args.env_file)

    try:
        if args.cmd == "doctor" and args.doctor_cmd == "config":
            return handle_doctor_config(args.format, loaded_env)
        if args.cmd == "broadcast" and args.broadcast_cmd == "send":
            return handle_broadcast_send(args, args.format)
        if args.cmd == "broadcast" and args.broadcast_cmd == "stats":
            return handle_broadcast_stats(args, args.format)
        if args.cmd == "subscribers" and args.subscribers_cmd == "show":
            return handle_subscribers_show(args, args.format)
        if args.cmd == "subscribers" and args.subscribers_cmd == "unsubscribe":
            return handle_subscribers_unsubscribe(args, args.format)
        if args.cmd == "analytics":
            if args.analytics_cmd == "bounce-hygiene":
                return handle_analytics_bounce_hygiene(args, args.format)
            return handle_analytics(args, args.format)
        parser.print_help()
        return 1
    except requests.HTTPError as exc:
        print_sanitized_http_error(exc)
        return 1
    except requests.RequestException as exc:
        print_sanitized_transport_error(exc)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

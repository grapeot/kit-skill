from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
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
    subscriber_count.add_argument("--format", choices=["text", "json"], default="text")

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
        count = client.subscriber_count(status=args.status)
        data = {"status": args.status, "count": count}
        if format_name == "text":
            print(count)
            return 0
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
        if args.cmd == "analytics":
            return handle_analytics(args, args.format)
        parser.print_help()
        return 1
    except requests.HTTPError as exc:
        response = exc.response
        if response is not None:
            print(f"HTTP {response.status_code}: {response.text}", file=sys.stderr)
        else:
            print(f"HTTP error: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
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

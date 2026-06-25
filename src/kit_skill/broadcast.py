from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from .markdown_render import build_preview, extract_title, md_to_html

FilterMode = Literal["all", "any", "none"]


@dataclass
class BroadcastOptions:
    subject: str | None = None
    preview_text: str | None = None
    description: str | None = None
    email_address: str | None = None
    email_template_id: int | None = None
    publish: bool = True
    schedule_minutes: int = 2
    draft: bool = False
    web_only: bool = False
    tag_ids: list[int] = field(default_factory=list)
    segment_ids: list[int] = field(default_factory=list)
    filter_mode: FilterMode = "all"


def build_subscriber_filter(
    *,
    tag_ids: list[int] | None = None,
    segment_ids: list[int] | None = None,
    filter_mode: FilterMode = "all",
) -> list[dict[str, Any]] | None:
    tag_ids = tag_ids or []
    segment_ids = segment_ids or []
    filters: list[dict[str, Any]] = []
    if tag_ids:
        filters.append({"type": "tag", "ids": tag_ids})
    if segment_ids:
        filters.append({"type": "segment", "ids": segment_ids})
    if not filters:
        return None
    return [
        {
            "all": filters if filter_mode == "all" else None,
            "any": filters if filter_mode == "any" else None,
            "none": filters if filter_mode == "none" else None,
        }
    ]


def build_broadcast_payload(markdown_path: Path, options: BroadcastOptions) -> dict[str, Any]:
    markdown = markdown_path.read_text(encoding="utf-8")
    subject = options.subject or extract_title(markdown, markdown_path.stem)
    preview_text = options.preview_text or build_preview(markdown)
    description = options.description or subject
    html_content = md_to_html(markdown, title=subject)

    now = datetime.now(timezone.utc)
    public = options.publish
    if options.draft:
        public = False
        send_at = None
    elif options.web_only:
        public = True
        # Legacy backfill behavior: Kit generates a public slug without a future send.
        send_at = (now - timedelta(minutes=1)).isoformat()
    else:
        send_at = (
            (now + timedelta(minutes=options.schedule_minutes)).isoformat()
            if options.schedule_minutes > 0
            else None
        )

    payload: dict[str, Any] = {
        "subject": subject,
        "preview_text": preview_text,
        "description": description,
        "content": html_content,
        "public": public,
        "published_at": now.isoformat(),
        "send_at": send_at,
    }

    if options.email_template_id is not None:
        payload["email_template_id"] = options.email_template_id
    if options.email_address:
        payload["email_address"] = options.email_address

    subscriber_filter = build_subscriber_filter(
        tag_ids=options.tag_ids,
        segment_ids=options.segment_ids,
        filter_mode=options.filter_mode,
    )
    if subscriber_filter is not None:
        payload["subscriber_filter"] = subscriber_filter

    return payload

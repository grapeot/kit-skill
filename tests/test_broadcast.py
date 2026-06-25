from __future__ import annotations

import json
from pathlib import Path

from kit_skill.broadcast import BroadcastOptions, build_broadcast_payload, build_subscriber_filter


def _sample_md(tmp_path: Path) -> Path:
    path = tmp_path / "newsletter.md"
    path.write_text("# Hello Kit\n\nThis is a **test** newsletter.", encoding="utf-8")
    return path


def test_subscriber_filter_for_tag() -> None:
    assert build_subscriber_filter(tag_ids=[123], filter_mode="all") == [
        {"all": [{"type": "tag", "ids": [123]}], "any": None, "none": None}
    ]


def test_subscriber_filter_for_segment_any() -> None:
    assert build_subscriber_filter(segment_ids=[456], filter_mode="any") == [
        {"all": None, "any": [{"type": "segment", "ids": [456]}], "none": None}
    ]


def test_payload_preserves_legacy_defaults_when_configured(tmp_path: Path) -> None:
    payload = build_broadcast_payload(
        _sample_md(tmp_path),
        BroadcastOptions(email_address="sender@example.com", email_template_id=111),
    )

    assert payload["subject"] == "Hello Kit"
    assert payload["preview_text"].startswith("This is a test newsletter")
    assert payload["public"] is True
    assert payload["send_at"] is not None
    assert payload["email_address"] == "sender@example.com"
    assert payload["email_template_id"] == 111
    assert "subscriber_filter" not in payload


def test_payload_with_tag_targeting(tmp_path: Path) -> None:
    payload = build_broadcast_payload(_sample_md(tmp_path), BroadcastOptions(tag_ids=[123]))

    assert payload["subscriber_filter"] == [
        {"all": [{"type": "tag", "ids": [123]}], "any": None, "none": None}
    ]


def test_draft_overrides_publish_and_schedule(tmp_path: Path) -> None:
    payload = build_broadcast_payload(
        _sample_md(tmp_path),
        BroadcastOptions(draft=True, publish=True, schedule_minutes=2),
    )

    assert payload["public"] is False
    assert payload["send_at"] is None


def test_web_only_uses_past_send_at(tmp_path: Path) -> None:
    payload = build_broadcast_payload(_sample_md(tmp_path), BroadcastOptions(web_only=True))

    assert payload["public"] is True
    assert payload["send_at"] is not None


def test_payload_is_json_serializable(tmp_path: Path) -> None:
    payload = build_broadcast_payload(_sample_md(tmp_path), BroadcastOptions(tag_ids=[123]))
    json.dumps(payload)

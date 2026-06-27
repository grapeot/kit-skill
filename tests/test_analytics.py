from __future__ import annotations

import json
import os

import pytest
import requests

from kit_skill.client import KitClient
from kit_skill.cli import main, redact_email


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_data=None, text: str | None = None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text if text is not None else ("{}" if json_data is None else "x")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self._json


def _client() -> KitClient:
    return KitClient(api_key="test-key", base_url="https://api.kit.test/v4", timeout=3)


def test_growth_stats_calls_correct_endpoint(monkeypatch) -> None:
    captured = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(json_data={"growth_stats": {"net_new_subscribers": 3}})

    monkeypatch.setattr(requests, "get", fake_get)

    data = _client().growth_stats("2026-03-01", "2026-03-14")

    assert captured["url"].endswith("/account/growth_stats")
    assert captured["params"] == {"starting": "2026-03-01", "ending": "2026-03-14"}
    assert data["growth_stats"]["net_new_subscribers"] == 3


def test_subscriber_count_reads_pagination_total(monkeypatch) -> None:
    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(json_data={"pagination": {"total_count": 42}, "subscribers": []})

    monkeypatch.setattr(requests, "get", fake_get)

    assert _client().subscriber_count() == 42


def test_sequences_calls_correct_endpoint(monkeypatch) -> None:
    captured = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(json_data={"sequences": [{"id": 1, "name": "Welcome"}]})

    monkeypatch.setattr(requests, "get", fake_get)

    data = _client().sequences(per_page=25)

    assert captured["url"].endswith("/sequences")
    assert captured["params"]["per_page"] == 25
    assert data["sequences"][0]["name"] == "Welcome"


def test_sequence_unwraps_envelope(monkeypatch) -> None:
    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(json_data={"sequence": {"id": 7, "active": True, "email_count": 3}})

    monkeypatch.setattr(requests, "get", fake_get)

    sequence = _client().sequence(7)
    assert sequence["id"] == 7
    assert sequence["active"] is True
    assert sequence["email_count"] == 3


def test_sequence_subscriber_count_missing_counter_is_zero(monkeypatch) -> None:
    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(json_data={"sequence": {"id": 7}})

    monkeypatch.setattr(requests, "get", fake_get)

    assert _client().sequence_subscriber_count(7) == 0


def test_sequence_subscribers_passes_status(monkeypatch) -> None:
    captured = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(json_data={"subscribers": []})

    monkeypatch.setattr(requests, "get", fake_get)

    _client().sequence_subscribers(7, status="active", per_page=50)

    assert captured["url"].endswith("/sequences/7/subscribers")
    assert captured["params"]["status"] == "active"
    assert captured["params"]["include_total_count"] == "true"


def test_add_subscriber_to_sequence_posts_email(monkeypatch) -> None:
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["content_type"] = headers.get("Content-Type")
        return _FakeResponse(json_data={"subscriber": {"id": 99}})

    monkeypatch.setattr(requests, "post", fake_post)

    out = _client().add_subscriber_to_sequence(7, "person@example.com")

    assert captured["url"].endswith("/sequences/7/subscribers")
    assert captured["json"]["email_address"] == "person@example.com"
    assert captured["content_type"] == "application/json"
    assert out["subscriber"]["id"] == 99


def test_post_raises_on_rate_limit(monkeypatch) -> None:
    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(status_code=429)

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(requests.HTTPError):
        _client().add_subscriber_to_sequence(7, "x@example.com")


def test_analytics_subscribers_redacts_emails_by_default(monkeypatch, capsys) -> None:
    monkeypatch.setenv("KIT_API_KEY", "test-key")

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(json_data={"subscribers": [{"email_address": "person@example.com"}]})

    monkeypatch.setattr(requests, "get", fake_get)

    code = main(["analytics", "subscribers", "--format", "json"])

    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["subscribers"][0]["email_address"] == "pe***@example.com"


def test_analytics_subscriber_count_text(monkeypatch, capsys) -> None:
    monkeypatch.setenv("KIT_API_KEY", "test-key")

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(json_data={"pagination": {"total_count": 12}, "subscribers": []})

    monkeypatch.setattr(requests, "get", fake_get)

    code = main(["analytics", "subscriber-count"])

    assert code == 0
    assert capsys.readouterr().out.strip() == "12"


def test_snapshot_enriches_recent_broadcasts(monkeypatch) -> None:
    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/account/growth_stats"):
            return _FakeResponse(json_data={"growth_stats": {}})
        if url.endswith("/account/email_stats"):
            return _FakeResponse(json_data={"email_stats": {}})
        if url.endswith("/broadcasts"):
            return _FakeResponse(json_data={"broadcasts": [{"id": 123, "subject": "Test"}]})
        if url.endswith("/broadcasts/123/stats"):
            return _FakeResponse(json_data={"broadcast": {"stats": {"open_rate": 0.5}}})
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(requests, "get", fake_get)

    data = _client().snapshot("2026-03-01", "2026-03-14", broadcasts_limit=1)

    assert data["recent_broadcasts"][0]["id"] == 123
    assert data["recent_broadcasts"][0]["stats"]["broadcast"]["stats"]["open_rate"] == 0.5


def test_redact_email_handles_short_names() -> None:
    assert redact_email("a@example.com") == "a*@example.com"


@pytest.mark.live_integration
@pytest.mark.skipif(
    os.getenv("KIT_ENABLE_LIVE_TESTS") != "1"
    or not os.getenv("KIT_LIVE_SEQUENCE_ID")
    or not os.getenv("KIT_LIVE_TEST_EMAIL"),
    reason="live Kit e2e disabled; set KIT_ENABLE_LIVE_TESTS=1, KIT_LIVE_SEQUENCE_ID, and KIT_LIVE_TEST_EMAIL",
)
def test_live_sequence_accepts_subscriber() -> None:
    sequence_id = os.environ["KIT_LIVE_SEQUENCE_ID"]
    test_email = os.environ["KIT_LIVE_TEST_EMAIL"]
    client = KitClient(
        api_key=os.environ["KIT_API_KEY"],
        base_url=os.getenv("KIT_BASE_URL", "https://api.kit.com/v4"),
        timeout=int(os.getenv("KIT_TIMEOUT", "30")),
    )

    before = client.sequence(sequence_id)
    assert before.get("active") is True
    assert (before.get("email_count") or 0) >= 1
    count_before = int(before.get("subscriber_count") or 0)

    client.create_subscriber(test_email)
    result = client.add_subscriber_to_sequence(sequence_id, test_email)
    assert result

    after = client.sequence(sequence_id)
    assert int(after.get("subscriber_count") or 0) >= count_before

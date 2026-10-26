from __future__ import annotations

import json
import stat

import requests

import kit_skill.cli as cli
from kit_skill.cli import main


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=None, forbid_json=False):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text if text is not None else "content"
        self._forbid_json = forbid_json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        if self._forbid_json:
            raise AssertionError("json() must not be called on this response")
        return self._json


EMAIL = "person@example.com"
NO_CONTENT = _FakeResponse(status_code=204, text="", forbid_json=True)


def _page(subscribers, has_next=False, cursor=None, total=None):
    pagination = {"has_next_page": has_next, "end_cursor": cursor}
    if total is not None:
        pagination["total_count"] = total
    return {"subscribers": subscribers, "pagination": pagination}


def _no_unsubscribe_writes(monkeypatch):
    def fail_post(url, *args, **kwargs):
        raise AssertionError(f"unexpected POST to {url}")

    monkeypatch.setattr(requests, "post", fail_post)


def _env(monkeypatch):
    monkeypatch.setenv("KIT_API_KEY", "test-key")


def _list_response(subscribers_row, has_next=False):
    data = _page(
        [
            {
                "id": subscribers_row.get("id", 404),
                "email_address": subscribers_row.get("email_address", EMAIL),
                "state": subscribers_row.get("state", "active"),
                "created_at": "2026-04-01T06:08:25Z",
            }
        ],
        has_next=False,
    )
    response = _FakeResponse(json_data=data)
    return response


def test_show_masks_emails_and_whitelists_fields(monkeypatch, capsys) -> None:
    _env(monkeypatch)

    def fake_get(url, headers=None, params=None, timeout=None):
        assert url.endswith("/subscribers")
        assert params["email_address"] == EMAIL
        assert params["status"] == "all"
        return _list_response({"state": "cancelled"})

    monkeypatch.setattr(requests, "get", fake_get)

    code = main(["subscribers", "show", EMAIL, "--format", "json"])

    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "id": 404,
        "state": "cancelled",
        "created_at": "2026-04-01T06:08:25Z",
        "email_address": "pe***@example.com",
    }


def test_show_not_found_exits_one(monkeypatch, capsys) -> None:
    _env(monkeypatch)

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(json_data=_page([], total=0))

    monkeypatch.setattr(requests, "get", fake_get)

    code = main(["subscribers", "show", EMAIL, "--format", "json"])

    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "not_found"


def test_unsubscribe_dry_run_does_not_write(monkeypatch, capsys) -> None:
    _env(monkeypatch)

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/subscribers"):
            return _list_response({"state": "active"})
        if url.endswith("/subscribers/404"):
            return _FakeResponse(json_data={"subscriber": {"id": 404, "email_address": EMAIL, "state": "active"}})
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    _no_unsubscribe_writes(monkeypatch)

    code = main(["subscribers", "unsubscribe", EMAIL, "--format", "json"])

    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "dry_run"
    assert out["email_address"] == "pe***@example.com"
    assert out["note"].startswith("Unsubscribe is consent-revoking")


def test_unsubscribe_dry_run_cancelled_is_no_op(monkeypatch, capsys) -> None:
    _env(monkeypatch)

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/subscribers"):
            return _list_response({"state": "cancelled"})
        if url.endswith("/subscribers/404"):
            return _FakeResponse(json_data={"subscriber": {"id": 404, "email_address": EMAIL, "state": "cancelled"}})
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    _no_unsubscribe_writes(monkeypatch)

    code = main(["subscribers", "unsubscribe", EMAIL, "--format", "json"])

    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "already_cancelled"


def test_unsubscribe_recheck_by_id_blocks_stale_active_list(monkeypatch, capsys) -> None:
    _env(monkeypatch)

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/subscribers"):
            return _list_response({"state": "active"})
        if url.endswith("/subscribers/404"):
            return _FakeResponse(json_data={"subscriber": {"id": 404, "email_address": EMAIL, "state": "cancelled"}})
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    _no_unsubscribe_writes(monkeypatch)

    code = main(["subscribers", "unsubscribe", EMAIL, "--format", "json"])

    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "already_cancelled"


def test_unsubscribe_identity_mismatch_aborts_before_write(monkeypatch, capsys) -> None:
    _env(monkeypatch)

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/subscribers"):
            return _list_response({"state": "active"})
        if url.endswith("/subscribers/404"):
            return _FakeResponse(
                json_data={"subscriber": {"id": 404, "email_address": "other@example.com", "state": "active"}}
            )
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    _no_unsubscribe_writes(monkeypatch)

    code = main(["subscribers", "unsubscribe", EMAIL, "--format", "json"])

    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "error"


def test_unsubscribe_non_active_state_is_skipped(monkeypatch, capsys) -> None:
    _env(monkeypatch)

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/subscribers"):
            return _list_response({"state": "complained"})
        if url.endswith("/subscribers/404"):
            return _FakeResponse(json_data={"subscriber": {"id": 404, "email_address": EMAIL, "state": "complained"}})
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    _no_unsubscribe_writes(monkeypatch)

    code = main(["subscribers", "unsubscribe", EMAIL, "--format", "json"])

    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "skipped_non_active"


def test_unsubscribe_rejects_comma_separated_input(monkeypatch, capsys) -> None:
    _env(monkeypatch)
    _no_unsubscribe_writes(monkeypatch)

    code = main(["subscribers", "unsubscribe", "a@example.com,b@example.com", "--format", "json"])

    assert code == 2
    assert "single bare email address" in capsys.readouterr().err


def test_unsubscribe_execute_confirmed(monkeypatch, capsys, tmp_path) -> None:
    _env(monkeypatch)
    monkeypatch.setattr(cli, "subscription_log_dir", lambda: tmp_path)
    id_reads = {"count": 0}

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/subscribers"):
            return _list_response({"state": "active"})
        if url.endswith("/subscribers/404"):
            id_reads["count"] += 1
            state = "active" if id_reads["count"] == 1 else "cancelled"
            return _FakeResponse(json_data={"subscriber": {"id": 404, "email_address": EMAIL, "state": state}})
        raise AssertionError(f"unexpected GET {url}")

    def fake_post(url, headers=None, json=None, params=None, timeout=None):
        assert url.endswith("/subscribers/404/unsubscribe")
        return NO_CONTENT

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    code = main(["subscribers", "unsubscribe", EMAIL, "--execute", "--format", "json"])

    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "confirmed_cancelled"
    assert out["state_before"] == "active"
    assert out["state_after"] == "cancelled"
    log_path = tmp_path / out["attempt_log"].split("/")[-1]
    assert log_path.is_file()
    assert stat.S_IMODE(log_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    assert EMAIL not in log_path.name
    assert "404" not in log_path.name
    record = json.loads(log_path.read_text(encoding="utf-8"))
    assert record["outcome"] == "confirmed_cancelled"
    assert record["phase"] == "pre_write"
    assert record["subscriber_id"] == 404


def test_unsubscribe_execute_204_but_readback_fails(monkeypatch, capsys, tmp_path) -> None:
    _env(monkeypatch)
    monkeypatch.setattr(cli, "subscription_log_dir", lambda: tmp_path)
    id_reads = {"count": 0}

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/subscribers"):
            return _list_response({"state": "active"})
        if url.endswith("/subscribers/404"):
            id_reads["count"] += 1
            if id_reads["count"] == 2:
                raise requests.HTTPError("HTTP 500", response=_FakeResponse(status_code=500, json_data={"errors": ["boom"]}, text='{"errors": ["boom"]}'))
            return _FakeResponse(json_data={"subscriber": {"id": 404, "email_address": EMAIL, "state": "active"}})
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", lambda url, *args, **kwargs: NO_CONTENT)

    code = main(["subscribers", "unsubscribe", EMAIL, "--execute", "--format", "json"])

    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "write_succeeded_verification_failed"
    record = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert record["outcome"] == "write_succeeded_verification_failed"


def test_unsubscribe_execute_transport_error_is_unknown(monkeypatch, capsys, tmp_path) -> None:
    _env(monkeypatch)
    monkeypatch.setattr(cli, "subscription_log_dir", lambda: tmp_path)

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/subscribers"):
            return _list_response({"state": "active"})
        if url.endswith("/subscribers/404"):
            return _FakeResponse(json_data={"subscriber": {"id": 404, "email_address": EMAIL, "state": "active"}})
        raise AssertionError(f"unexpected GET {url}")

    def fake_post(url, headers=None, json=None, params=None, timeout=None):
        raise requests.ConnectionError("connection reset")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    code = main(["subscribers", "unsubscribe", EMAIL, "--execute", "--format", "json"])

    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "write_outcome_unknown"


def test_unsubscribe_execute_non_204_is_unknown(monkeypatch, capsys, tmp_path) -> None:
    _env(monkeypatch)
    monkeypatch.setattr(cli, "subscription_log_dir", lambda: tmp_path)

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/subscribers"):
            return _list_response({"state": "active"})
        if url.endswith("/subscribers/404"):
            return _FakeResponse(json_data={"subscriber": {"id": 404, "email_address": EMAIL, "state": "active"}})
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(
        requests,
        "post",
        lambda url, headers=None, json=None, params=None, timeout=None: _FakeResponse(status_code=200, text=""),
    )

    code = main(["subscribers", "unsubscribe", EMAIL, "--execute", "--format", "json"])

    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "write_outcome_unknown"
    assert out["http_status"] == 200


def test_hygiene_resolves_tag_paginates_and_filters(monkeypatch, capsys) -> None:
    _env(monkeypatch)
    captured = {"gets": [], "posts": []}

    def fake_get(url, headers=None, params=None, timeout=None):
        assert url.endswith("/tags")
        return _FakeResponse(json_data={"tags": [{"id": 77, "name": "example:newsletter"}]})

    def fake_post(url, headers=None, json=None, params=None, timeout=None):
        captured["posts"].append({"url": url, "json": json, "params": params})
        if params.get("after") is None:
            return _FakeResponse(
                json_data=_page(
                    [
                        {
                            "id": 1,
                            "email_address": EMAIL,
                            "created_at": "2026-04-01T00:00:00Z",
                            "stats": {"sent": 10, "opened": 2, "clicked": 1, "bounced": 5, "last_sent": None},
                        },
                        {
                            "id": 2,
                            "email_address": "quiet@example.com",
                            "created_at": "2026-04-02T00:00:00Z",
                            "stats": {"sent": 10, "opened": 0, "clicked": 0, "bounced": 1, "last_sent": None},
                        },
                    ],
                    has_next=True,
                    cursor="c2",
                    total=99,
                )
            )
        return _FakeResponse(
            json_data=_page(
                [
                    {
                        "id": 3,
                        "email_address": "zero_sent@example.com",
                        "created_at": "2026-04-03T00:00:00Z",
                        "stats": {"sent": 0, "opened": 0, "clicked": 0, "bounced": 4, "last_sent": None},
                    }
                ],
                has_next=False,
                total=None,
            )
        )

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    code = main(
        [
            "analytics",
            "bounce-hygiene",
            "--tag",
            "example:newsletter",
            "--since",
            "2026-04-01",
            "--until",
            "2026-10-26",
            "--format",
            "json",
        ]
    )

    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["scanned"] == 99
    assert out["requested_states"] == ["active"]
    assert out["window"] == {"start": "2026-04-01", "end": "2026-10-26"}
    assert [row["id"] for row in out["candidates"]] == [1, 3]
    assert out["candidates"][0]["email_address"] == "pe***@example.com"
    assert out["candidates"][0]["bounce_ratio"] == 0.5
    assert out["candidates"][1]["bounce_ratio"] is None
    assert "manual investigation" in out["note"]
    assert len(captured["posts"]) == 2
    first, second = captured["posts"]
    assert first["json"] == second["json"]
    assert first["params"] == {"per_page": 500}
    assert second["params"] == {"per_page": 500, "after": "c2"}
    assert "unsubscribe" not in second["url"]


def test_hygiene_missing_stats_aborts_scan(monkeypatch, capsys) -> None:
    _env(monkeypatch)

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(json_data={"tags": [{"id": 77, "name": "example:newsletter"}]})

    def fake_post(url, headers=None, json=None, params=None, timeout=None):
        return _FakeResponse(
            json_data=_page([{"id": 1, "email_address": EMAIL, "created_at": "2026-04-01T00:00:00Z"}])
        )

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    code = main(
        [
            "analytics",
            "bounce-hygiene",
            "--tag",
            "example:newsletter",
            "--since",
            "2026-04-01",
            "--format",
            "json",
        ]
    )

    assert code == 1
    assert "stats missing" in capsys.readouterr().err


def test_hygiene_unknown_tag_exits_two(monkeypatch, capsys) -> None:
    _env(monkeypatch)

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(json_data={"tags": [{"id": 5, "name": "example:main"}]})

    monkeypatch.setattr(requests, "get", fake_get)

    code = main(
        [
            "analytics",
            "bounce-hygiene",
            "--tag",
            "example:newsletter",
            "--since",
            "2026-04-01",
            "--format",
            "json",
        ]
    )

    assert code == 2


def test_hygiene_rejects_reversed_window(monkeypatch, capsys) -> None:
    _env(monkeypatch)
    _no_unsubscribe_writes(monkeypatch)

    code = main(
        [
            "analytics",
            "bounce-hygiene",
            "--tag",
            "example:newsletter",
            "--since",
            "2026-10-26",
            "--until",
            "2026-04-01",
            "--format",
            "json",
        ]
    )

    assert code == 2
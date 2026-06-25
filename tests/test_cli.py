from __future__ import annotations

import json
from pathlib import Path

from kit_skill.cli import main, resolve_tag_names


def test_cli_dry_run_outputs_json_with_tag(tmp_path: Path, capsys) -> None:
    md = tmp_path / "newsletter.md"
    md.write_text("# Subject\n\nBody text", encoding="utf-8")

    code = main(["broadcast", "send", str(md), "--tag-id", "123", "--dry-run", "--format", "json"])

    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True
    assert out["payload"]["subscriber_filter"] == [
        {"all": [{"type": "tag", "ids": [123]}], "any": None, "none": None}
    ]


def test_cli_draft_dry_run_outputs_unscheduled_payload(tmp_path: Path, capsys) -> None:
    md = tmp_path / "newsletter.md"
    md.write_text("# Subject\n\nBody text", encoding="utf-8")

    code = main(["broadcast", "send", str(md), "--draft", "--dry-run", "--format", "json"])

    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["payload"]["public"] is False
    assert out["payload"]["send_at"] is None


class _FakeClient:
    def list_tags(self):
        return {"tags": [{"id": 123, "name": "example:newsletter"}, {"id": 456, "name": "example:main"}]}


def test_resolve_tag_names_exact_match() -> None:
    assert resolve_tag_names(_FakeClient(), ["example:newsletter"]) == [123]

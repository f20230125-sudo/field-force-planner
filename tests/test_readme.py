"""README.md is generated from the template and headline.json; it must not be edited by hand or left stale."""

from __future__ import annotations

import json

from ff import readme


def test_readme_is_up_to_date():
    assert readme.main(["--check"]) == 0, "run: python -m ff.readme"


def test_every_placeholder_resolves_and_none_is_left_over():
    data = json.loads(readme.HEADLINE.read_text(encoding="utf-8"))
    text = readme.render(readme.TEMPLATE.read_text(encoding="utf-8"), data)
    assert "{{" not in text and "}}" not in text


def test_formats():
    assert readme.fmt(1234567.6, "int") == "1,234,568"
    assert readme.fmt(0.0754, "pct1") == "7.5%"
    assert readme.fmt(2.74, "pct0") == "274%"
    assert readme.fmt("2026-10-14", "date") == "14 Oct 2026"

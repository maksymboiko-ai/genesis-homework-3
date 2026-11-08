import csv
import io

import pytest

from hookgen.checks import run_checks, unverified_claims
from hookgen.export import COLUMNS, to_csv
from hookgen.llm import _extract_json
from hookgen.mock import mock_generation
from hookgen.prompt import build_messages
from hookgen.schema import Generation, Variant


@pytest.mark.parametrize("text,flagged", [
    ("Five pairs for $29", []),
    ("I've lost 47 single socks", []),
    ("Only $19 today", ["$19"]),
    ("93% of people agree", ["93%"]),
    ("Join 10,000 happy customers", ["10,000 happy customers"]),
    ("Free shipping on every box", ["free shipping"]),
    ("Money-back guarantee", ["money-back", "guarantee"]),
])
def test_unverified_claims(text, flagged):
    assert sorted(unverified_claims(text)) == sorted(flagged)


def _v(hook, t="pain", screen="Short text", bridge="Then this happened.", visual="A sock."):
    return Variant(hook_type=t, hook_vo=hook, on_screen_text=screen, bridge_line=bridge,
                   visual_note=visual, rationale="r")


def test_mock_batch_passes_checks():
    gen = mock_generation(10)
    res = run_checks(gen, 10, "Some original first line\nbody")
    assert res["passed"], res
    assert res["clean_variants"] == 10


def test_checks_flag_limits_duplicates_and_count():
    gen = Generation(winning_angle="a", variants=[
        _v("one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen"),
        _v("Where do my socks go every single laundry day?", t="question", screen="x" * 50),
        _v("Where do my socks go every single laundry day??", t="made_up"),
    ])
    res = run_checks(gen, 4, "")
    issues = res["variant_issues"]
    assert any("hook is 16 words" in i for i in issues[0])
    assert any("on-screen text is 50 chars" in i for i in issues[1])
    assert any("unknown hook type" in i for i in issues[2])
    assert any("too similar to variant 2" in i for i in issues[2])
    assert res["batch"]["count_ok"] is False
    assert res["batch"]["no_duplicates"] is False
    assert res["passed"] is False


def test_checks_flag_copy_of_original_hook():
    gen = Generation(winning_angle="a", variants=[_v("My dryer has been running a sock smuggling operation.")])
    res = run_checks(gen, 1, "My dryer has been running a sock smuggling operation for years.\nbody")
    assert any("near-copy" in i for i in res["variant_issues"][0])


def test_extract_json_handles_fences_and_prose():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('Sure! {"a": {"b": 2}} hope this helps') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        _extract_json("no json here")


def test_prompt_filters_unknown_hook_types_and_includes_notes():
    msgs = build_messages("line one", 5, hook_types=["humor", "bogus"], notes="be funny")
    assert "- humor:" in msgs[0]["content"] and "- pain:" not in msgs[0]["content"]
    assert "exactly 5 variants" in msgs[1]["content"] and "be funny" in msgs[1]["content"]


def test_csv_export_columns_and_escaping():
    rows = [{"hook_type": "humor", "hook_vo": 'He said "click", then left', "on_screen_text": "a, b",
             "bridge_line": "x", "visual_note": "y", "rationale": "z", "issues": ["too long", "93%"]}]
    out = to_csv(rows, source_script="line1\nline2", winning_angle="angle", model="m")
    parsed = list(csv.DictReader(io.StringIO(out)))
    assert list(parsed[0].keys()) == COLUMNS
    assert parsed[0]["variant_id"] == "V01"
    assert parsed[0]["hook_vo"] == 'He said "click", then left'
    assert parsed[0]["check_issues"] == "too long; 93%"
    assert parsed[0]["source_script"] == "line1\nline2"

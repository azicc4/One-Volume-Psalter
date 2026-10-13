"""Golden tests for the PDF parser on known pages of LH-Per_annum.pdf (see docs/source-pdf-format.md).

Requires build/l1/PA.sqlite (python -m lh extract PA). Skipped if the source PDF has not been extracted.
"""
import pytest

from lh.extract.spans import l1_path
from lh.extract.lines import load_lines
from lh.model.canon import canon, cmp_key, restore, unit_verses
from lh.parse.hour import parse_hour, segment
from lh.psalter.refs import fmt, parse_ref

pytestmark = pytest.mark.skipif(not l1_path("PA").exists(), reason="run `python -m lh extract PA` first")


def hours(p0, p1):
    hs, _ = segment(load_lines("PA", p0, p1), "PA")
    for h in hs:
        parse_hour(h)
    return hs


def slots(h):
    return [e.slot for e in h.elements if e.type not in ("marker", "label", "rubric")]


@pytest.fixture(scope="module")
def week1_monday():
    return {h.code: h for h in hours(119, 143)}


def test_week1_monday_has_all_hours(week1_monday):
    assert set(week1_monday) == {"INV", "OR", "LAUDS", "MIDDAY", "VESPERS", "COMPLINE"}


def test_lauds_slots(week1_monday):
    s = slots(week1_monday["LAUDS"])
    for slot in ("OPENING", "HYMN", "ANT1", "PS1", "ANT1_R", "PS2", "PS3", "LB", "RB", "GOSPEL_ANT", "GOSPEL_CANT",
                 "PRECES", "PATER", "ORATIO", "CONCLUSION"):
        assert slot in s, slot


def test_psalm5_heading_and_omitted_verse(week1_monday):
    ps1 = next(e for e in week1_monday["LAUDS"].elements if e.slot == "PS1")
    assert ps1.data["psalm"] == {"vulg": "5", "hebr": "5", "range": "2-10. 12-13"}
    verses, _ = unit_verses(ps1.data["lines"])
    assert "11" not in verses and verses[0] == "2" and verses[-1] == "13"


def test_sectioned_psalm_9(week1_monday):
    ps = [e for e in week1_monday["OR"].elements if e.type == "psalm"]
    assert [p.data.get("section") for p in ps] == [None, "I", "II"]
    assert ps[2].data["psalm"]["hebr"] == "9"          # section II inherits the heading of section I


def test_gloria_printed_once_after_ps6(week1_monday):
    ps6 = next(e for e in week1_monday["OR"].elements if e.slot == "PS1")
    assert ps6.data.get("gloria_printed") is True


def test_hora_media_subhours(week1_monday):
    els = week1_monday["MIDDAY"].elements
    assert {e.sub for e in els if e.slot == "HYMN"} == {"TERCE", "SEXT", "NONE"}
    assert {e.sub for e in els if e.slot == "PS1"} == {""}            # psalmody shared by the three hours
    assert sum(1 for e in els if e.type == "oratio") == 3


def test_preces_petitions(week1_monday):
    pr = next(e for e in week1_monday["LAUDS"].elements if e.type == "preces")
    assert pr.data["response"].startswith("<i>Spíritum tuum")
    assert len(pr.data["petitions"]) == 4


def test_sunday_year_abc_antiphons():
    lauds = next(h for h in hours(276, 292) if h.code == "LAUDS")
    years = [e.cond.get("year") for e in lauds.elements if e.slot == "GOSPEL_ANT"]
    assert years == ["A", "B", "C"]


def test_dan3_no_gloria_and_ps110_omits_v6():
    hs = hours(821, 836)                    # Sunday of OT week 5 = psalter week I
    lauds = next(h for h in hs if h.code == "LAUDS")
    dan = next(e for e in lauds.elements if e.type == "psalm" and e.data.get("ref", "").startswith("Dan 3, 57-88"))
    assert dan.data.get("no_gloria")
    v2 = next(h for h in hs if h.code == "V2")
    ps110 = next(e for e in v2.elements if e.slot == "PS1")
    verses, _ = unit_verses(ps110.data["lines"])
    assert "6" not in verses and "7" in verses


def test_roundtrip_week1_monday(week1_monday):
    for h in week1_monday.values():
        for e in h.elements:
            c = canon(e)
            if c is None:
                continue
            otype, payload, _, extra = c
            assert cmp_key(restore(otype, payload, extra)) == cmp_key(e.source_text), (e.slot, e.page)


@pytest.mark.parametrize("ref,expected", [
    ("Ps 5:2-10, 12-13", "Ps 5:2-10, 12-13"),
    ("Ap 4, 11; 5, 9. 10. 12", "Rev 4:11, 5:9-10, 12"),
    ("Is 61, 10 — 62, 5", "Isa 61:10-end, 62:1-5"),
    ("Cf. Ap 19, 1-2, 5-7", "Rev 19:1-2, 5-7"),
    ("Tobit 13:1-8", "Tob 13:1-8"),
])
def test_reference_parser(ref, expected):
    b, r, _ = parse_ref(ref)
    assert fmt(b, r) == expected


def test_year_condition_does_not_leak_past_gospel_antiphons():
    """'Anno A/B/C' governs only the Gospel antiphon (and its repeat), never the preces or prayer after it (T-COM-5)."""
    lauds = next(h for h in hours(276, 292) if h.code == "LAUDS")
    leaked = [e.slot for e in lauds.elements if e.cond.get("year") and e.type not in ("ant", "marker")]
    assert leaked == []

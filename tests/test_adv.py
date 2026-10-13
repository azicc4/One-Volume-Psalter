"""Golden tests for LH-Adventus_et_Nativitatis.pdf (ADV, workstream WS1): tricky pages, the seven start-date copies,
the two Christmas tracks and the calendar each copy implies.

Requires build/l1/ADV.sqlite (python -m lh extract ADV; or LH_L1_DIR). Skipped if the volume has not been extracted.
"""
import datetime as dt
import re
from types import SimpleNamespace

import pytest

from lh.extract.lines import load_lines
from lh.extract.spans import l1_path, open_l1
from lh.model.canon import canon, cmp_key, plain, restore
from lh.parse.appendix import parse_appendices
from lh.parse.hour import parse_hour, segment
from lh.sources import adv

pytestmark = pytest.mark.skipif(not l1_path("ADV").exists(), reason="run `python -m lh extract ADV` first")


def hours(p0, p1):
    hs, outside = segment(load_lines("ADV", p0, p1), "ADV")
    for h in hs:
        parse_hour(h)
    return hs, outside


def assert_roundtrip(hs):
    for h in hs:
        for e in h.elements:
            c = canon(e)
            if c is None:
                continue
            otype, payload, _, extra = c
            assert cmp_key(restore(otype, payload, extra)) == cmp_key(e.source_text), (e.slot, e.page)


def test_year_gospel_antiphons_without_ant_label():
    """ADV 37-38: Advent I Sunday, II Vespers prints its Year A/B/C Magnificat antiphons without 'Ant.'."""
    hs, _ = hours(7, 42)
    v2 = next(h for h in hs if h.code in ("VESPERS", "V2") and h.page_start >= 34)
    ants = [e for e in v2.elements if e.slot in ("GOSPEL_ANT", "GOSPEL_ANT_R")]
    assert [(e.slot, e.cond.get("year")) for e in ants] == [
        ("GOSPEL_ANT", "A"), ("GOSPEL_ANT", "B"), ("GOSPEL_ANT", "C"),
        ("GOSPEL_ANT_R", "A"), ("GOSPEL_ANT_R", "B"), ("GOSPEL_ANT_R", "C")]
    assert ants[0].data["text"].startswith("Spíritus Sanctus in te descéndet") and ants[0].data["bare"]
    assert_roundtrip([v2])


def test_pre_title_date_lines_belong_to_the_next_day():
    """ADV 713 'Die 25 decembris' and 1137 'Dominica post diem 6 ianuarii occurrente' are printed above the day title."""
    hs, outside = hours(695, 750)
    dec24 = [h for h in hs if h.day.startswith("DIE 24 DECEMBRIS")]
    assert dec24 and not any("Die 25 decembris" in L.text for h in dec24 for L in h.lines)
    pre = [o for o in outside if o.line.text == "Die 25 decembris"]
    assert pre and pre[0].role == "day_extra" and pre[0].day == "IN NATIVITATE DOMINI"
    hs, outside = hours(1118, 1140)
    assert not any("Dominica post diem 6" in L.text for h in hs if h.day.startswith("DIE 7") for L in h.lines)
    assert any(o.line.text.startswith("Dominica post diem 6") and o.day == "IN BAPTISMATE DOMINI" for o in outside)


def test_wrapped_psalm_heading_and_one_line_canticle_heading():
    """ADV 1685 'Psalmus 68 (69),' / '2-22. 30-37' (heading wrapped after the comma);
    ADV 286 'Canticum Eph 1, 3-10' (reference on the heading line)."""
    hs, _ = hours(1684, 1690)
    ps = [e for e in next(h for h in hs if h.code == "OR").elements if e.type == "psalm"]
    assert [p.data.get("section") for p in ps] == [None, "II", "III"] or [p.data.get("section") for p in ps] == ["I", "II", "III"]
    assert ps[0].data["psalm"] == {"vulg": "68", "hebr": "69", "range": "2-22. 30-37"}
    assert all(p.data["psalm"]["hebr"] == "69" for p in ps)
    hs, _ = hours(284, 288)
    v1 = next(h for h in hs if h.code == "V1")
    ps3 = next(e for e in v1.elements if e.slot == "PS3")
    assert ps3.data["canticle"] and ps3.data["ref"] == "Eph 1, 3-10"
    assert_roundtrip(hs)


def test_antiphon_continues_over_a_page_break():
    """ADV 1747-1748: 'Ant. Missus est Gábriel … desponsátam' / (next page) 'Ioseph, de domo David …' — a capital
    after an unfinished antiphon; ADV 1704-1705: a two-line page-top continuation of 'O Sapiéntia'."""
    hs, _ = hours(1742, 1748)
    lauds = next(h for h in hs if h.code == "LAUDS")
    b = next(e for e in lauds.elements if e.slot == "GOSPEL_ANT" and e.cond.get("year") == "B")
    assert b.data["text"].endswith("Ioseph, de domo David, et nomen vírginis María, allelúia.")
    hs, _ = hours(1701, 1706)
    ants = [e for e in next(h for h in hs if h.code == "VESPERS").elements if e.slot.startswith("GOSPEL_ANT")]
    assert [e.slot for e in ants] == ["GOSPEL_ANT", "GOSPEL_ANT_R"]
    assert ants[0].data["text"].endswith("viam prudéntiæ.")
    assert not any(e.type == "text" for e in next(h for h in hs if h.code == "VESPERS").elements)


def test_appendix_octave_compline_and_vigil_canticles():
    """ALIA EX ORDINARIO (8388-8414): the link 'Antiphonæ finales …' (8411) does not start a chapter; APPENDIX
    (8415-8420): three numbered vigil canticles and the Gospel with its shorter form."""
    lines = load_lines("ADV", 8388, 8420)
    apx = parse_appendices(lines, "ADV")
    compl = [h for h in apx if h.day_key == "ORD.COMPLETORIUM"]
    assert len(compl) == 1 and compl[0].page_start == 8409 and compl[0].page_end == 8414
    assert not any(h.day_key.startswith("ORD.MARIAN.") for h in apx)
    vigil = next(h for h in apx if h.day_key.startswith("PROP.CANTICA"))
    cants = [e for e in vigil.elements if e.type == "psalm"]
    assert [e.data["ref"] for e in cants] == ["Is 26, 1-4. 7-9. 12", "Is 40, 1-8", "Is 66, 10-14"]
    gospels = [e for e in vigil.elements if e.slot == "GOSPEL"]
    assert len(gospels) == 2 and gospels[1].cond.get("alt", "").startswith("Vel forma breviore")
    assert plain(gospels[0].data["intro"][0]) == "Lectio sancti Evangélii secundum Mathæum 1, 1-25"
    assert not any(e.type == "ordinary_ref" for e in vigil.elements)
    assert_roundtrip(apx)


def test_copy_boundaries_and_index_pages():
    """Each copy starts with its two-page index ('Adventus incipit …'); COPIES and NON_CONTENT agree with it."""
    l1 = open_l1("ADV")
    starts = [r[0] for r in l1.execute("SELECT page FROM line WHERE text LIKE 'Adventus incipit%' ORDER BY page")]
    assert starts == [c[0] for c in adv.COPIES]
    assert [(a, b) for a, b, _ in adv.NON_CONTENT[1:]] == [(s, s + 1) for s in starts]
    assert all(c1 + 1 == n0 for (_, c1, _), (n0, _, _) in zip(adv.COPIES, adv.COPIES[1:]))
    assert adv.COPIES[-1][1] == 8387        # ALIA EX ORDINARIO starts on 8388


def test_tracks_match_each_copy_index():
    """Days linked under only one 'TEMPUS NATIVITATIS POST OCTAVAM (quando Epiphania celebratur …)' heading of a copy
    index lie in a TRACKS range of that track; days linked under both do not.
    Known index error (TODO §3 T-ADV-10): the 27 Nov index links the Baptism of the Epiphany-Sunday track to the
    Sunday printing (p. 1137) instead of the Monday printing (pp. 1172-1198)."""
    known = {("27 Nov", 1137)}
    l1 = open_l1("ADV")
    for (a, b, _), (_, _, lab) in zip(adv.NON_CONTENT[1:], adv.COPIES):
        entries = {adv.E6: set(), adv.ESUN: set()}
        cur = None
        for p in range(a, b + 1):
            links = l1.execute("SELECT y0, y1, target FROM link WHERE page=?", (p,)).fetchall()
            for y0, y1, text in l1.execute("SELECT y0, y1, text FROM line WHERE page=? ORDER BY id", (p,)):
                if "Epiphania celebratur die 6" in text:
                    cur = adv.E6
                elif "Epiphania celebratur die dominica" in text:
                    cur = adv.ESUN
                elif text.startswith("ALIA EX"):
                    cur = None
                elif cur:
                    ts = [t for ly0, ly1, t in links if ly0 < y1 - 1 and ly1 > y0 + 1]
                    if ts:
                        entries[cur].add(min(ts))
        for t, other in ((adv.E6, adv.ESUN), (adv.ESUN, adv.E6)):
            for pg in entries[t] - entries[other]:
                assert adv.track(pg) == t, (lab, pg)
            for pg in entries[t] & entries[other]:
                assert adv.track(pg) is None or (lab, pg) in known, (lab, pg)


def test_calendar_of_the_copies():
    """Immaculate Conception moved to 9 Dec in the 1 Dec copy; Holy Family on 30 Dec when Christmas is a Sunday;
    after Epiphany on Sunday 2 Jan the next weekdays take the texts of 7, 8 … January."""
    cal = {c: adv.calendar(c) for _, _, c in adv.COPIES}
    imm = {c: [d for d, k, _, _ in rows if k == "SOL.IMMACULATE_CONCEPTION"] for c, rows in cal.items()}
    assert imm["1 Dec"] == [dt.date(2024, 12, 9)] and imm["27 Nov"] == [dt.date(2022, 12, 8)]
    hf = [d for d, k, _, _ in cal["27 Nov"] if k == "FEAST.HOLY_FAMILY"]
    assert hf == [dt.date(2022, 12, 30)]
    esun = [(d.day, k) for d, k, _, t in cal["28 Nov"] if t == adv.ESUN]
    assert (3, "CHR.POSTEPI.JAN07") in esun and (8, "CHR.POSTEPI.JAN12") in esun
    assert (2, "CHR.2.SUN") in [(d.day, k) for d, k, _, t in cal["28 Nov"] if t == adv.E6]
    assert not any(t for _, _, _, t in cal["2 Dec"])          # 6 January is a Sunday: one track


def test_refine_hour_keys_weekdays_after_epiphany_by_position():
    """28 Nov copy p. 2233 'DIE 3 IANUARII' after Epiphany on Sunday 2 January = first weekday after Epiphany."""
    info = adv.day_info("TEMPUS NATIVITATIS POST OCTAVAM", "DIE 3 IANUARII")
    assert info["key"] == "CHR.JAN03"
    key, copy = adv.refine_hour(SimpleNamespace(page_start=2233), info, "28 Nov")
    assert key["key"] == "CHR.POSTEPI.JAN07" and copy == "28 Nov, Epiphany Sunday"
    key, copy = adv.refine_hour(SimpleNamespace(page_start=2129), info, "28 Nov")       # before Epiphany, 6-Jan track
    assert key["key"] == "CHR.JAN03" and copy == "28 Nov, Epiphany 6 Jan"
    assert re.match(r"^CHR\.2\.SUN$", adv.day_info("", "DOMINICA II POST NATIVITATEM")["key"])

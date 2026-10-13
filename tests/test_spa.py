"""Golden tests for LH-Sanctis-Per_annum.pdf (SPA, workstream WS4a) on tricky pages.

Requires build/l1/SPA.sqlite (python -m lh extract SPA) and the Liturgical Calendar API data
(python -m lh fetch → sources/web/litcal/). Skipped otherwise.
"""
import pytest

from lh.extract.spans import l1_path
from lh.model.days import hour_code
from lh.parse.run import parse_pdf
from lh.sources import copy_label, plugin
from lh.sources import sanctis as sc

pytestmark = pytest.mark.skipif(not l1_path("SPA").exists() or not sc.have_calendar(),
                                reason="run `python -m lh extract SPA` and `python -m lh fetch` first")
spa = plugin("SPA")


def office(p0, p1):
    """Parsed hours of a page range, by hour code."""
    hours, _ = parse_pdf("SPA", p0, p1)
    return {hour_code(h.code, h.subtitle): h for h in hours}


def slots(h, sub=None):
    return [e.slot for e in h.elements if e.type not in ("marker", "label", "rubric") and (sub is None or e.sub == sub)]


def info(h):
    return spa.day_info(h.section, h.day, h.day_extra)


def test_solemnity_nativity_of_john_the_baptist():
    """SPA 620-652: solemnity with I Vespers, two Complines, and Daytime Prayer printed per hour (layout C)."""
    o = office(620, 652)
    assert set(o) == {"V1", "COMPLINE1", "INV", "OR", "LAUDS", "MIDDAY", "V2", "COMPLINE"}
    d = info(o["LAUDS"])
    assert (d["key"], d["rank"], d["precedence"]) == ("SANCT.06-24.NativityJohnBaptist", "solemnity", 3)
    assert sc.preamble(o["V1"])["printed_rank"] == "Sollemnitas"
    for sub in ("TERCE", "SEXT", "NONE"):              # each sub-hour has its own reading, versicle and oration
        s = slots(o["MIDDAY"], sub)
        assert {"LB", "V", "ORATIO"} <= set(s), (sub, s)
    assert "TE_DEUM" in slots(o["OR"])


def test_feast_conversion_of_paul_no_first_vespers():
    """SPA 91-112: a feast — no I Vespers (GILH 231), proper Daytime Prayer, Te Deum."""
    o = office(91, 112)
    assert set(o) == {"INV", "OR", "LAUDS", "MIDDAY", "VESPERS"}
    d = info(o["OR"])
    assert (d["key"], d["rank"], d["precedence"]) == ("SANCT.01-25.ConversionStPaul", "feast", 7)
    assert sc.preamble(o["OR"])["printed_rank"] == "Festum"
    assert "TE_DEUM" in slots(o["OR"]) and "PS1" in slots(o["LAUDS"])


def test_memorial_agnes_psalmody_de_feria():
    """SPA 59-72: obligatory memorial — psalms and first reading 'de feria currente', no Daytime Prayer."""
    o = office(59, 72)
    assert set(o) == {"INV", "OR", "LAUDS", "VESPERS"}
    d = info(o["OR"])
    assert (d["key"], d["rank"]) == ("SANCT.01-21.StAgnes", "memorial")
    pre = sc.preamble(o["OR"])
    assert pre["printed_rank"] == "Memoria" and pre["bio"]
    s = slots(o["OR"])
    assert "LECT2" in s and "RESP2" in s and "PS1" not in s and "LECT1" not in s
    assert any(e.type == "rubric" and "de feria currente" in e.source_text for e in o["OR"].elements)


def test_optional_memorial_hilary_has_no_rank_line():
    """SPA 24-32: optional memorial — no rank line; the biography is the day's preamble."""
    o = office(24, 32)
    d = info(o["LAUDS"])
    assert (d["key"], d["rank"], d["precedence"]) == ("SANCT.01-13.StHilaryPoitiers", "optional_memorial", 12)
    pre = sc.preamble(o["LAUDS"])
    assert pre["printed_rank"] is None and pre["printed_rank_code"] == "optional_memorial"
    assert pre["bio"].startswith("Pictavii natus est")


def test_altera_office_keyed_to_its_saint():
    """SPA 2003: the ALTERA office of St Fabian 'ut pastor' — same day key, copy label from the volume index."""
    o = office(2002, 2011)
    assert info(o["LAUDS"])["key"] == "SANCT.01-20.StFabianPope"
    assert copy_label("SPA", o["LAUDS"].page_start) == "altera Pastor"
    assert o["LAUDS"].section == "ALTERA"
    labels = {lab for _, _, lab in spa.COPIES}
    assert {"altera Pastor", "altera Virgo", "altera Festum", "altera Religiosus", "altera Educatrix"} <= labels
    assert len(spa.COPIES) == 58


def test_assumption_title_set_non_bold():
    """SPA 1111: the Assumption's title is 14.4 regular, not 16.6 bold — still the day title."""
    o = office(1111, 1145)
    v1 = o["V1"]
    assert v1.day == "Die 15 augusti / IN ASSUMPTIONE BEATÆ MARIÆ VIRGINIS"
    assert info(v1)["key"] == "SANCT.08-15.Assumption"
    assert sc.preamble(v1)["printed_rank"] == "Sollemnitas"
    # its Compline ends with the Marian antiphon link continued on a black line (SPA 1145)
    assert "MARIAN" in slots(o["COMPLINE"])


def test_two_line_title_without_die_and_infra_rubric():
    """SPA 1379: date line '16 septembris' (no 'Die'), a two-line title, and the ALTERA link rubric."""
    o = office(1379, 1388)
    h = o["OR"]
    assert h.day == "16 septembris / SS. CORNELII, PAPÆ, ET CYPRIANI, EPISCOPI, / MARTYRUM"
    assert info(h)["key"] == "SANCT.09-16.StsCorneliusCyprian"
    assert sc.preamble(h)["rubrics"].startswith("Infra memoria ut martyres, vel altera")


def test_eodem_die_and_movable_immaculate_heart():
    assert spa.day_info("", "Eodem die 20 ianuarii / S. SEBASTIANI, MARTYRIS")["key"] == "SANCT.01-20.StSebastian"
    d = spa.day_info("", "Sabbato post dominicam II post Pentecosten / IMMACULATI CORDIS BEATÆ MARIÆ VIRGINIS")
    assert (d["key"], d["rank"]) == ("SANCT.MOVABLE.ImmaculateHeart", "memorial")


def test_alternative_gospel_antiphon_and_preces():
    """'Vel: <antiphon>' (SPA 145) is an alternative antiphon in the same slot; 'Vel aliæ:' starts a second set of
    preces and 'Vel: <response>' an alternative response (SPA 251-255)."""
    v = office(144, 147)["VESPERS"]
    alts = [e for e in v.elements if e.type == "ant" and e.cond.get("alt")]
    assert [e.slot for e in alts] == ["GOSPEL_ANT", "GOSPEL_ANT_R"]
    assert alts[0].data["lead"] == "Vel:" and alts[0].data["text"].startswith("Grátias tibi ago")
    o = office(246, 255)
    assert len([e for e in o["LAUDS"].elements if e.type == "preces"]) == 2
    vp = [e for e in o["VESPERS"].elements if e.type == "preces"]
    assert len(vp) == 2 and vp[0].data["response_alt"].endswith("et exáudi nos.</i>")
    assert not [e for e in o["VESPERS"].elements if e.type == "unparsed"]


def test_missing_labels_recovered():
    """Source omissions reported in TODO.md §3: hymn without HYMNUS (SPA 259), short responsory without its label
    (SPA 414), second reading without LECTIO ALTERA (SPA 1314)."""
    assert "HYMN" in slots(office(259, 261)["LAUDS"])
    assert "RB" in slots(office(413, 416)["VESPERS"])
    assert "LECT2" in slots(office(1313, 1315)["OR"])


def test_index_lists_every_office():
    idx = sc.read_index("SPA")
    assert len(idx) == 228 and len([e for e in idx if e["label"]]) == 58
    by = {(e["mmdd"], e["n"], e["label"]): e["hours"] for e in idx}
    assert by[("08-14", 1, None)] == {"INV", "OR", "LAUDS"}                  # Vespers = I Vespers of 15 Aug
    assert by[("09-14", 1, None)] == {"V1", "COMPLINE1", "INV", "OR", "LAUDS", "MIDDAY", "V2", "COMPLINE"}
    assert by[("MOVABLE", 1, None)] == {"INV", "OR", "LAUDS"}                # Immaculate Heart (no day number)
    assert by[("01-20", 1, "Pastor")] == {"INV", "OR", "LAUDS", "VESPERS"}   # Fabian, ALTERA


def test_same_key_in_every_sanctis_volume():
    """One celebration, one key: SQ's commemoration of St Agatha and SPA's memorial (both LitCal StAgatha)."""
    assert spa.day_info("", "Die 5 februarii / S. AGATHÆ, VIRGINIS ET MARTYRIS", ["Memoria"])["key"] == \
        plugin("SQ").day_info("", "Die 5 februarii / S. AGATHÆ, VIRGINIS ET MARTYRIS", ["Pro commemoratione"])["key"]

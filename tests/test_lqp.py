"""Golden tests for LH-Quadragesimae_et_Paschae.pdf (LQP, workstream WS2) on its tricky pages.

Requires build/l1/LQP.sqlite (python -m lh extract LQP; in a worktree point LH_L1_DIR at the main checkout).
"""
import pytest

from lh.extract.lines import load_lines
from lh.extract.spans import l1_path
from lh.model.canon import canon, cmp_key, plain, restore
from lh.model.days import day_info
from lh.parse.hour import parse_hour, segment
from lh.sources import copy_label, plugin
from lh.verify.checks import REQUIRED, TEMPLATE_EXCEPTIONS, expected_from_index

pytestmark = pytest.mark.skipif(not l1_path("LQP").exists(), reason="run `python -m lh extract LQP` first")


def hours(p0, p1):
    hs, _ = segment(load_lines("LQP", p0, p1), "LQP")
    for h in hs:
        parse_hour(h)
    return hs


def by(hs, day_prefix, code):
    return [h for h in hs if h.day.startswith(day_prefix) and h.code == code]


def els(h, slot):
    return [e for e in h.elements if e.slot == slot]


def roundtrips(h):
    for e in h.elements:
        c = canon(e)
        if c is None:
            continue
        otype, payload, _, extra = c
        assert cmp_key(restore(otype, payload, extra, e.slot)) == cmp_key(e.source_text), e


@pytest.fixture(scope="module")
def triduum():
    return hours(1125, 1190)


@pytest.fixture(scope="module")
def easter_sunday_and_octave():
    return hours(1191, 1245)


# ------------------------------------------------------------------------------------- Easter Vigil (GILH 212)

def test_easter_vigil_replaces_office_of_readings(easter_sunday_and_octave):
    (vig,) = by(easter_sunday_and_octave, "DOMINICA PASCHÆ", "OR")
    assert vig.page_start == 1192
    assert [e.slot for e in vig.elements if e.type == "reading"] == ["LECT1", "LECT2", "LECT3", "LECT4"]
    chants = [e for e in vig.elements if e.type == "psalm"]
    assert [e.slot for e in chants] == ["PS1", "PS2", "PS3"]
    assert chants[0].data["ref"] == "Ex 15, 1-6. 17-18"
    assert chants[1].data["ref"] == "Psalmi 41 (42), 2-3. 5 bcd; 42 (43), 3-4"   # two psalms sung as one chant
    assert chants[2].data["psalm"]["hebr"] == "118"
    assert len(els(vig, "TE_DEUM")) == 2                     # label + text, after the Gospel (4th reading)
    # a prayer after the 1st and 2nd chants (none after the Alleluia psalm, as at the Vigil), then the collect
    assert len([e for e in vig.elements if e.type == "oratio"]) == 2 + 1
    assert not [e for e in vig.elements if e.type == "unparsed"]
    req = TEMPLATE_EXCEPTIONS[("EAS.1.SUN", "OR")]
    assert set(req) <= {e.slot for e in vig.elements}
    assert "HYMN" in REQUIRED["OR"] and "HYMN" not in req
    roundtrips(vig)


# ------------------------------------------------------------------------------------- Triduum: Christus factus est

def test_triduum_christus_factus_est_is_the_rb_slot(triduum):
    rb = {}
    for h in triduum:
        if h.code in ("LAUDS", "VESPERS", "COMPLINE"):
            (e,) = els(h, "RB")
            assert e.type == "ant" and plain(e.data["text"]).startswith("Christus factus est pro nobis obœdiens")
            assert h.elements[h.elements.index(e) - 1].source_text == "Loco responsorii dicitur:"
            rb[(h.day, h.code)] = plain(e.data["text"])
    assert len(rb) == 8          # Thu V, C · Fri L, V, C · Sat L, V, C
    # the antiphon grows through the Triduum (Phil 2, 8-9)
    assert rb[("FERIA V IN CENA DOMINI", "VESPERS")].startswith("Christus factus est pro nobis obœdiens usque ad mortem")
    assert "Propter quod" not in rb[("FERIA VI IN PASSIONE DOMINI", "LAUDS")]
    assert "Propter quod" in rb[("SABBATO SANCTO", "VESPERS")]
    for h in triduum:
        roundtrips(h)


# ------------------------------------------------------------------------------------- Easter Octave: Hæc dies, Regina cæli

def test_octave_haec_dies_and_regina_caeli(easter_sunday_and_octave):
    (lauds,) = by(easter_sunday_and_octave, "FERIA II INFRA OCTAVAM", "LAUDS")
    (rb,) = els(lauds, "RB")
    assert rb.type == "ant" and plain(rb.data["text"]).startswith("Hæc dies quam fecit Dóminus")
    assert not els(lauds, "ANT")          # no longer a free-floating antiphon
    (compl,) = by(easter_sunday_and_octave, "FERIA II INFRA OCTAVAM", "COMPLINE")
    (marian,) = els(compl, "MARIAN")
    assert marian.type == "text" and marian.source_text.startswith("Regína cæli, lætáre, allelúia")
    assert set(REQUIRED["COMPLINE"]) <= {e.slot for e in compl.elements}
    roundtrips(lauds)
    roundtrips(compl)


# ------------------------------------------------------------------------------------- Ascension tracks

def test_ascension_tracks_are_labelled():
    assert copy_label("LQP", 2206) == "Ascension Sun"     # Wed Vespers of week VI: only when Ascension is on Sunday
    assert copy_label("LQP", 2216) == "Ascension Sun"     # Thursday of week VI as a feria
    assert copy_label("LQP", 2267) == "Ascension Sun"
    assert copy_label("LQP", 2286) is None                # the solemnity itself serves both tracks
    assert copy_label("LQP", 2201) is None                # Wed Hora media (shared)
    assert copy_label("LQP", 2321) == "Ascension Thu"     # Friday after the Ascension on Thursday
    assert copy_label("LQP", 2346) == "Ascension Thu"
    assert copy_label("LQP", 2365) is None                # Sunday VII
    assert day_info("LQP", "HEBDOMADA VI PASCHÆ", "FERIA VI HEBDOMADÆ VI PASCHÆ")["key"] == "EAS.6.FRI"
    assert day_info("LQP", "HEBDOMADA VI PASCHÆ", "IN ASCENSIONE DOMINI")["key"] == "SOL.ASCENSION"


def test_volume_index_lists_both_ascension_tracks():
    exp = expected_from_index("LQP")
    lqp = plugin("LQP")
    days = {}
    for k, hrs in exp.items():
        key = lqp.index_day_key(*k.split("|"))
        if key:
            days.setdefault(key, []).append(hrs)
    assert len(days) == 98          # Ash Wed–Sat 4 · Lent 5×7 · Holy Week Sun–Thu 5 · Triduum 3 · Octave 7 · 6×7 · 2
    assert len(days["SOL.ASCENSION"]) == 2 and len(days["EAS.6.FRI"]) == 2
    wed = sorted(sorted(h) for h in days["EAS.6.WED"])  # Thursday track: no Vespers/Compline (I Vespers of Ascension)
    assert wed == [["COMPLINE", "INV", "LAUDS", "MIDDAY", "OR", "VESPERS"], ["INV", "LAUDS", "MIDDAY", "OR"]]
    assert "EAS.6.THU" in days and len(days["EAS.6.THU"]) == 1   # a feria only on the Sunday track


def test_ascension_first_vespers_without_psalmody_label():
    hs = hours(2286, 2293)
    (v1,) = [h for h in hs if h.code == "V1"]
    # LQP 2286 omits the opening verse and the PSALMODIA label: numbered antiphons still get ANT1..3
    assert [e.slot for e in v1.elements if e.type == "ant" and "GOSPEL" not in e.slot] == ["ANT1", "ANT1_R", "ANT2", "ANT2_R", "ANT3", "ANT3_R"]
    assert not els(v1, "OPENING") and not els(v1, "CONCLUSION")
    exc = plugin("LQP").STRUCTURE_EXCEPTIONS[("SOL.ASCENSION", "V1")]
    assert exc["missing"] == ["OPENING", "CONCLUSION"] and "GILH 41" in exc["reason"]


# ------------------------------------------------------------------------------------- Easter Hora media

def test_easter_daytime_prayer_missing_terce_header_is_inferred():
    (mid,) = [h for h in hours(1496, 1501) if h.code == "MIDDAY"]
    assert [e.data["text"] for e in mid.elements if e.type == "ant"][0].startswith("Allelúia")   # single Easter ant
    for slot in ("LB", "V", "ORATIO"):
        subs = [e.sub for e in els(mid, slot) if e.type != "label"]
        assert subs == ["TERCE", "SEXT", "NONE"], (slot, subs)
    assert "Ad Tertiam" not in [e.source_text for e in mid.elements if e.slot == "SUBHOUR"][3:]   # source omits it


def test_easter_week5_sunday_none_versicle_is_a_source_omission():
    (mid,) = [h for h in hours(1941, 1946) if h.code == "MIDDAY"]
    v = [e.sub for e in els(mid, "V")]
    assert v == ["TERCE", "SEXT"]                       # LQP 1946: None prints no versicle
    assert ("EAS.5.SUN", "MIDDAY") in plugin("LQP").STRUCTURE_EXCEPTIONS

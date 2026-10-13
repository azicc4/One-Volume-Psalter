"""Golden tests for WS3 (COM, LH-Communia.pdf): Commons with their sub-variants, the four seasonal copies, the Office of
the Dead and the ALIA EX ORDINARIO appendix.

Parser tests need build/l1/COM.sqlite (python -m lh extract COM); they are skipped when it is missing.
"""
import pytest

from lh.extract.lines import load_lines
from lh.extract.spans import l1_path
from lh.model.canon import canon, cmp_key, plain, restore
from lh.model.days import day_info, hour_code
from lh.parse.hour import parse_hour, segment, subvariant
from lh.parse.run import parse_pdf
from lh.sources import copy_label, non_content

pytestmark = pytest.mark.skipif(not l1_path("COM").exists(), reason="run `python -m lh extract COM` first")


def hours(p0, p1):
    """{(day key, hour code): Hour} for a page range of LH-Communia.pdf."""
    hs, _ = segment(load_lines("COM", p0, p1), "COM")
    out = {}
    for h in hs:
        parse_hour(h)
        out[(day_info("COM", h.section, h.day)["key"], hour_code(h.code, h.subtitle))] = h
    return out


def roundtrips(h):
    for e in h.elements:
        c = canon(e)
        if c is None:
            continue
        otype, payload, _, extra = c
        assert cmp_key(restore(otype, payload, extra, e.slot)) == cmp_key(e.source_text), (e.slot, e.page)


def first_line(e):
    return plain(e.data["stanzas"][0][0]) if e.type == "hymn" else e.source_text


# ------------------------------------------------------------------------------------------------ plug-in


def test_day_keys_copies_and_non_content():
    assert day_info("COM", "PASCHÆ INDEX", "COMMUNE MARTYRUM: / PRO UNO MARTYRE")["key"] == "COMMON.MARTYRS.ONE"
    assert day_info("COM", "OFFICIUM DEFUNCTORUM", "COMMUNE SANCTARUM MULIERUM")["key"] == "DEAD"
    assert day_info("COM", "PER ANNUM INDEX", "MEMORIA SANCTÆ MARIÆ IN SABBATO")["key"] == "MEM.BVM_SATURDAY"
    assert [copy_label("COM", p) for p in (5, 417, 900, 1640, 1650)] == ["ADV", "LENT", "EAS", "OT", None]
    assert non_content("COM", 818) and not non_content("COM", 819)


def test_subvariant_rubrics():
    assert subvariant("Pro papa:") == "Pro papa"
    assert subvariant("Vel alia, præsertim pro episcopo:") == "Præsertim pro episcopo"
    assert subvariant("In ipsa ecclesia dedicata:") == "In ipsa ecclesia dedicata"
    assert subvariant("Tempore Adventus:") == "Tempore Adventus"
    assert subvariant("Pro vigilia protracta, hic adduntur cantica, ut in Appendice") is None     # ADV 727


# ------------------------------------------------------------------------------------------------ sub-variants


@pytest.fixture(scope="module")
def pastors():
    return hours(1416, 1462)                    # COMMUNE PASTORUM, Per annum copy


def test_pastors_hymn_stanza_variants(pastors):
    """COM 1416-1417: 'Pro uno pastore' hymn with one stanza each 'Pro papa / episcopo / presbytero'; the remaining
    common stanzas, printed after the last variant without a marker, go back to 'Pro uno pastore'."""
    v1 = pastors[("COMMON.PASTORS", "V1")]
    hy = [(e.cond.get("for"), first_line(e)) for e in v1.elements if e.type == "hymn"]
    assert hy == [("Pro uno pastore", "Vir celse, forma fúlgida"), ("Pro papa", "Tu Petri ovíle cǽlitus"),
                  ("Pro episcopo", "Virtúte factus dítior"), ("Pro presbytero", "Regális huius cúlminis"),
                  ("Pro uno pastore", "Locátus in cæléstibus,"), ("Pro pluribus pastoribus", "Sacráta nobis gáudia")]
    roundtrips(v1)


def test_pastors_prayers_and_readings(pastors):
    v1 = pastors[("COMMON.PASTORS", "V1")]
    orations = [(e.cond.get("for"), e.cond.get("alt")) for e in v1.elements if e.type == "oratio"]
    assert orations == [("Pro papa", None), ("Pro episcopo", None), ("Pro fundatore Ecclesiæ", None),
                        ("Pro pastore", None), (None, "Vel:"), ("Pro missionario", None)]
    gospel = [(e.slot, e.cond.get("for")) for e in v1.elements if e.slot.startswith("GOSPEL_ANT")]
    assert gospel == [("GOSPEL_ANT", "Pro papa vel episcopo"), ("GOSPEL_ANT", "Pro presbytero"),
                      ("GOSPEL_ANT_R", "Pro papa vel episcopo"), ("GOSPEL_ANT_R", "Pro presbytero")]
    oor = pastors[("COMMON.PASTORS", "OR")]
    reading_conds = [(e.slot, e.cond.get("for")) for e in oor.elements if e.type in ("reading", "responsory")]
    assert reading_conds[:4] == [("LECT1", "Pro papa vel episcopo"), ("RESP1", "Pro papa vel episcopo"),
                                 ("LECT1", "Pro presbytero"), ("RESP1", "Pro presbytero")]
    assert ("LECT2", "Præsertim pro episcopo") in reading_conds        # "Vel alia, præsertim pro episcopo:" (1434)
    roundtrips(oor)


def test_hora_media_per_hour_and_one_oration(pastors):
    """Layout C: Terce, Sext and None each have hymn, antiphon + complementary psalmody, short reading, versicle; the
    oration (with its sub-variants) is printed once, after None."""
    md = pastors[("COMMON.PASTORS", "MIDDAY")]
    assert [e.sub for e in md.elements if e.slot == "LB"] == ["TERCE", "SEXT", "NONE"]
    assert [e.sub for e in md.elements if e.slot == "V"] == ["TERCE", "SEXT", "NONE"]
    assert {e.sub for e in md.elements if e.type == "oratio"} == {"NONE"}


def test_virgins_inline_variant_antiphons():
    """COM 1500: 'Ant. pro virgine et martyre: …' then 'Pro virgine: …' and 'Pro pluribus: …' printed without 'Ant.',
    each repeated after the Magnificat."""
    v1 = hours(1497, 1502)[("COMMON.VIRGINS", "V1")]
    g = [(e.slot, e.cond.get("for")) for e in v1.elements if e.slot.startswith("GOSPEL_ANT")]
    assert g == [("GOSPEL_ANT", "Pro virgine et martyre"), ("GOSPEL_ANT", "Pro virgine"), ("GOSPEL_ANT", "Pro pluribus"),
                 ("GOSPEL_ANT_R", "Pro virgine et martyre"), ("GOSPEL_ANT_R", "Pro virgine"),
                 ("GOSPEL_ANT_R", "Pro pluribus")]
    roundtrips(v1)


def test_holy_men_vel_inside_a_subvariant():
    """COM 1540: 'Pro religioso: Nisi quis…' then 'vel: Hic accípiet…' = another antiphon for the same sub-variant."""
    v1 = hours(1535, 1542)[("COMMON.HOLY_MEN", "V1")]
    g = [e.cond for e in v1.elements if e.slot == "GOSPEL_ANT"]
    assert {"alt": "vel:", "for": "Pro religioso"} in g
    roundtrips(v1)


def test_martyr_short_responsory_variants():
    """COM 1379: 'Pro uno martyre:' / 'Pro una martyre:' — two short responsories, both RB."""
    v1 = hours(1375, 1381)[("COMMON.MARTYRS.ONE", "V1")]
    assert [(e.type, e.cond.get("for")) for e in v1.elements if e.slot == "RB"] == [
        ("resp_breve", "Pro uno martyre"), ("resp_breve", "Pro una martyre")]


# ------------------------------------------------------------------------------------------------ Dedication, BVM


def test_dedication_prayers_in_and_outside_the_church():
    lauds = hours(1209, 1237)[("COMMON.DEDICATION", "LAUDS")]
    assert [(e.cond.get("for"), e.cond.get("alt")) for e in lauds.elements if e.type == "oratio"] == [
        ("In ipsa ecclesia dedicata", None), ("Extra ipsam ecclesiam dedicatam", None), (None, "Vel:")]
    oor = hours(1209, 1226)[("COMMON.DEDICATION", "OR")]
    assert any(e.type == "te_deum" for e in oor.elements)        # "In sollemnitatibus et festis Hymnus Te Deum"
    roundtrips(lauds)


def test_bvm_preces_alternative_response_and_second_set():
    """COM 1251-1252 (II Vespers): 'Vel: Plenam grátia intuére…' after the response stays in the preces; 'Vel aliæ:'
    starts a second set of preces."""
    v2 = hours(1247, 1284)[("COMMON.BVM", "V2")]
    pr = [e for e in v2.elements if e.type == "preces"]
    assert len(pr) == 2 and pr[1].cond.get("alt") == "Vel aliæ:"
    assert pr[0].data["response_alt"].startswith("<r>Vel:</r>")
    assert len(pr[1].data["petitions"]) == 5
    roundtrips(v2)


def test_bvm_advent_copy_seasonal_prayers():
    v1 = hours(43, 48)[("COMMON.BVM", "V1")]
    assert [e.cond.get("for") for e in v1.elements if e.type == "oratio"] == ["Tempore Adventus", "Tempore Nativitatis"]


# ------------------------------------------------------------------------------------------------ seasonal copies


def test_easter_copy_adds_alleluia():
    """The same Common in the Advent (COM 5) and Easter (COM 819) copies: the Easter antiphons end in 'allelúia' and
    the opening verse keeps 'Allelúia' (Lent drops it, COM 418)."""
    adv = hours(5, 10)[("COMMON.DEDICATION", "V1")]
    eas = hours(819, 824)[("COMMON.DEDICATION", "V1")]
    lent = hours(418, 423)[("COMMON.DEDICATION", "V1")]

    def ant2(h):
        return next(e.data["text"] for e in h.elements if e.slot == "ANT2")

    assert ant2(adv) == "Confortávit Dóminus seras portárum tuárum, benedíxit fíliis tuis in te."
    assert ant2(eas) == "Confortávit Dóminus seras portárum tuárum, benedíxit fíliis tuis in te, allelúia."
    opening = {k: next(e for e in h.elements if e.slot == "OPENING").source_text for k, h in
               (("adv", adv), ("lent", lent))}
    assert opening["adv"].endswith("Allelúia.") and not opening["lent"].endswith("Allelúia.")
    rb = next(e for e in eas.elements if e.slot == "RB")
    assert "Allelúia, allelúia" in rb.source_text


# ------------------------------------------------------------------------------------------------ Office of the Dead


@pytest.fixture(scope="module")
def dead():
    return hours(1641, 1675)


def test_office_of_the_dead(dead):
    assert {h for d, h in dead if d == "DEAD"} == {"INV", "OR", "LAUDS", "MIDDAY", "VESPERS", "COMPLINE"}
    oor = dead[("DEAD", "OR")]
    hy = [(e.cond.get("for"), first_line(e)) for e in oor.elements if e.type == "hymn"]
    # one stanza per sub-variant, then the closing stanza common to all (COM 1643)
    assert hy == [(None, "Qui vivis ante sǽcula"), ("Pro uno defuncto", "Hoc vitæ regno pérfrui"),
                  ("Pro una defuncta", "Hoc vitæ regno pérfrui"), ("Pro pluribus", "Hoc vitæ regno pérfrui"),
                  (None, "Hoc regnum nobis própera")]
    lauds = dead[("DEAD", "LAUDS")]
    assert ("Pro fratribus, propinquis et benefactoribus" in
            [e.cond.get("for") for e in lauds.elements if e.type == "oratio"])
    for h in dead.values():
        roundtrips(h)


# ------------------------------------------------------------------------------------------------ appendix


def test_appendix_psalm_heading_with_alternative():
    """COM 1684: 'Psalmus 121 (122), vel 128 (129)' (red + blue link) heads Ps 122; it no longer runs into Ps 121."""
    hs, _ = parse_pdf("COM", 1676, 1699)
    ps = [e for h in hs for e in h.elements if e.type == "psalm" and e.page == 1684]
    assert [(e.data["psalm"]["hebr"], e.data.get("alt_psalm")) for e in ps] == [("122", "128 (129)"), ("129", None)]

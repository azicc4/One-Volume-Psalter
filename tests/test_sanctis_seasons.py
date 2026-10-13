"""Golden tests for WS4b: the seasonal Proper of Saints volumes SP (Easter), SQ (Lent) and SADV (Advent/Christmas).

Parser tests need build/l1/<KEY>.sqlite (python -m lh extract SP SQ SADV); database tests need build/lh.sqlite built
with those sources (python -m lh build PA LQP ADV:4-1198 SP SQ SADV). Each is skipped when its input is missing.
"""
import sqlite3

import pytest

from lh.config import DB_PATH
from lh.extract.spans import l1_path
from lh.model.canon import canon, cmp_key, restore
from lh.model.days import day_info, hour_code
from lh.parse.run import parse_pdf
from lh.sources import copy_label, plugin
from lh.sources.sanctis_seasons import nice_title, rank_of, split_day, title_slug

needs = {k: pytest.mark.skipif(not l1_path(k).exists(), reason=f"run `python -m lh extract {k}` first")
         for k in ("SP", "SQ", "SADV")}


def _db_has(*keys):
    if not DB_PATH.exists():
        return False
    con = sqlite3.connect(DB_PATH)
    try:
        have = {r[0] for r in con.execute("SELECT key FROM source")}
    finally:
        con.close()
    return set(keys) <= have


needs_db = pytest.mark.skipif(not _db_has("SP", "SQ", "SADV"),
                              reason="run `python -m lh build PA LQP ADV:4-1198 SP SQ SADV` first")


def roundtrips(e) -> bool:
    otype, payload, _, extra = canon(e)
    return cmp_key(restore(otype, payload, extra, e.slot)) == cmp_key(e.source_text)


def hours_of(key, p0, p1):
    hours, _ = parse_pdf(key, p0, p1)
    return hours


def slots(h):
    return [e.slot for e in h.elements if e.type not in ("marker", "label", "rubric")]


# ------------------------------------------------------------------------------------------------ header helpers

def test_header_helpers():
    assert split_day("Die 24 aprilis / S. FIDELIS DE SIGMARINGEN, PRESBYTERI ET / MARTYRIS") == (
        4, 24, "S. FIDELIS DE SIGMARINGEN, PRESBYTERI ET MARTYRIS", False)
    assert split_day("Eodem die 8 februarii / S. IOSEPHINÆ BAKHITA, VIRGINIS")[3] is True
    assert title_slug("S. AGATHÆ, VIRGINIS ET MARTYRIS") == "agathae"
    assert title_slug("CATHEDRÆ S. PETRI APOSTOLI") == "cathedrae-petri-apostoli"
    assert title_slug("SS. CYRILLI, MONACHI, ET METHODII, EPISCOPI") == "cyrilli-et-methodii"
    assert title_slug("IN ANNUNTIATIONE DOMINI") == "annuntiatione-domini"
    assert nice_title("S. GREGORII VII, PAPÆ") == "S. Gregorii VII, Papæ"
    assert rank_of(["Pro commemoratione", "Vel ubi celebratur ut festum.", "Memoria"]) == ("commemoration", 12)
    assert rank_of(["Natus est …"]) == ("optional_memorial", 12)


# ------------------------------------------------------------------------------------------------ SQ commemoration

@needs["SQ"]
def test_sq_commemoration_agatha():
    """SQ 8-9: 'Pro commemoratione' — OR second reading + responsory + prayer; Lauds and Vespers only an antiphon."""
    hours = hours_of("SQ", 7, 9)
    assert [h.code for h in hours] == ["OR", "LAUDS", "VESPERS"]
    h = hours[0]
    assert h.day == "Die 5 februarii / S. AGATHÆ, VIRGINIS ET MARTYRIS"     # date line joined with the title
    info = day_info("SQ", h.section, h.day, h.day_extra)
    assert info["key"] == "SANCT.02-05.agathae"
    assert (info["rank"], info["copy"]) == ("commemoration", "commemoratio")
    assert slots(h) == ["LECT2", "RESP2", "ORATIO"]
    assert slots(hours[1]) == ["ANT"] and slots(hours[2]) == ["ANT"]
    req = plugin("SQ").required_slots(info["key"], "OR", "commemoratio", [])
    assert set(req) <= set(slots(h))
    assert all(roundtrips(e) for x in hours for e in x.elements if e.type not in ("marker", "label", "rubric"))


@needs["SADV"]
def test_sadv_commemoration_single_lectio():
    """SA 143: late-Advent commemoration labels its reading 'LECTIO' (no PRIOR/ALTERA): it is the LECT2 slot."""
    hours = hours_of("SADV", 143, 144)
    assert day_info("SADV", hours[0].section, hours[0].day, hours[0].day_extra)["copy"] == "commemoratio"
    assert slots(hours[0]) == ["LECT2", "RESP2", "ORATIO"]
    assert slots(hours[1]) == ["ANT", "ORATIO"]                  # SADV repeats the prayer at Lauds and Vespers


# ------------------------------------------------------------------------------------------------ SP Easter memorial

@needs["SP"]
def test_sp_easter_memorial_alleluias_and_feria():
    """SP 129-137 (St Anselm): Easter-time alleluias; psalmody «de feria currente» by rubric; optional memorial."""
    hours = hours_of("SP", 129, 137)
    assert [h.code for h in hours] == ["INV", "OR", "LAUDS", "VESPERS"]
    info = day_info("SP", hours[0].section, hours[0].day, hours[0].day_extra)
    assert (info["key"], info["rank"]) == ("SANCT.04-21.anselmi", "optional_memorial")
    inv = next(e for e in hours[0].elements if e.slot == "INV_ANT")
    assert inv.data["text"].endswith("allelúia.")
    rb = next(e for e in hours[2].elements if e.slot == "RB")
    assert "Allelúia, allelúia" in rb.source_text
    rub = [e.data["text"] for e in hours[1].elements if e.type == "rubric"]
    assert any("de feria currente" in t for t in rub)
    assert {"LECT2", "RESP2", "ORATIO"} <= set(slots(hours[1])) and "PS1" not in slots(hours[1])


@needs["SP"]
def test_sp_inline_alternative_antiphon():
    """SP 100: red 'Vel:' + black text after the Magnificat antiphon is an alternative antiphon (cond alt), also when
    repeated after the canticle; restore() rebuilds the 'Vel:' lead."""
    vesp = next(h for h in hours_of("SP", 94, 101) if h.code == "VESPERS")
    alts = [e for e in vesp.elements if e.type == "ant" and e.data.get("lead")]
    assert [e.slot for e in alts] == ["GOSPEL_ANT", "GOSPEL_ANT_R"]
    assert alts[0].cond == {"alt": "Vel:"}
    assert alts[0].data["text"].startswith("Grátias tibi ago, Christe") and alts[0].data["text"].endswith("allelúia.")
    assert all(roundtrips(e) for e in alts)
    assert not [e for e in vesp.elements if e.slot == "TEXT"]


# ------------------------------------------------------------------------------------------------ St Joseph, Annunciation

@needs["SP"]
def test_st_joseph_midday_per_hour_layout():
    """SP 31-34: Hora media printed per hour (hymn, antiphon + complementary psalmody links, LB, versicle, prayer
    under each of Terce/Sext/None) keeps each part under its own sub-hour."""
    hours = hours_of("SP", 11, 41)
    assert {day_info("SP", h.section, h.day, h.day_extra)["key"] for h in hours} == {"SANCT.03-19.ioseph"}
    codes = [hour_code(h.code, h.subtitle) for h in hours]
    assert codes == ["V1", "COMPLINE1", "INV", "OR", "LAUDS", "MIDDAY", "V2", "COMPLINE"]
    mid = hours[codes.index("MIDDAY")]
    for slot in ("LB", "V", "ORATIO"):
        assert sorted(e.sub for e in mid.elements if e.slot == slot and e.type != "label") == ["NONE", "SEXT", "TERCE"], slot


@needs_db
def test_joseph_and_annunciation_one_day_two_seasonal_printings():
    """19 and 25 March are printed in SQ (Lent) and SP (Easter): one day key each; the short responsories differ
    only by the Easter alleluias and are distinct objects."""
    con = sqlite3.connect(DB_PATH)
    try:
        for key in ("SANCT.03-19.ioseph", "SANCT.03-25.annuntiatione-domini"):
            src = {r[0] for r in con.execute("SELECT DISTINCT source FROM hour_instance WHERE day_key=?", (key,))}
            assert src == {"SP", "SQ"}
            assert con.execute("SELECT rank FROM day WHERE key=?", (key,)).fetchone()[0] == "solemnity"
            rb = dict(con.execute("""SELECT h.source, ob.plain FROM occurrence o JOIN hour_instance h ON h.id=o.hour_id
                                     JOIN object ob ON ob.id=o.object_id WHERE h.day_key=? AND h.hour='V1'
                                     AND o.slot='RB'""", (key,)))
            assert "Allelúia" in rb["SP"] and "Allelúia" not in rb["SQ"]
        # SQ's commemoration of St Francis of Paola and SP's memorial resolve to the same day
        rows = set(con.execute("SELECT source, copy FROM hour_instance WHERE day_key='SANCT.04-02.francisci-de-paola'"))
        assert rows == {("SP", None), ("SQ", "commemoratio")}
    finally:
        con.close()


# ------------------------------------------------------------------------------------------------ SADV traps

@needs["SADV"]
def test_sadv_26_dec_vespers_only():
    """SA 149: St Stephen gives only Vespers (rubric: the other hours are in the Proper of Time) — keyed to the
    temporale day CHR.DEC26, printing labelled 'sollemnitas'."""
    hours = hours_of("SADV", 149, 153)
    assert [h.code for h in hours] == ["VESPERS"]
    h = hours[0]
    assert any(t.startswith("Invitatorium, Officium lectionis, Laudes matutinæ et Hora media") for t in h.day_extra)
    assert day_info("SADV", h.section, h.day, h.day_extra)["key"] == "CHR.DEC26"
    assert copy_label("SADV", h.page_start) == "sollemnitas"
    assert {"HYMN", "PS1", "PS2", "PS3", "GOSPEL_ANT", "PRECES", "ORATIO"} <= set(slots(h))


@needs_db
def test_sadv_db_vespers_only_and_immaculate_conception():
    con = sqlite3.connect(DB_PATH)
    try:
        for dd in (26, 27, 28):
            rows = set(con.execute("SELECT hour, copy FROM hour_instance WHERE source='SADV' AND day_key=?",
                                   (f"CHR.DEC{dd}",)))
            assert rows == {("VESPERS", "sollemnitas")}
        hours = {r[0] for r in con.execute(
            "SELECT hour FROM hour_instance WHERE source='SADV' AND day_key='SOL.IMMACULATE_CONCEPTION'")}
        assert hours == {"V1", "COMPLINE1", "INV", "OR", "LAUDS", "MIDDAY", "V2", "COMPLINE"}
    finally:
        con.close()


@needs_db
def test_sanctis_index_checks_pass():
    from lh.verify.checks import _con, check_index
    con = _con()
    try:
        for key in ("SP", "SQ", "SADV"):
            assert check_index(con, key)["n_mismatch"] == 0, key
    finally:
        con.rollback()
        con.close()

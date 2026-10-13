"""Golden tests for WS5 (PA residue): interrupted preces (T-UNP), the Saturday memorial of the BVM (PA 6269-6290) and
the hymns ad libitum (PA 6264-6268) with the links that name them.

Parser tests need build/l1/<KEY>.sqlite (python -m lh extract PA LQP); database tests need build/lh.sqlite
(python -m lh build PA LQP ADV:4-1198). Each is skipped when its input is missing.
"""
import json
import sqlite3

import pytest

from lh.config import DB_PATH
from lh.extract.lines import load_lines
from lh.extract.spans import l1_path
from lh.model.canon import canon, cmp_key, restore
from lh.parse.hour import parse_hour, segment
from lh.parse.run import parse_pdf

needs_pa = pytest.mark.skipif(not l1_path("PA").exists(), reason="run `python -m lh extract PA` first")
needs_lqp = pytest.mark.skipif(not l1_path("LQP").exists(), reason="run `python -m lh extract LQP` first")
needs_db = pytest.mark.skipif(not DB_PATH.exists(), reason="run `python -m lh build PA LQP ADV:4-1198` first")


def content(h):
    return [e for e in h.elements if e.type not in ("marker", "label", "rubric")]


def roundtrips(e) -> bool:
    otype, payload, _, extra = canon(e)
    return cmp_key(restore(otype, payload, extra, e.slot)) == cmp_key(e.source_text)


@pytest.fixture(scope="module")
def prop():
    """ALIA EX PROPRIO DE TEMPORE (PA 6263-6290): {(chapter title, hour code, copy): Hour}."""
    hours, _ = parse_pdf("PA", 6263, 6290)
    return {(h.day_title, h.code, getattr(h, "copy", None)): h for h in hours}


BVM = "MEMORIA SANCTÆ MARIÆ IN SABBATO"


@needs_pa
def test_bvm_preces_alternative_set_is_parsed(prop):
    """PA 6277-6278: a second set of preces after a separator and "Vel aliæ:" (was 5 unparsed "— …" lines)."""
    lauds = prop[(BVM, "LAUDS", None)]
    assert not [e for e in lauds.elements if e.type == "unparsed"]
    preces = [e for e in lauds.elements if e.slot == "PRECES" and e.type == "preces"]
    assert len(preces) == 2
    first, alt = preces
    assert not first.cond and len(first.data["petitions"]) == 4
    assert alt.cond == {"alt": "Vel aliæ:"}
    assert alt.data["response"] == "<i>Intercédat pro nobis mater tua, Dómine.</i>"
    pets = alt.data["petitions"]
    assert len(pets) == 5
    # wrapped first half (x=100 continuation) stays in the first half
    assert pets[0] == {"a": "Salvátor mundi, qui redemptiónis tuæ virtúte ab omni peccáti labe matrem tuam præservásti,",
                       "b": "serva nos mundos a peccáto."}
    assert pets[-1]["b"] == "tríbue nos eiúsdem glóriæ meréri consórtium."
    assert roundtrips(alt)


@needs_lqp
def test_easter7_friday_vespers_preces_without_label():
    """LQP 2522: the PRECES label is missing in the source; the preces follow the repeated Magnificat antiphon."""
    hs, _ = segment(load_lines("LQP", 2516, 2522), "LQP")
    vespers = next(h for h in hs if h.code == "VESPERS")
    parse_hour(vespers)
    assert not [e for e in vespers.elements if e.type == "unparsed"]
    slots = [e.slot for e in content(vespers)]
    assert slots[-5:] == ["GOSPEL_ANT_R", "PRECES", "PATER", "ORATIO", "CONCLUSION"]
    preces = next(e for e in vespers.elements if e.type == "preces")
    assert preces.data["intro"].startswith("Benedicámus Patrem, qui in natiónes grátiam Spíritus effúdit")
    assert preces.data["response"] == "<i>Diffundátur, Dómine, grátia Spíritus Sancti.</i>"
    assert len(preces.data["petitions"]) == 5
    assert preces.data["petitions"][4]["b"] == "ut in advéntu Christi resurrectiónem assequántur."
    assert roundtrips(preces)


@needs_pa
def test_bvm_numbered_gospel_antiphons_and_prayers(prop):
    """PA 6276-6279: "1 …" … "6 …" (red number, black text) are numbered alternatives, not rubrics + loose text."""
    lauds = prop[(BVM, "LAUDS", None)]
    ants = [e for e in lauds.elements if e.slot == "GOSPEL_ANT"]
    reps = [e for e in lauds.elements if e.slot == "GOSPEL_ANT_R"]
    ors = [e for e in lauds.elements if e.slot == "ORATIO" and e.type == "oratio"]
    assert [e.cond["choice"] for e in ants] == [str(i) for i in range(1, 7)]
    assert [e.data["text"] for e in reps] == [e.data["text"] for e in ants]     # repeated after the Benedictus
    assert ants[3].data["text"] == "Ave, María, grátia plena; Dóminus tecum; benedícta tu in muliéribus, allelúia."
    assert [e.cond["choice"] for e in ors] == [str(i) for i in range(1, 7)]
    assert ors[0].data["lines"][0] == [1, "Concéde nos fámulos tuos, quǽsumus, Dómine Deus, perpétua mentis et"]
    assert not [e for e in lauds.elements if e.type == "text"]
    assert all(roundtrips(e) for e in ants + reps + ors)
    # the printed number is occurrence data, not part of the canonical text
    otype, payload, _, extra = canon(ors[1])
    assert extra == {"choice": "2"} and not payload["lines"][0][1].startswith("2")


@needs_pa
def test_bvm_alternative_short_readings_and_second_readings(prop):
    """PA 6275: "Vel (Ap 12, 1):" introduces an alternative short reading; PA 6280-6290: the second readings that
    follow Lauds are their own appendix fragment, each "Vel alia:" a LECT2 alternative."""
    lauds = prop[(BVM, "LAUDS", None)]
    lbs = [e for e in lauds.elements if e.slot == "LB"]
    assert [e.cond.get("alt") for e in lbs] == [None, "Vel (Cf. Is 61, 10):", "Vel (Ap 12, 1):"]
    assert lbs[2].data["ref"] == "Ap 12, 1"
    assert lauds.page_end == 6279                                     # Lauds ends at its conclusion
    frag = prop[(BVM, "APPX", "LECTIO ALTERA")]
    lect = [e for e in frag.elements if e.slot == "LECT2"]
    resp = [e for e in frag.elements if e.slot == "RESP2"]
    assert len(lect) == len(resp) == 9
    assert lect[1].cond == {"alt": "Vel alia:"} and lect[1].data["intro"] == ["Ex Sermónibus beáti Guerríci abbátis"]
    assert lect[8].cond == {"alt": "aut de die 16 iulii:"}
    assert frag.elements[0].type == "label"                           # the fragment keeps its first line
    # the Office of Readings names these readings in LECT2 links
    orr = prop[(BVM, "OR", None)]
    links = [e for e in orr.elements if e.type == "link" and e.slot == "LECT2"]
    assert [e.data["target"] for e in links] == [6280, 6281, 6282, 6283, 6284, 6285, 6287, 6288, 6289]


@needs_pa
def test_ad_libitum_hymn_links_are_hymn_alternatives(prop):
    """OT.02.SUN I Vespers (PA 261): "Ad libitum dici potest hymnus Salve dies." links to the hymn on PA 6267."""
    hs, _ = segment(load_lines("PA", 261, 266), "PA")
    v1 = next(h for h in hs if h.code == "V1")
    parse_hour(v1)
    link = next(e for e in v1.elements if e.type == "link" and "Salve dies" in e.data["text"])
    assert link.slot == "HYMN_ALT" and link.data["target"] == 6267
    hymns = [e for h in prop.values() if h.day_title.startswith("Hymni ad libitum") for e in h.elements
             if e.type == "hymn"]
    assert [e.data["stanzas"][0][0] for e in hymns] == [
        "Dies iræ, dies illa", "Quid sum miser tunc dictúrus,", "Peccatrícem qui solvísti",
        "Salve dies, diérum glória,", "Dies ætásque céteris"]
    assert next(e for e in hymns if e.page == 6267).data["stanzas"][0][0].startswith("Salve dies")


@pytest.fixture(scope="module")
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    yield con
    con.close()


@needs_db
def test_db_ad_libitum_links_resolve_to_hymns(db):
    rows = db.execute("""SELECT o.source_text, lt.object_id, lt.how, h.day_key FROM link_target lt
                         JOIN occurrence o ON o.id = lt.occurrence_id JOIN hour_instance h ON h.id = o.hour_id
                         WHERE h.source = 'PA' AND o.slot = 'HYMN_ALT' AND o.source_text LIKE 'Ad libitum%'""").fetchall()
    got = {(r["source_text"], r["object_id"].split(".")[1], r["how"]) for r in rows}
    assert got == {
        ("Ad libitum dici potest hymnus Dies iræ.", "dies-irae-dies-illa", "text"),
        ("Ad libitum dici potest hymnus Quid sum miser.", "quid-sum-miser-tunc", "text"),
        ("Ad libitum dici potest hymnus Peccatrícem qui.", "peccatricem-qui-solvisti", "text"),
        ("Ad libitum dici potest hymnus Salve dies.", "salve-dies-dierum-gloria", "text"),
        ("Ad libitum dici potest hymnus Dies ætásque.", "dies-aetasque-ceteris", "text"),
    }
    weeks = {r["day_key"] for r in rows if "Salve dies" in r["source_text"]}
    assert "OT.02.SUN" in weeks and len(weeks) == 16


@needs_db
def test_db_bvm_saturday_is_a_day_with_complete_hours(db):
    day = db.execute("SELECT * FROM day WHERE key = 'MEM.BVM_SATURDAY'").fetchone()
    assert day["rank"] == "optional_memorial" and day["weekday"] == "SAT" and day["season"] == "OT"
    assert not db.execute("SELECT 1 FROM day WHERE key LIKE 'PROP.MEMORIA%'").fetchone()
    hours = {r["hour"] for r in db.execute("SELECT hour FROM hour_instance WHERE day_key = 'MEM.BVM_SATURDAY'")}
    assert {"INV", "OR", "LAUDS"} <= hours
    fails = db.execute("""SELECT subject FROM check_result WHERE check_name = 'structure' AND status = 'fail'
                          AND subject LIKE 'MEM.BVM_SATURDAY%'""").fetchall()
    assert not fails, [r[0] for r in fails]
    # OT Saturdays point to the memorial ("Memoria ad libitum Sanctæ Mariæ") at each hour
    memo = db.execute("""SELECT DISTINCT th.hour FROM link_target lt JOIN occurrence o ON o.id = lt.occurrence_id
                         JOIN hour_instance th ON th.id = lt.hour_id WHERE o.slot = 'MEMORIAL'""").fetchall()
    assert {r[0] for r in memo} == {"INV", "OR", "LAUDS"}
    assert not db.execute("""SELECT 1 FROM occurrence o JOIN hour_instance h ON h.id = o.hour_id
                             WHERE h.day_key = 'MEM.BVM_SATURDAY' AND o.type = 'unparsed'""").fetchone()
    assert json.loads(db.execute("""SELECT o.cond FROM occurrence o JOIN hour_instance h ON h.id = o.hour_id
                                    WHERE h.day_key = 'MEM.BVM_SATURDAY' AND h.hour = 'LAUDS' AND o.slot = 'PRECES'
                                    AND o.cond IS NOT NULL""").fetchone()[0]) == {"alt": "Vel aliæ:"}

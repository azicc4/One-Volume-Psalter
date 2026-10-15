"""The page arrangement table (lh/sim/arrangement.py; book/out/<file>-ribbons.json) and the refrain hymn fix."""
import datetime as dt
import json
import sqlite3

import pytest

from lh.config import BOOK, DB_PATH

TABLE = BOOK / "out" / "book-ribbons.json"


@pytest.mark.skipif(not TABLE.exists(), reason="run `python -m lh book` (or `lh ribbons`) first")
def test_table_covers_six_months_hour_by_hour():
    t = json.loads(TABLE.read_text(encoding="utf-8"))
    a, b = dt.date.fromisoformat(t["from"]), dt.date.fromisoformat(t["to"])
    assert 180 <= (b - a).days <= 186 and len(t["days"]) == (b - a).days + 1
    assert len(t["ribbons"]) == 9
    for day in t["days"]:
        names = [h["name"] for h in day["hours"]]
        assert names[:3] == ["Invitatory", "Office of Readings", "Lauds"] and names[-1] == "Compline"
        for h in day["hours"]:
            assert h["start"] and set(h["ribbons"]) <= {str(n) for n in range(1, 10)}


@pytest.mark.skipif(not DB_PATH.exists(), reason="run `python -m lh build` first")
def test_a_refrain_cue_does_not_split_a_hymn():
    """"(O María.)" between the stanzas (SPA 1926–1927) belongs to the hymn: one hymn, no "Amen." hymn."""
    con = sqlite3.connect(DB_PATH)
    hymns = {oid: json.loads(p)["stanzas"] for oid, p in con.execute("SELECT id, payload FROM object WHERE type='hymn'")}
    salve = [s for s in hymns.values() if s[0][0].startswith("Salve, mater misericórdiæ")]
    assert len(salve) == 1 and len(salve[0]) == 3
    assert not [s for s in hymns.values() if s[0][0].strip() in ("Amen.", "Amen")]


@pytest.mark.parametrize("name", ["book", "book-weekly"])
def test_ribbon_5_always_lies_after_ribbon_4(name):
    """Ribbon 4 keeps the four-week cycle, ribbon 5 the Proper of Time after it (the weeks of Ordinary Time, the
    seasons' days): wherever the reader has laid them, 5 is further on in the book than 4."""
    path = BOOK / "out" / f"{name}-ribbons.json"
    if not path.exists():
        pytest.skip("run `python -m lh book` first")
    t = json.loads(path.read_text(encoding="utf-8"))
    lie = {}
    for day in t["days"]:
        for h in day["hours"]:
            lie.update(h["ribbons"])
            if "4" in lie and "5" in lie:
                assert int(lie["5"]) > int(lie["4"]), (day["date"], h["hour"], lie["4"], lie["5"])


@pytest.mark.skipif(not DB_PATH.exists(), reason="run `python -m lh build` first")
def test_hymn_stanzas_follow_the_stanza_gap():
    """A stanza ends at the stanza gap of the source, not at an indented line (the short fourth line of a sapphic
    stanza, PA 19) nor at a page break inside it (María, quæ mortálium)."""
    con = sqlite3.connect(DB_PATH)
    hymns = {oid: json.loads(p)["stanzas"] for oid, p in con.execute("SELECT id, payload FROM object WHERE type='hymn'")}
    te_patrem = next(s for s in hymns.values() if s[0][0].startswith("Te Patrem summum"))
    assert [len(x) for x in te_patrem] == [4, 4, 4, 4]
    maria = [s for s in hymns.values() if s[0][0].startswith("María, quæ mortálium")]
    assert maria and all(len(s[0]) == 4 for s in maria)

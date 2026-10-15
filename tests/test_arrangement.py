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

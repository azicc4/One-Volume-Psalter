"""lh/sim: calendar dates, and one simulated day against the built book (needs `python -m lh book`)."""
import datetime as dt
import sqlite3

import pytest

from lh.config import BOOK, BUILD, DB_PATH
from lh.sim.calendar import Calendar, advent1, easter


def test_easter_and_advent():
    assert [easter(y) for y in (2025, 2026, 2027, 2038)] == [dt.date(2025, 4, 20), dt.date(2026, 4, 5),
                                                              dt.date(2027, 3, 28), dt.date(2038, 4, 25)]
    assert advent1(2026) == dt.date(2026, 11, 29) and advent1(2027) == dt.date(2027, 11, 28)


needs_db = pytest.mark.skipif(not DB_PATH.exists(), reason="run `python -m lh build` first")


@needs_db
@pytest.mark.parametrize("date, office", [
    ("2026-11-29", "ADV.1.SUN"), ("2026-12-20", "ADV.4.SUN"), ("2026-12-21", "ADV.DEC21"),
    ("2026-12-27", "FEAST.HOLY_FAMILY"), ("2027-01-10", "FEAST.BAPTISM"), ("2027-01-11", "OT.01.MON"),
    ("2027-02-10", "LENT.0.WED"), ("2027-03-19", "SANCT.03-19.StJoseph"), ("2027-03-25", "HOLY.THU"),
    ("2027-03-28", "EAS.1.SUN"), ("2027-05-16", "SOL.PENTECOST"), ("2027-05-17", "OT.07.MON"),
    ("2027-08-06", "SANCT.08-06.Transfiguration"), ("2027-11-02", "SANCT.11-02.AllSouls"),
    ("2027-11-21", "SOL.CHRIST_KING"), ("2027-01-28", "SANCT.01-28.StThomasAquinas"),
])
def test_calendar(date, office):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    assert Calendar(con).celebration(dt.date.fromisoformat(date)).office == office


@needs_db
def test_memorial_in_lent_is_a_commemoration():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    c = Calendar(con).celebration(dt.date(2027, 2, 10))          # St Scholastica on Ash Wednesday
    assert c.office == "LENT.0.WED" and any("Scholastica" in n for n in c.notes)


@pytest.mark.skipif(not (BUILD / "latex" / "book.aux").exists() or not (BOOK / "out" / "book.pdf").exists(),
                    reason="run `python -m lh book` first")
def test_a_simulated_day_finds_every_page():
    from lh.sim.run import Sim
    sim = Sim()
    cel, steps = sim.steps(dt.date(2027, 1, 28))                  # a memorial: saint, Common and weekday
    hours = {s.hour for s in steps}
    assert {"INV", "OR", "LAUDS", "MIDDAY", "COMPLINE"} <= hours and hours & {"VESPERS", "V2"}
    assert all(s.page is not None for s in steps) and not sim.off[False].missing
    assert {s.source for s in steps} >= {"SANCT.01-28.StThomasAquinas", "OT.03.THU"}
    row = sim.run_days([dt.date(2027, 1, 28)])[0]
    assert row["search"] > 0 and row["moves"] <= row["steps"]

"""Date → office celebrated, after the General Roman Calendar (UNLY) with a simplified table of precedence.

Simplifications (documented in reports/simulation.md):
- universal dates: Epiphany 6 January, Ascension on Thursday, Corpus Christi on Thursday;
- no transfers: a solemnity impeded by a privileged Sunday or day is simply not celebrated that year;
- optional memorials are kept only when `optional=True` (the first of the day; otherwise the weekday);
- memorials falling in Lent or on 17–24 December are commemorations only, so the weekday is celebrated.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field

WD = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]          # date.weekday() order


def easter(year: int) -> dt.date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


def advent1(year: int) -> dt.date:
    """First Sunday of Advent of the liturgical year that begins in `year` (Sunday 27 Nov – 3 Dec)."""
    d = dt.date(year, 11, 27)
    return d + dt.timedelta(days=(6 - d.weekday()) % 7)


def sunday_on_or_before(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


@dataclass
class Celebration:
    date: dt.date
    temporal: str                         # day key of the Proper of Time (grid day, proper day or solemnity)
    office: str                           # day key whose office is said (temporal or SANCT.… / SOL.…)
    rank: int                             # table of precedence (1 highest)
    kind: str                             # solemnity, feast, memorial, sunday, weekday …
    title: str = ""
    year_cycle: str = "A"                 # Sunday cycle A/B/C
    weekday_cycle: str = "I"              # weekday cycle I/II
    psalter_week: int | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def is_saint(self) -> bool:
        return self.office != self.temporal


class Calendar:
    """Celebrations from the day table of the database (keys and ranks)."""

    def __init__(self, con, optional: bool = False):
        self.con = con
        self.optional = optional
        self.days = {r["key"]: r for r in con.execute("SELECT * FROM day")}
        self.by_date: dict[str, list] = {}
        for k, r in self.days.items():
            m = re.match(r"^SANCT\.(\d\d-\d\d)\.", k)
            if m:
                self.by_date.setdefault(m.group(1), []).append(r)
        self.by_date.setdefault("12-08", []).append(self.days["SOL.IMMACULATE_CONCEPTION"])

    # ------------------------------------------------------------------ Proper of Time
    def temporal(self, d: dt.date) -> tuple[str, int, str]:
        """(day key, precedence rank, kind) of the Proper of Time on date d."""
        wd = WD[d.weekday()]
        y = d.year
        e = easter(y)
        ash = e - dt.timedelta(days=46)
        pent = e + dt.timedelta(days=49)
        adv = advent1(y)
        ck = adv - dt.timedelta(days=7)                       # Christ the King
        xmas = dt.date(y, 12, 25)
        epi = dt.date(y, 1, 6)
        bapt = epi + dt.timedelta(days=7 - (epi.weekday() + 1) % 7 or 7)   # Sunday after 6 January
        off = (d - e).days
        named = {0: ("EAS.1.SUN", 1, "solemnity"), 39: ("SOL.ASCENSION", 1, "solemnity"),
                 49: ("SOL.PENTECOST", 1, "solemnity"), 56: ("SOL.TRINITY", 3, "solemnity"),
                 60: ("SOL.CORPUS_CHRISTI", 3, "solemnity"), 68: ("SOL.SACRED_HEART", 3, "solemnity"),
                 -3: ("HOLY.THU", 2, "holy_week"), -2: ("TRIDUUM.FRI", 1, "triduum"),
                 -1: ("TRIDUUM.SAT", 1, "triduum")}
        if off in named:
            return named[off]
        if d == ck:
            return "SOL.CHRIST_KING", 3, "solemnity"
        # Christmas Time (both ends of the civil year)
        if d >= xmas:
            if d == xmas:
                return "SOL.CHRISTMAS", 1, "solemnity"
            hf = next((xmas + dt.timedelta(days=i) for i in range(1, 7) if (xmas + dt.timedelta(days=i)).weekday() == 6),
                      dt.date(y, 12, 30))
            if d == hf:
                return "FEAST.HOLY_FAMILY", 5, "feast"
            return f"CHR.DEC{d.day}", 9, "privileged_weekday"
        if d <= bapt:
            if d.month == 1 and d.day == 1:
                return "SOL.MARY_MOTHER_OF_GOD", 3, "solemnity"
            if d == epi:
                return "SOL.EPIPHANY", 1, "solemnity"
            if d == bapt:
                return "FEAST.BAPTISM", 5, "feast"
            if d < epi:
                return ("CHR.2.SUN", 6, "sunday") if wd == "SUN" else (f"CHR.JAN{d.day:02d}", 13, "weekday")
            return f"CHR.POSTEPI.JAN{d.day:02d}", 13, "weekday"
        # Advent
        if d >= adv:
            if d.month == 12 and 17 <= d.day <= 24 and wd != "SUN":
                return f"ADV.DEC{d.day}", 9, "privileged_weekday"
            n = (d - adv).days // 7 + 1
            return f"ADV.{n}.{wd}", (2 if wd == "SUN" else 13), ("sunday" if wd == "SUN" else "weekday")
        # Lent and Holy Week
        if ash <= d < e:
            if d < ash + dt.timedelta(days=4):
                return f"LENT.0.{wd}", (2 if wd == "WED" else 9), ("ash_wednesday" if wd == "WED" else "privileged_weekday")
            if d >= e - dt.timedelta(days=7):
                return f"HOLY.{wd}", 2, "holy_week"
            n = (d - (e - dt.timedelta(days=42))).days // 7 + 1
            return f"LENT.{n}.{wd}", (2 if wd == "SUN" else 9), ("sunday" if wd == "SUN" else "privileged_weekday")
        # Easter Time
        if e < d < pent:
            if off < 7:
                return f"EAS.OCT.{wd}", 2, "octave"
            n = off // 7 + 1
            return f"EAS.{n}.{wd}", (2 if wd == "SUN" else 13), ("sunday" if wd == "SUN" else "weekday")
        # Ordinary Time
        if bapt < d < ash:
            n = (d - bapt).days // 7 + 1
        else:                                                  # after Pentecost: counted back from week 34
            n = 34 - (ck - sunday_on_or_before(d)).days // 7
        return f"OT.{n:02d}.{wd}", (6 if wd == "SUN" else 13), ("sunday" if wd == "SUN" else "weekday")

    # ------------------------------------------------------------------ Proper of Saints
    SAINT_RANK = {"solemnity": 3, "all_souls": 3, "feast_lord": 5, "feast": 7, "memorial": 10, "optional_memorial": 12}

    def celebration(self, d: dt.date) -> Celebration:
        tkey, trank, tkind = self.temporal(d)
        if tkey not in self.days:                              # e.g. OT.34.SUN replaced by Christ the King
            tkey = next((k for k in (tkey, re.sub(r"\.(\d)\.", lambda m: f".{int(m.group(1)):02d}.", tkey))
                         if k in self.days), tkey)
        best, brank, bkind = tkey, trank, tkind
        notes = []
        for r in self.by_date.get(f"{d.month:02d}-{d.day:02d}", []):
            rank = self.SAINT_RANK.get(r["rank"])
            if rank is None:
                continue
            if r["rank"] == "optional_memorial" and not self.optional:
                continue
            if rank >= 10 and trank <= 9:                     # memorial in Lent / 17–24 Dec / octaves: commemoration
                notes.append(f"commemoration: {r['key']}")
                continue
            if rank < brank or (rank >= 10 and brank == 13):
                best, brank, bkind = r["key"], rank, r["rank"]
        lit_year = d.year + (1 if d >= advent1(d.year) else 0)
        trow = self.days.get(tkey)
        return Celebration(date=d, temporal=tkey, office=best, rank=brank, kind=bkind,
                           title=(self.days[best]["title"] if best in self.days else best) or best,
                           year_cycle="ABC"[(lit_year - 2023) % 3], weekday_cycle="I" if lit_year % 2 else "II",
                           psalter_week=(trow["psalter_week"] if trow is not None else None), notes=notes)

    def has_first_vespers(self, c: Celebration) -> bool:
        """Sundays and solemnities (and feasts of the Lord on a Sunday) begin with First Vespers the evening before."""
        return c.kind in ("sunday", "solemnity", "triduum") or c.date.weekday() == 6 and c.rank <= 6

    def describe(self, c: Celebration) -> str:
        x = json.loads(self.days[c.office]["extra"] or "{}") if c.office in self.days else {}
        return f"{c.date.isoformat()} {c.date.strftime('%a')}: {c.title} [{c.kind}]" + (" (Proper of Saints)" if c.is_saint else "") \
            + (f" — {x.get('printed_rank')}" if x.get("printed_rank") else "")

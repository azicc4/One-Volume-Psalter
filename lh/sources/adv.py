"""ADV — LH-Adventus_et_Nativitatis.pdf: Advent and Christmas Time.

The volume prints Advent–Baptism once for each possible date of the First Sunday of Advent (27 Nov … 3 Dec);
see COPIES. Workstream WS1 (TODO.md) collapses the copies into one set of objects.
"""
from __future__ import annotations

import re

from lh.model.days import DAY_NAMES, roman, special_day, weekday_of

KEY = "ADV"
TITLE = "Proprium de Tempore — Tempus Adventus et Nativitatis"
NON_CONTENT = [
    (1, 3, "cover, title page, index of start dates"),
    # each start-date copy opens with its own two-page index ("Adventus incipit … / HEBDOMADA I ADVENTUS / Dominica 1v …")
    (4, 5, "copy index"), (1199, 1200, "copy index"), (2463, 2464, "copy index"), (3732, 3733, "copy index"),
    (5003, 5004, "copy index"), (6274, 6275, "copy index"), (7397, 7398, "copy index"),
]
COPIES = [
    (4, 1198, "27 Nov"), (1199, 2462, "28 Nov"), (2463, 3731, "29 Nov"), (3732, 5002, "30 Nov"),
    (5003, 6273, "1 Dec"), (6274, 7396, "2 Dec"), (7397, 8387, "3 Dec"),
]
MONTHS = {"NOVEMBRIS": 11, "DECEMBRIS": 12, "IANUARII": 1}
SPECIAL = {
    "IN CONCEPTIONE IMMACULATA BEATÆ MARIÆ / VIRGINIS": ("SOL.IMMACULATE_CONCEPTION", "Immaculate Conception of the BVM", "solemnity", 3),
    "IN NATIVITATE DOMINI": ("SOL.CHRISTMAS", "Nativity of the Lord", "solemnity", 2),
    "SANCTÆ FAMILIÆ IESU, MARIÆ ET IOSEPH": ("FEAST.HOLY_FAMILY", "Holy Family", "feast", 5),
    "In octava Nativitatis Domini / SANCTÆ DEI GENETRICIS MARIÆ": ("SOL.MARY_MOTHER_OF_GOD", "Mary, Mother of God", "solemnity", 3),
    "IN EPIPHANIA DOMINI": ("SOL.EPIPHANY", "Epiphany of the Lord", "solemnity", 2),
    "IN BAPTISMATE DOMINI": ("FEAST.BAPTISM", "Baptism of the Lord", "feast", 5),
}


def day_info(section: str, day: str) -> dict:
    sp = special_day(SPECIAL, day)
    if sp:
        return sp
    m = re.match(r"^DIE (\d+) (DECEMBRIS|IANUARII)", day)
    if m:
        dd, mon = int(m.group(1)), MONTHS[m.group(2)]
        if mon == 12 and 17 <= dd <= 24:
            wk = re.search(r"HEBDOMADÆ ([IVX]+) ADVENTUS", day)
            w = roman(wk.group(1)) if wk else None
            return {"key": f"ADV.DEC{dd}", "season": "ADV", "week": w, "weekday": weekday_of(day), "psalter_week": w,
                    "title": f"{dd} December (Advent)", "rank": "privileged_weekday", "precedence": 9}
        octave = mon == 12 or (mon == 1 and dd == 1)
        return {"key": f"CHR.{'DEC' if mon == 12 else 'JAN'}{dd:02d}", "season": "CHR", "week": None, "weekday": None,
                "psalter_week": None, "title": f"{dd} {'December' if mon == 12 else 'January'} (Christmas Time)",
                "rank": "octave_day" if octave else "weekday", "precedence": 9 if octave else 13}
    m = re.search(r"HEBDOMADA ([IVX]+) ADVENTUS", section)
    if m:
        wk = roman(m.group(1))
        wd = "SUN" if day == "DOMINICA" else weekday_of(day)
        return {"key": f"ADV.{wk}.{wd}", "season": "ADV", "week": wk, "weekday": wd, "psalter_week": wk,
                "title": f"{DAY_NAMES[wd]} of Week {wk} of Advent", "rank": "sunday" if wd == "SUN" else "weekday",
                "precedence": 2 if wd == "SUN" else 13}
    raise ValueError(f"unmapped Advent/Christmas section {section!r} / day {day!r}")

"""LQP — LH-Quadragesimae_et_Paschae.pdf: Lent, Holy Week, Paschal Triduum, Easter Time (to Pentecost).

Known quirks (workstream WS2): the Ascension is printed on two tracks (Thursday / transferred to Sunday), so some
days appear twice (hour_instance.copy = '#2'); the Easter Vigil replaces the Office of Readings of Easter Sunday.
"""
from __future__ import annotations

import re

from lh.model.days import DAY_NAMES, roman, special_day, weekday_of

KEY = "LQP"
TITLE = "Proprium de Tempore — Tempus Quadragesimæ et Paschæ"
NON_CONTENT = [
    (1, 6, "cover, title page and volume index"),
]
LENT_PSALTER = {0: 4, 1: 1, 2: 2, 3: 3, 4: 4, 5: 1}
EASTER_PSALTER = {2: 2, 3: 3, 4: 4, 5: 1, 6: 2, 7: 3}
SPECIAL = {
    "DOMINICA IN PALMIS DE PASSIONE DOMINI": ("HOLY.SUN", "Palm Sunday of the Passion of the Lord", "sunday", 2),
    "FERIA V IN CENA DOMINI": ("TRIDUUM.THU", "Holy Thursday, Evening Mass of the Lord's Supper", "triduum", 1),
    "FERIA VI IN PASSIONE DOMINI": ("TRIDUUM.FRI", "Good Friday of the Passion of the Lord", "triduum", 1),
    "SABBATO SANCTO": ("TRIDUUM.SAT", "Holy Saturday", "triduum", 1),
    "DOMINICA PASCHÆ IN RESURRECTIONE DOMINI": ("EAS.1.SUN", "Easter Sunday of the Resurrection of the Lord", "solemnity", 1),
    "IN ASCENSIONE DOMINI": ("SOL.ASCENSION", "Ascension of the Lord", "solemnity", 2),
    "DOMINICA PENTECOSTES": ("SOL.PENTECOST", "Pentecost Sunday", "solemnity", 2),
}


def day_info(section: str, day: str) -> dict:
    sp = special_day(SPECIAL, day)
    if sp:
        return sp
    wd = weekday_of(day)
    if "CINERUM" in section:
        return {"key": f"LENT.0.{wd}", "season": "LENT", "week": 0, "weekday": wd, "psalter_week": 4,
                "title": "Ash Wednesday" if wd == "WED" else f"{DAY_NAMES[wd]} after Ash Wednesday",
                "rank": "privileged_weekday", "precedence": 2 if wd == "WED" else 9}
    m = re.search(r"HEBDOMADA ([IVX]+) QUADRAGESIMÆ", section)
    if m:
        wk = roman(m.group(1))
        return {"key": f"LENT.{wk}.{wd}", "season": "LENT", "week": wk, "weekday": wd, "psalter_week": LENT_PSALTER[wk],
                "title": f"{DAY_NAMES[wd]} of Week {wk} of Lent", "rank": "sunday" if wd == "SUN" else "privileged_weekday",
                "precedence": 2 if wd == "SUN" else 9}
    if "HEBDOMADA SANCTA" in section:
        return {"key": f"HOLY.{wd}", "season": "LENT", "week": 6, "weekday": wd, "psalter_week": 2,
                "title": f"{DAY_NAMES[wd]} of Holy Week", "rank": "privileged_weekday", "precedence": 2}
    if "OCTAVA" in section:
        return {"key": f"EAS.OCT.{wd}", "season": "EAS", "week": 1, "weekday": wd, "psalter_week": None,
                "title": f"{DAY_NAMES[wd]} within the Octave of Easter", "rank": "octave_day", "precedence": 2}
    m = re.search(r"HEBDOMADA ([IVX]+) (?:TEMPORIS PASCHALE|PASCHÆ)", section)
    if m:
        wk = roman(m.group(1))
        return {"key": f"EAS.{wk}.{wd}", "season": "EAS", "week": wk, "weekday": wd, "psalter_week": EASTER_PSALTER[wk],
                "title": f"{DAY_NAMES[wd]} of Week {wk} of Easter", "rank": "sunday" if wd == "SUN" else "weekday",
                "precedence": 2 if wd == "SUN" else 13}
    raise ValueError(f"unmapped Lent/Easter section {section!r} / day {day!r}")

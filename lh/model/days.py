"""Map a parsed hour (source, section heading, day title, subtitle) to a liturgical-day key and hour code.

Day keys:  OT.05.SUN   ADV.1.MON   LENT.0.WED   EAS.OCT.TUE   SOL.TRINITY   (more added per source)
Hour codes: INV OR LAUDS MIDDAY VESPERS V1 V2 COMPLINE COMPLINE1 (Compline after I Vespers)
"""
from __future__ import annotations

import re

ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}
WEEKDAYS = {"DOMINICA": "SUN", "FERIA II": "MON", "FERIA III": "TUE", "FERIA IV": "WED",
            "FERIA V": "THU", "FERIA VI": "FRI", "SABBATO": "SAT"}
WEEKDAY_ORDER = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
DAY_NAMES = {"SUN": "Sunday", "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday",
             "FRI": "Friday", "SAT": "Saturday"}
HOUR_NAMES = {"INV": "Invitatory", "OR": "Office of Readings", "LAUDS": "Lauds", "MIDDAY": "Daytime Prayer",
              "TERCE": "Terce", "SEXT": "Sext", "NONE": "None", "VESPERS": "Vespers", "V1": "I Vespers",
              "V2": "II Vespers", "COMPLINE": "Compline", "COMPLINE1": "Compline after I Vespers"}

PA_SOLEMNITIES = {
    "SANCTISSIMÆ TRINITATIS": ("SOL.TRINITY", "Most Holy Trinity"),
    "SS.MI CORPORIS ET SANGUINIS CHRISTI": ("SOL.CORPUS_CHRISTI", "Most Holy Body and Blood of Christ"),
    "SACRATISSIMI CORDIS IESU": ("SOL.SACRED_HEART", "Most Sacred Heart of Jesus"),
    "DOMINI NOSTRI IESU CHRISTI / UNIVERSORUM REGIS": ("SOL.CHRIST_KING", "Our Lord Jesus Christ, King of the Universe"),
}


def roman(s: str) -> int:
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN[ch]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def psalter_week_ot(week: int) -> int:
    return (week - 1) % 4 + 1


def hour_code(code: str, subtitle: str) -> str:
    if code == "COMPLINE" and subtitle.startswith("POST I VESPERAS"):
        return "COMPLINE1"
    return code


def day_key_pa(section: str, day: str) -> dict:
    """Per annum: sections 'HEBDOMADA N' with days FERIA x / DOMINICA / SABBATO; plus solemnities of the Lord."""
    if day in PA_SOLEMNITIES:
        key, name = PA_SOLEMNITIES[day]
        d = {"key": key, "season": "OT", "week": None, "weekday": None, "psalter_week": None,
             "title": name, "rank": "solemnity", "precedence": 3}
        if key == "SOL.CHRIST_KING":
            d.update(week=34, weekday="SUN", precedence=3)
        return d
    m = re.search(r"HEBDOMADA ([IVXL]+)$", section)
    if not m:
        raise ValueError(f"unmapped Per annum section {section!r} / day {day!r}")
    week = roman(m.group(1))
    wd = next((v for k, v in sorted(WEEKDAYS.items(), key=lambda kv: -len(kv[0])) if day.startswith(k)), None)
    if wd is None:
        raise ValueError(f"unmapped Per annum day {day!r}")
    return {"key": f"OT.{week:02d}.{wd}", "season": "OT", "week": week, "weekday": wd,
            "psalter_week": psalter_week_ot(week),
            "title": f"{DAY_NAMES[wd]} of Week {week} in Ordinary Time",
            "rank": "sunday" if wd == "SUN" else "weekday", "precedence": 6 if wd == "SUN" else 13}


MONTHS = {"NOVEMBRIS": 11, "DECEMBRIS": 12, "IANUARII": 1}
LENT_PSALTER = {0: 4, 1: 1, 2: 2, 3: 3, 4: 4, 5: 1}
EASTER_PSALTER = {2: 2, 3: 3, 4: 4, 5: 1, 6: 2, 7: 3}
SEASON_DAYS = {
    # Advent / Christmas
    "IN CONCEPTIONE IMMACULATA BEATÆ MARIÆ / VIRGINIS": ("SOL.IMMACULATE_CONCEPTION", "Immaculate Conception of the BVM", "solemnity", 3),
    "IN NATIVITATE DOMINI": ("SOL.CHRISTMAS", "Nativity of the Lord", "solemnity", 2),
    "SANCTÆ FAMILIÆ IESU, MARIÆ ET IOSEPH": ("FEAST.HOLY_FAMILY", "Holy Family", "feast", 5),
    "In octava Nativitatis Domini / SANCTÆ DEI GENETRICIS MARIÆ": ("SOL.MARY_MOTHER_OF_GOD", "Mary, Mother of God", "solemnity", 3),
    "IN EPIPHANIA DOMINI": ("SOL.EPIPHANY", "Epiphany of the Lord", "solemnity", 2),
    "IN BAPTISMATE DOMINI": ("FEAST.BAPTISM", "Baptism of the Lord", "feast", 5),
    # Lent / Easter
    "DOMINICA IN PALMIS DE PASSIONE DOMINI": ("HOLY.SUN", "Palm Sunday of the Passion of the Lord", "sunday", 2),
    "FERIA V IN CENA DOMINI": ("TRIDUUM.THU", "Holy Thursday, Evening Mass of the Lord's Supper", "triduum", 1),
    "FERIA VI IN PASSIONE DOMINI": ("TRIDUUM.FRI", "Good Friday of the Passion of the Lord", "triduum", 1),
    "SABBATO SANCTO": ("TRIDUUM.SAT", "Holy Saturday", "triduum", 1),
    "DOMINICA PASCHÆ IN RESURRECTIONE DOMINI": ("EAS.1.SUN", "Easter Sunday of the Resurrection of the Lord", "solemnity", 1),
    "IN ASCENSIONE DOMINI": ("SOL.ASCENSION", "Ascension of the Lord", "solemnity", 2),
    "DOMINICA PENTECOSTES": ("SOL.PENTECOST", "Pentecost Sunday", "solemnity", 2),
}


def _weekday(day: str) -> str | None:
    for k, v in sorted(WEEKDAYS.items(), key=lambda kv: -len(kv[0])):
        if day.startswith(k) or f" / {k}" in day:
            return v
    return None


def _special(day: str) -> dict | None:
    if day in SEASON_DAYS:
        key, name, rank, prec = SEASON_DAYS[day]
        return {"key": key, "season": key.split(".")[0], "week": None, "weekday": None, "psalter_week": None,
                "title": name, "rank": rank, "precedence": prec}
    return None


def day_key_adv(section: str, day: str) -> dict:
    sp = _special(day)
    if sp:
        return sp
    m = re.match(r"^DIE (\d+) (DECEMBRIS|IANUARII)", day)
    if m:
        dd, mon = int(m.group(1)), MONTHS[m.group(2)]
        if mon == 12 and 17 <= dd <= 24:
            wk = re.search(r"HEBDOMADÆ ([IVX]+) ADVENTUS", day)
            w = roman(wk.group(1)) if wk else None
            return {"key": f"ADV.DEC{dd}", "season": "ADV", "week": w, "weekday": _weekday(day), "psalter_week": w,
                    "title": f"{dd} December (Advent)", "rank": "privileged_weekday", "precedence": 9}
        octave = mon == 12 or (mon == 1 and dd == 1)
        return {"key": f"CHR.{'DEC' if mon == 12 else 'JAN'}{dd:02d}", "season": "CHR", "week": None, "weekday": None,
                "psalter_week": None, "title": f"{dd} {'December' if mon == 12 else 'January'} (Christmas Time)",
                "rank": "octave_day" if octave else "weekday", "precedence": 9 if octave else 13}
    m = re.search(r"HEBDOMADA ([IVX]+) ADVENTUS", section)
    if m:
        wk = roman(m.group(1))
        wd = "SUN" if day == "DOMINICA" else _weekday(day)
        return {"key": f"ADV.{wk}.{wd}", "season": "ADV", "week": wk, "weekday": wd, "psalter_week": wk,
                "title": f"{DAY_NAMES[wd]} of Week {wk} of Advent", "rank": "sunday" if wd == "SUN" else "weekday",
                "precedence": 2 if wd == "SUN" else 13}
    raise ValueError(f"unmapped Advent/Christmas section {section!r} / day {day!r}")


def day_key_lqp(section: str, day: str) -> dict:
    sp = _special(day)
    if sp:
        return sp
    wd = _weekday(day)
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


def day_info(source: str, section: str, day: str) -> dict:
    if source == "PA":
        return day_key_pa(section, day)
    if source == "ADV":
        return day_key_adv(section, day)
    if source == "LQP":
        return day_key_lqp(section, day)
    raise NotImplementedError(source)

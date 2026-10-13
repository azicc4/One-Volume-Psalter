"""Shared liturgical-day helpers. Source-specific day mapping lives in the plug-ins (lh/sources/<key>.py).

Day keys:  OT.05.SUN   ADV.1.MON   ADV.DEC17   CHR.DEC26   LENT.0.WED   HOLY.MON   TRIDUUM.FRI   EAS.OCT.TUE
           EAS.3.WED   SOL.TRINITY   FEAST.BAPTISM   ORD.INVITATORY (appendix chapters)   — see docs/architecture.md
Hour codes: INV OR LAUDS MIDDAY VESPERS V1 V2 COMPLINE COMPLINE1 (Compline after I Vespers) APPX (appendix chapter)
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


def weekday_of(day: str) -> str | None:
    """'FERIA II HEBDOMADÆ I' → MON; also finds the weekday in two-line titles ('DIE 19 DECEMBRIS / FERIA II …')."""
    for k, v in sorted(WEEKDAYS.items(), key=lambda kv: -len(kv[0])):
        if day.startswith(k) or f" / {k}" in day:
            return v
    return None


def special_day(table: dict, day: str) -> dict | None:
    """Look a day title up in a plug-in's table {title: (key, English name, rank, precedence)}."""
    if day in table:
        key, name, rank, prec = table[day]
        return {"key": key, "season": key.split(".")[0], "week": None, "weekday": None, "psalter_week": None,
                "title": name, "rank": rank, "precedence": prec}
    return None


def day_info(source: str, section: str, day: str) -> dict:
    from lh.sources import plugin
    return plugin(source).day_info(section, day)


# ------------------------------------------------------------------------------------------- short names (margins)

SHORT = {
    "SOL.TRINITY": "Trinity", "SOL.CORPUS_CHRISTI": "Corpus Christi", "SOL.SACRED_HEART": "Sacred Heart",
    "SOL.CHRIST_KING": "Christ the King", "SOL.IMMACULATE_CONCEPTION": "Imm. Conception", "SOL.CHRISTMAS": "Christmas",
    "FEAST.HOLY_FAMILY": "Holy Family", "SOL.MARY_MOTHER_OF_GOD": "Mother of God", "SOL.EPIPHANY": "Epiphany",
    "FEAST.BAPTISM": "Baptism of the Lord", "HOLY.SUN": "Palm Sunday", "TRIDUUM.THU": "Holy Thu",
    "TRIDUUM.FRI": "Good Fri", "TRIDUUM.SAT": "Holy Sat", "EAS.1.SUN": "Easter Sun", "SOL.ASCENSION": "Ascension",
    "SOL.PENTECOST": "Pentecost",
}
MONTH_ABBR = {"DEC": "Dec", "JAN": "Jan"}


def short_name(d: dict) -> str:
    """Short day name for margin notes ("Trinity", "26 Dec", "Easter Oct. Mon", "Lent 1 Mon")."""
    key = d["key"]
    if key in SHORT:
        return SHORT[key]
    m = re.match(r"^(?:CHR|ADV)\.(DEC|JAN)(\d+)$", key)
    if m:
        return f"{int(m.group(2))} {MONTH_ABBR[m.group(1)]}"
    m = re.match(r"^EAS\.OCT\.(\w+)$", key)
    if m:
        return f"Easter Oct. {DAY_NAMES[m.group(1)][:3]}"
    if key == "LENT.0.WED":
        return "Ash Wed"
    m = re.match(r"^LENT\.0\.(\w+)$", key)
    if m:
        return f"{DAY_NAMES[m.group(1)][:3]} after Ash Wed"
    m = re.match(r"^HOLY\.(\w+)$", key)
    if m:
        return f"Holy {DAY_NAMES[m.group(1)][:3]}"
    m = re.match(r"^(OT|ADV|LENT|EAS)\.(\d+)\.(\w+)$", key)
    if m:
        season = {"OT": "OT", "ADV": "Adv", "LENT": "Lent", "EAS": "Easter"}[m.group(1)]
        return f"{season} {int(m.group(2))} {DAY_NAMES[m.group(3)][:3]}"
    return d.get("title") or key

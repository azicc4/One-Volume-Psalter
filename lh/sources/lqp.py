"""LQP — LH-Quadragesimae_et_Paschae.pdf: Lent, Holy Week, Paschal Triduum, Easter Time (to Pentecost).

Known quirks (workstream WS2):
* The Ascension is printed on two tracks; the volume index (p.5) lists week VI twice, "quando Ascensio celebratur
  Feria V" and "… die Dominica". See COPIES: hours printed for one track only carry the track as hour_instance.copy;
  the Ascension itself (2286-2320) and week VI Sunday-Wednesday Hora media are shared and carry no label.
* The Easter Vigil replaces the Office of Readings of Easter Sunday (GILH 212): LQP 1192-1198 print four readings
  (LECTIO PRIMA … QUARTA → slots LECT1-LECT4), each with its chant and prayer, then the Te Deum and the oration.
  The structure check uses a template exception for it (lh/verify/checks.py TEMPLATE_EXCEPTIONS).
* Triduum and Easter Octave: "Loco responsorii dicitur:" + antiphon (Christus factus est / Hæc dies) → slot RB;
  Eastertide Compline prints the Regína cæli in full under "ANTIPHONA FINALIS …" → slot MARIAN.
"""
from __future__ import annotations

import re

from lh.model.days import DAY_NAMES, roman, special_day, weekday_of

KEY = "LQP"
TITLE = "Proprium de Tempore — Tempus Quadragesimæ et Paschæ"
NON_CONTENT = [
    (1, 6, "cover, title page and volume index"),
]
# Ascension tracks (index p.5). Thursday track: … Feria IV (2189-2206 Hora media) → In Ascensione (2286) → Feria VI
# 2321, Sabbato 2346 → Dominica VII 2365. Sunday track: … Feria IV incl. Vespers/Compline 2206-2215, Feria V 2216,
# Feria VI 2242, Sabbato 2267 → In Ascensione on Sunday 2286 (its I Vespers on Saturday evening) → Feria II hebd. VII.
COPIES = [
    (2206, 2285, "Ascension Sun"),     # said only when the Ascension is transferred to Sunday VII
    (2321, 2364, "Ascension Thu"),     # Friday and Saturday after the Ascension celebrated on Thursday
]
# Hours where the source itself omits a GILH-required element (the data stay as printed; owner decides on an override,
# see TODO.md §3). (day_key, hour) -> {"missing": [slots excused], "reason": …}. Read by lh/verify/checks.py.
STRUCTURE_EXCEPTIONS = {
    ("SOL.ASCENSION", "V1"): {
        "missing": ["OPENING", "CONCLUSION"],
        "reason": "LQP 2286/2290 print no opening verse (GILH 41) and no 'Conclusio Horæ' link (GILH 54) for I Vespers "
                  "of the Ascension (nor the PSALMODIA label); every other I Vespers has them. TODO §3 T-LQP-1.",
    },
    ("SOL.ASCENSION", "OR"): {
        "missing": ["CONCLUSION"],
        "reason": "LQP 2301: the Office of Readings of the Ascension ends with the oration; the 'Conclusio Horæ' link "
                  "(GILH 69) is not printed. TODO §3 T-LQP-1.",
    },
    ("EAS.5.SUN", "MIDDAY"): {
        "missing": ["Vx3"],
        "reason": "LQP 1946: None has no versicle after its short reading (GILH 79 requires one; the other Easter "
                  "Sundays print ℣. Mane nobíscum, Dómine, allelúia). TODO §3 T-LQP-2.",
    },
}
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


# Volume index (pp.3-5), read by lh/verify/checks.py check_index: section lines and "Feria II   ol ld hm vp cp" entries.
INDEX_SECTION_RE = (r"^(HEBDOMADA CINERUM|QUADRAGESIMÆ HEBDOMADA [IVX]+|HEBDOMADA SANCTA|SACRUM TRIDUUM PASCHALE"
                    r"|OCTAVA PASCHÆ|PASCHÆ HEBDOMADA [IVX]+(?: \(quando .*\))?)$")
INDEX_WEEKDAY = {"Dominica": "SUN", "Feria II": "MON", "Feria III": "TUE", "Feria IV": "WED", "Feria V": "THU",
                 "Feria VI": "FRI", "Sabbato": "SAT"}
INDEX_SPECIAL = {"In Ascensione Domini": "SOL.ASCENSION", "Pentecostes": "SOL.PENTECOST",
                 "Feria IV Cinerum": "LENT.0.WED", "Feria V post Cineres": "LENT.0.THU",
                 "Feria VI post Cineres": "LENT.0.FRI", "Sabbato post Cineres": "LENT.0.SAT",
                 "Feria V in Cena Domini": "TRIDUUM.THU", "Feria VI in Passione Domini": "TRIDUUM.FRI",
                 "Sabbato Sancto": "TRIDUUM.SAT"}


def index_day_key(section: str, name: str) -> str | None:
    """Day key of a volume-index entry (section line, entry name), e.g. ('PASCHÆ HEBDOMADA II', 'Feria V')."""
    if name in INDEX_SPECIAL:
        return INDEX_SPECIAL[name]
    wd = INDEX_WEEKDAY.get(name)
    if wd is None:
        return None
    if section == "HEBDOMADA SANCTA":
        return f"HOLY.{wd}"
    if section == "OCTAVA PASCHÆ":
        return "EAS.1.SUN" if wd == "SUN" else f"EAS.OCT.{wd}"
    m = re.match(r"^(QUADRAGESIMÆ|PASCHÆ) HEBDOMADA ([IVX]+)", section)
    if m:
        return f"{'LENT' if m.group(1) == 'QUADRAGESIMÆ' else 'EAS'}.{roman(m.group(2))}.{wd}"
    return None


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

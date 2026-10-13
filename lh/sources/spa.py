"""SPA — LH-Sanctis-Per_annum.pdf: Proprium de Sanctis, Tempus per Annum (workstream WS4a).

Outline: month → date → (title, hours as siblings). Each celebration: date line (14.4 bold, "Die 20 ianuarii",
"Eodem die …", twice without "Die"), title (16.6 bold, may wrap; the Assumption's is non-bold, SPA 1111), rank line
(14.4 italic red Memoria / Festum / Sollemnitas; none = optional memorial), rubrics, biography, then the hours.
Parsing, day keys (SANCT.MM-DD.<litcal_key>) and the index check are shared with SP, SQ and SADV:
lh/sources/sanctis.py.

ALTERA (SPA 2002–2596, not outlined) prints alternative offices of some saints (as pastor, virgin, religious,
educator, or as a feast …). They are keyed to their saint's day; hour_instance.copy = "altera <label>", the label
printed only in the volume index (SPA 3–22), e.g. "altera Pastor". ALIA EX ORDINARIO (SPA 2597–2639) is the appendix.
Overlaps with SQ (Feb–Mar), SP (May–Jun) and SADV (30 Nov): reports/sanctis_overlaps.md.
"""
from __future__ import annotations

from lh.sources import sanctis
from lh.sources.sanctis import check_index, classify_lines, copies_report, required_slots  # noqa: F401  (hooks)

KEY = "SPA"
TITLE = "Proprium de Sanctis — Tempus per Annum"
NON_CONTENT = [
    (1, 2, "cover and title page"),
    (3, 22, "volume index (read by the Sanctis index check and for the ALTERA labels, not printed)"),
]
ALTERA_LAST_PAGE = 2596
# Celebrations printed in SPA that are not in the General Roman Calendar data (LitCal); see TODO.md §3 T-SPA-6.
EVENTS = {
    (6, 26, "ESCRIV"): {"key": "StJosemariaEscriva", "month": 6, "day": 26, "grade": 2,
                        "name_la": "Sancti Iosephmariæ Escrivá de Balaguer, presbyteri",
                        "name_en": "Saint Josemaría Escrivá, Priest", "edition": "not in the General Roman Calendar",
                        "changes": [], "movable": False},
}

_NO_OPENING = "prints no opening verse 'Deus, in adiutórium' (GILH 41, 79); every other hour of the volume has it"
_NO_CONCLUSION = "ends with the oration: no 'Conclusio Horæ, ut in Ordinario' link (GILH 54, 79)"
# Source omissions (TODO.md §3 T-SPA-2); the structure check excuses exactly these slots.
STRUCTURE_EXCEPTIONS = {
    ("SANCT.01-25.ConversionStPaul", "MIDDAY"): {"missing": ["OPENING"], "reason": f"SPA 103: Daytime Prayer {_NO_OPENING}."},
    ("SANCT.03-07.StsPerpetuaFelicity", "VESPERS"): {"missing": ["CONCLUSION"], "reason": f"SPA 330: Vespers {_NO_CONCLUSION}."},
    ("SANCT.03-08.StJohnGod", "VESPERS"): {"missing": ["CONCLUSION"], "reason": f"SPA 339: Vespers {_NO_CONCLUSION}."},
    ("SANCT.06-26.StJosemariaEscriva", "VESPERS"): {"missing": ["CONCLUSION"], "reason": f"SPA 661: Vespers {_NO_CONCLUSION}."},
    ("SANCT.08-10.StLawrenceDeacon", "OR"): {"missing": ["OPENING"], "reason": f"SPA 1055: Office of Readings {_NO_OPENING}."},
    ("SANCT.08-10.StLawrenceDeacon", "LAUDS"): {"missing": ["OPENING", "CONCLUSION"],
                                                "reason": f"SPA 1062-1067: Lauds {_NO_OPENING}, and {_NO_CONCLUSION}."},
    ("SANCT.09-14.ExaltationCross", "LAUDS"): {"missing": ["CONCLUSION"], "reason": f"SPA 1351: Lauds {_NO_CONCLUSION}."},
    ("SANCT.09-29.StsArchangels", "LAUDS"): {"missing": ["CONCLUSION"], "reason": f"SPA 1496: Lauds {_NO_CONCLUSION}."},
    ("SANCT.10-16.StMargaretAlacoque", "VESPERS"): {"missing": ["CONCLUSION"], "reason": f"SPA 1635: Vespers {_NO_CONCLUSION}."},
    ("SANCT.10-18.StLukeEvangelist", "MIDDAY"): {"missing": ["CONCLUSION"], "reason": f"SPA 1660: Daytime Prayer {_NO_CONCLUSION}."},
}


def day_info(section: str, day: str, extra: list[str] | None = None) -> dict:
    return sanctis.sanct_day_info(section, day, extra, events=EVENTS)


def day_meta(info: dict, hour, copy: str | None) -> None:
    sanctis.day_meta(info, hour, copy, EVENTS)


def __getattr__(name):             # COPIES (the ALTERA offices) is read from the volume index on first use
    if name == "COPIES":
        return sanctis.altera_copies(KEY, ALTERA_LAST_PAGE)
    raise AttributeError(name)

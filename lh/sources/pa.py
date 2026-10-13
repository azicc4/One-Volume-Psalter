"""PA — LH-Per_annum.pdf: Proprium de Tempore, Tempus per Annum (weeks I–XXXIV + solemnities of the Lord),
followed by the unoutlined appendices ALIA EX ORDINARIO / ALIA EX PROPRIO (parsed by lh/parse/appendix.py)."""
from __future__ import annotations

import re

from lh.model.days import DAY_NAMES, psalter_week_ot, roman, weekday_of

KEY = "PA"
TITLE = "Proprium de Tempore — Tempus per Annum"
NON_CONTENT = [
    (1, 2, "cover and title page"),
    (3, 8, "volume index (used by the index check, not printed)"),
]

SOLEMNITIES = {
    "SANCTISSIMÆ TRINITATIS": ("SOL.TRINITY", "Most Holy Trinity"),
    "SS.MI CORPORIS ET SANGUINIS CHRISTI": ("SOL.CORPUS_CHRISTI", "Most Holy Body and Blood of Christ"),
    "SACRATISSIMI CORDIS IESU": ("SOL.SACRED_HEART", "Most Sacred Heart of Jesus"),
    "DOMINI NOSTRI IESU CHRISTI / UNIVERSORUM REGIS": ("SOL.CHRIST_KING", "Our Lord Jesus Christ, King of the Universe"),
}


def day_info(section: str, day: str) -> dict:
    """Sections 'HEBDOMADA N' with days FERIA x / DOMINICA / SABBATO; plus the solemnities of the Lord."""
    if day in SOLEMNITIES:
        key, name = SOLEMNITIES[day]
        d = {"key": key, "season": "OT", "week": None, "weekday": None, "psalter_week": None,
             "title": name, "rank": "solemnity", "precedence": 3}
        if key == "SOL.CHRIST_KING":
            d.update(week=34, weekday="SUN")
        return d
    m = re.search(r"HEBDOMADA ([IVXL]+)$", section)
    if not m:
        raise ValueError(f"unmapped Per annum section {section!r} / day {day!r}")
    week = roman(m.group(1))
    wd = weekday_of(day)
    if wd is None:
        raise ValueError(f"unmapped Per annum day {day!r}")
    return {"key": f"OT.{week:02d}.{wd}", "season": "OT", "week": week, "weekday": wd,
            "psalter_week": psalter_week_ot(week), "title": f"{DAY_NAMES[wd]} of Week {week} in Ordinary Time",
            "rank": "sunday" if wd == "SUN" else "weekday", "precedence": 6 if wd == "SUN" else 13}

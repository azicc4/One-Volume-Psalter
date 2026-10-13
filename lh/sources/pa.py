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

# ALIA EX PROPRIO chapters (PA 6264-6290) keyed as days of their own (lh/model/build.py), by chapter title.
APPENDIX_DAYS = {
    # "Sabbatis per annum, quibus permittuntur memoriæ ad libitum, celebrari potest … memoria ad libitum Sanctæ Mariæ"
    # (PA 6269): a full office (Invitatory, Office of Readings, Lauds); psalmody and first reading of the current Saturday.
    "MEMORIA SANCTÆ MARIÆ IN SABBATO": {
        "key": "MEM.BVM_SATURDAY", "season": "OT", "week": None, "weekday": "SAT", "psalter_week": None,
        "title": "Memorial of the Blessed Virgin Mary on Saturday", "rank": "optional_memorial", "precedence": 12},
    # Dies iræ / Quid sum miser / Peccatrícem qui (week XXXIV weekdays, OR/Lauds/Vespers), then — printed without a
    # heading of their own — Salve dies and Dies ætásque (Sunday I Vespers). Weeks name them in "Ad libitum dici potest
    # hymnus …" links (slot HYMN_ALT), resolved to these hymns in link_target.
    "Hymni ad libitum dicendi in feriis hebdomadæ XXXIV": {
        "key": "PROP.HYMNS_AD_LIBITUM", "season": "PROP", "week": None, "weekday": None, "psalter_week": None,
        "title": "Hymns ad libitum (Dies iræ, Salve dies, Dies ætásque)", "rank": "appendix", "precedence": None},
}

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

"""SADV — LH-Sanctis-Adventus_et_Nativitatis.pdf: Proprium de Sanctis — Tempus Adventus et Nativitatis
(30 Nov – 7 Jan).

Traps:
- 26, 27, 28 Dec print only Vespers (rubric SA 149/154/160: Invitatory, Office of Readings, Lauds and Daytime Prayer
  are in the Proper of Time; these Vespers are for places that keep the feast as a solemnity). They are keyed to
  the temporale days CHR.DEC26-28 with hour_instance.copy "sollemnitas".
- 8 Dec, the Immaculate Conception (SA 65), is keyed to SOL.IMMACULATE_CONCEPTION, the day ADV prints in six of its
  seven start-date copies (the 1 Dec copy lacks it — WS1 can take it from here).
- 21, 23, 29, 31 Dec fall on privileged days: commemorations (rank `commemoration`, copy "commemoratio").
Unoutlined ALTERA 193-211 (13 Dec as Virgo, 2 Jan as Doctores); ALIA EX ORDINARIO 212-238.
Overlap: SPA (St Andrew, 30 Nov) — see reports/sanctis_overlaps.md. Header parsing: lh/sources/sanctis_seasons.py.
"""
from __future__ import annotations

from lh.sources.sanctis_seasons import check_index, classify_lines, required_slots, sanct_day_info  # noqa: F401  (hooks)

KEY = "SADV"
TITLE = "Proprium de Sanctis — Tempus Adventus et Nativitatis"
NON_CONTENT = [
    (1, 2, "cover and title page"),
    (3, 7, "volume index (read by the Sanctis index check, not printed)"),
]
COPIES = [
    (149, 164, "sollemnitas"),          # 26-28 Dec: Vespers where the feast is kept as a solemnity
    (194, 202, "altera Virgo"),         # 13 Dec S. Luciæ
    (203, 211, "altera Doctores"),      # 2 Jan  SS. Basilii Magni et Gregorii Nazianzeni
]
# source omissions excused by the structure check until the owner decides (TODO.md §3 T-SANCT)
STRUCTURE_EXCEPTIONS = {
    ("SANCT.12-13.luciae", "VESPERS"): {
        "missing": ["CONCLUSION"],
        "reason": "SA 133: Vespers of St Lucy prints no 'Conclusio Horæ, ut in Ordinario.' link after the prayer "
                  "(GILH 54); the ALTERA printing (SA 202) has it. TODO §3 T-SANCT-1.",
    },
}
# the volume's own index disagrees with what is printed (TODO.md §3 T-SANCT): entry -> reason
INDEX_ERRATA = {
    "01-03 #1": "index lists 'LD VP' but the Holy Name also prints an Office of Readings reading (SA 180-181)",
}


def _chr(dd: int) -> dict:
    return {"key": f"CHR.DEC{dd}", "season": "CHR", "week": None, "weekday": None, "psalter_week": None,
            "title": f"{dd} December (Christmas Time)", "rank": "octave_day", "precedence": 9}


# days the Proper of Time (ADV) also prints: same key as there (records as lh/sources/adv.py makes them)
SPECIAL = {
    "12-08": {"key": "SOL.IMMACULATE_CONCEPTION", "season": "SOL", "week": None, "weekday": None, "psalter_week": None,
              "title": "Immaculate Conception of the BVM", "rank": "solemnity", "precedence": 3},
    "12-26": _chr(26), "12-27": _chr(27), "12-28": _chr(28),
}


def day_info(section: str, day: str, extra: list[str] | None = None) -> dict:
    return sanct_day_info(section, day, extra, SPECIAL)

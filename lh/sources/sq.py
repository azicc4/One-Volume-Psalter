"""SQ — LH-Sanctis-Quadragesimae.pdf: Proprium de Sanctis — Tempus Quadragesimæ (5 Feb – 13 Apr).

Most days are commemorations ("Pro commemoratione": Office of Readings second reading + responsory + prayer, and a
Lauds / Vespers antiphon) — rank `commemoration`, hour_instance.copy "commemoratio". 22 Feb (feast), 19 Mar and
25 Mar (solemnities) are printed in full. Unoutlined ALTERA 146-165: 14 Feb (Cyril and Methodius) as a feast
("Vel ubi celebratur ut festum", SQ 21). ALIA EX ORDINARIO 166-192 (lh/parse/appendix.py).
Overlaps: SPA (Feb-Mar), SP (19 Mar, 25 Mar, 2-13 Apr) — see reports/sanctis_overlaps.md.
Header parsing: lh/sources/sanctis_seasons.py.
"""
from __future__ import annotations

from lh.sources.sanctis_seasons import check_index, classify_lines, required_slots, sanct_day_info  # noqa: F401  (hooks)

KEY = "SQ"
TITLE = "Proprium de Sanctis — Tempus Quadragesimæ"
NON_CONTENT = [
    (1, 2, "cover and title page"),
    (3, 6, "volume index (read by the Sanctis index check, not printed)"),
]
COPIES = [
    (147, 165, "altera Festum"),        # SS. Cyril and Methodius where kept as a feast (index: "Festum OL LD HM VP")
]
# source omissions excused by the structure check until the owner decides (TODO.md §3 T-SANCT)
STRUCTURE_EXCEPTIONS = {
    ("SANCT.02-14.cyrilli-et-methodii", "LAUDS"): {
        "missing": ["HYMN"],
        "reason": "SQ 153 (ALTERA, feast form): the Lauds hymn 'Hi sacerdótes Dómini sacráti' is printed without its "
                  "HYMNUS label, so it is parsed as plain text (GILH 42 requires the hymn). TODO §3 T-SANCT-3.",
    },
}


def day_info(section: str, day: str, extra: list[str] | None = None) -> dict:
    return sanct_day_info(section, day, extra)

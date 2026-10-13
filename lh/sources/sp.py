"""SP — LH-Sanctis-Paschae.pdf: Proprium de Sanctis — Tempus Paschæ (19 Mar – 11 Jun).

Every office is printed in full with Easter-time alleluias. 19 Mar and 25 Mar (solemnities) also appear in SQ;
2-13 Apr also appear in SQ as Lenten commemorations; May-June saints also appear in SPA (Ordinary Time) —
see reports/sanctis_overlaps.md. Unoutlined ALTERA 486-616: alternative offices labelled in the volume's index
(Pastor, Educator, Religiosus …), recorded as hour_instance.copy "altera <label>". ALIA EX ORDINARIO 617-647.
Header parsing: lh/sources/sanctis_seasons.py.
"""
from __future__ import annotations

from lh.sources.sanctis_seasons import check_index, classify_lines, required_slots, sanct_day_info  # noqa: F401  (hooks)

KEY = "SP"
TITLE = "Proprium de Sanctis — Tempus Paschæ"
NON_CONTENT = [
    (1, 2, "cover and title page"),
    (3, 9, "volume index (read by the Sanctis index check, not printed)"),
]
# ALTERA (486 = divider page): page ranges and the label the index gives each alternative office
COPIES = [
    (487, 495, "altera Educator"),      # 7 Apr  S. Ioannis Baptistæ de La Salle
    (496, 504, "altera Pastor"),        # 11 Apr S. Stanislai
    (505, 513, "altera Pastor"),        # 13 Apr S. Martini I
    (514, 522, "altera Pastor"),        # 23 Apr S. Adalberti
    (523, 531, "altera Pastor"),        # 24 Apr S. Fidelis de Sigmaringen
    (532, 541, "altera Vir sanctus"),   # 28 Apr S. Ludovici Mariæ Grignion de Montfort
    (542, 562, "altera Festum"),        # 29 Apr S. Catharinæ Senensis
    (563, 571, "altera Pastor"),        # 18 May S. Ioannis I
    (572, 580, "altera Religiosus"),    # 20 May S. Bernardini Senensis
    (581, 589, "altera Religiosus"),    # 25 May S. Bedæ Venerabilis
    (590, 598, "altera Religiosa"),     # 25 May S. Mariæ Magdalenæ de' Pazzi
    (599, 607, "altera Religiosus"),    # 26 May S. Philippi Neri
    (608, 616, "altera Pastor"),        # 5 Jun  S. Bonifatii
]
# the volume's own index disagrees with what is printed (TODO.md §3 T-SANCT): entry -> reason
INDEX_ERRATA = {
    "06-11 #1": "index lists 'OL LD VP' but the feast of St Barnabas prints its own Hora media (SP 477-480)",
}


def day_info(section: str, day: str, extra: list[str] | None = None) -> dict:
    return sanct_day_info(section, day, extra)

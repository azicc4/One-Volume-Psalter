"""SPA — Proprium de Sanctis — Tempus per Annum.  NOT YET PARSED: workstream WS4a in TODO.md.

Outline: date -> title and hours as siblings. Date line (14.4 bold) + title (16.6 bold, may wrap) + rank (14.4 italic red: Memoria/Festum/Sollemnitas; none for optional memorials) + bio. Unoutlined ALTERA sections SPA 2002-2596; ALIA EX ORDINARIO 2597-2639. Assumption title is non-bold (SPA 1111). Key days SANCT.MM-DD.<litcal_key>; take ranks from the LitCal propriumdesanctis data.
See docs/source-pdf-format.md for this volume's layout and traps.
"""
from __future__ import annotations

KEY = "SPA"
TITLE = "Proprium de Sanctis — Tempus per Annum"
NON_CONTENT = [(1, 3, "cover, title page, index")]   # verify with `python -m lh verify` (coverage report) when implementing


def day_info(section: str, day: str) -> dict:
    raise NotImplementedError(f"SPA: day mapping not implemented yet (workstream WS4a); section={section!r} day={day!r}")

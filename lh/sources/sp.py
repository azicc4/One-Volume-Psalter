"""SP — Proprium de Sanctis — Tempus Paschæ.  NOT YET PARSED: workstream WS4b in TODO.md.

Saints of Easter Time; overlaps SQ (19 Mar, 25 Mar, 2-13 Apr) and SPA (May-June): deduplicate by date. ALTERA 486-616; ALIA EX ORDINARIO 617-647.
See docs/source-pdf-format.md for this volume's layout and traps.
"""
from __future__ import annotations

KEY = "SP"
TITLE = "Proprium de Sanctis — Tempus Paschæ"
NON_CONTENT = [(1, 3, "cover, title page, index")]   # verify with `python -m lh verify` (coverage report) when implementing


def day_info(section: str, day: str) -> dict:
    raise NotImplementedError(f"SP: day mapping not implemented yet (workstream WS4b); section={section!r} day={day!r}")

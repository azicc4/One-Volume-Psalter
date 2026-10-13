"""SQ — Proprium de Sanctis — Tempus Quadragesimæ.  NOT YET PARSED: workstream WS4b in TODO.md.

Saints in Lent: mostly commemorations (rank line 'Pro commemoratione': an antiphon + prayer at Lauds and Vespers, an extra reading at the Office of Readings). Overlaps SPA (Feb-Mar) and SP. ALTERA 145-164; ALIA EX ORDINARIO 165-192.
See docs/source-pdf-format.md for this volume's layout and traps.
"""
from __future__ import annotations

KEY = "SQ"
TITLE = "Proprium de Sanctis — Tempus Quadragesimæ"
NON_CONTENT = [(1, 3, "cover, title page, index")]   # verify with `python -m lh verify` (coverage report) when implementing


def day_info(section: str, day: str) -> dict:
    raise NotImplementedError(f"SQ: day mapping not implemented yet (workstream WS4b); section={section!r} day={day!r}")

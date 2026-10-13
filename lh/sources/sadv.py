"""SADV — Proprium de Sanctis — Tempus Adventus et Nativitatis.  NOT YET PARSED: workstream WS4b in TODO.md.

Saints of Advent/Christmas Time; SA 26-28 Dec give only Vespers (rubric SA 149); ALTERA 193-211; ALIA EX ORDINARIO 212-238. Immaculate Conception at SA 65 also fills the gap in ADV's 1 Dec copy (WS1).
See docs/source-pdf-format.md for this volume's layout and traps.
"""
from __future__ import annotations

KEY = "SADV"
TITLE = "Proprium de Sanctis — Tempus Adventus et Nativitatis"
NON_CONTENT = [(1, 3, "cover, title page, index")]   # verify with `python -m lh verify` (coverage report) when implementing


def day_info(section: str, day: str) -> dict:
    raise NotImplementedError(f"SADV: day mapping not implemented yet (workstream WS4b); section={section!r} day={day!r}")

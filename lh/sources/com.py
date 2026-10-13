"""COM — Communia et Officium Defunctorum.  NOT YET PARSED: workstream WS3 in TODO.md.

Four seasonal copies of the Commons (Advent/Christmas 4-416, Lent 417-817, Easter 818-1207, Per annum 1208-1640), Office of the Dead 1641-1675, ALIA EX ORDINARIO 1675-1699. Collapse the copies into one Common per kind with seasonal variants; key days COMMON.<NAME>[.<variant>] (e.g. COMMON.MARTYRS.ONE).
See docs/source-pdf-format.md for this volume's layout and traps.
"""
from __future__ import annotations

KEY = "COM"
TITLE = "Communia et Officium Defunctorum"
NON_CONTENT = [(1, 3, "cover, title page, index")]   # verify with `python -m lh verify` (coverage report) when implementing


def day_info(section: str, day: str) -> dict:
    raise NotImplementedError(f"COM: day mapping not implemented yet (workstream WS3); section={section!r} day={day!r}")

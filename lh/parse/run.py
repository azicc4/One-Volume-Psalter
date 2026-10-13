"""Parse a whole source PDF into hour instances (L2+L3)."""
from __future__ import annotations

from lh.extract.lines import load_lines
from lh.parse.appendix import parse_appendices
from lh.parse.hour import Hour, parse_hour, segment


def parse_pdf(key: str, p0: int | None = None, p1: int | None = None) -> tuple[list[Hour], list]:
    lines = load_lines(key, p0, p1)
    # the unoutlined appendices (ALIA EX ORDINARIO / ALIA EX PROPRIO) are parsed by lh/parse/appendix.py
    cut = next((i for i, L in enumerate(lines) if L.kind == "week" and L.text.startswith("ALIA EX")), None)
    body = lines if cut is None else lines[:cut]
    hours, outside = segment(body, key)
    for h in hours:
        parse_hour(h)
    if cut is not None:
        hours += parse_appendices(lines[cut:], key)
    return hours, outside

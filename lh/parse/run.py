"""Parse a whole source PDF into hour instances (L2+L3)."""
from __future__ import annotations

from lh.extract.lines import load_lines
from lh.parse.appendix import parse_appendices
from lh.parse.hour import Hour, Outside, parse_hour, segment


def parse_pdf(key: str, p0: int | None = None, p1: int | None = None) -> tuple[list[Hour], list[Outside]]:
    """Returns (hours, outside lines). Every line of the page range ends up in exactly one hour or one Outside entry;
    the coverage check (lh/verify/coverage.py) relies on this."""
    lines = load_lines(key, p0, p1)
    # the unoutlined appendices (ALIA EX ORDINARIO / ALIA EX PROPRIO) are parsed by lh/parse/appendix.py
    cut = next((i for i, L in enumerate(lines) if L.kind == "week" and L.text.startswith("ALIA EX")), None)
    body = lines if cut is None else lines[:cut]
    hours, outside = segment(body, key)
    for h in hours:
        parse_hour(h)
    if cut is not None:
        apx = parse_appendices(lines[cut:], key)
        hours += apx
        in_apx = {id(L) for h in apx for L in h.lines}
        outside += [Outside(L, "heading" if L.kind == "week" else "front", "ALIA EX", "")
                    for L in lines[cut:] if id(L) not in in_apx]
    return hours, outside

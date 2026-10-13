"""Scripture reference parsing shared by the Felix Just import and the LH comparison.

Handles English style ("Ps 5:2-10, 12-13", "Rev 4:11; 5:9, 10, 12", "Isa 61:10—62:5") and the LH's Latin style
("Psalmus 5, 2-10. 12-13", "Ap 4, 11; 5, 9. 10. 12", "Is 61, 10 — 62, 5"). A reference becomes
(book, [(chapter, first_verse, last_verse_or_None), …]) at whole-verse granularity; verse-part letters
(3c, 10b) are kept separately so differences in partial verses can be reported as minor.
"""
from __future__ import annotations

import re

BOOKS = {
    # Latin LH abbreviations → canonical English
    "Ps": "Ps", "Psalmus": "Ps", "1 Chr": "1 Chr", "1 Sam": "1 Sam", "Ap": "Rev", "Dan": "Dan", "Deut": "Deut",
    "Eccli": "Sir", "Eph": "Eph", "Ex": "Exod", "Ez": "Ezek", "Hab": "Hab", "Ier": "Jer", "Is": "Isa",
    "Iudt": "Jdt", "Lc": "Luke", "Phil": "Phil", "Sap": "Wis", "Tob": "Tob", "Col": "Col", "1 Petr": "1 Pet",
    "1 Tim": "1 Tim", "1 Th": "1 Thess",
    # English (Felix Just)
    "Rev": "Rev", "Exod": "Exod", "Ezek": "Ezek", "Jer": "Jer", "Isa": "Isa", "Judith": "Jdt", "Jdt": "Jdt",
    "Sir": "Sir", "Sirach": "Sir", "Wis": "Wis", "Tobit": "Tob", "Luke": "Luke", "1 Pet": "1 Pet", "1 Peter": "1 Pet",
    "1 Thess": "1 Thess",
}
_BOOK_RE = re.compile(r"^(?:Cf\.\s*)?(" + "|".join(sorted(map(re.escape, BOOKS), key=len, reverse=True)) + r")\b\.?\s*(.*)$")


def parse_ref(ref: str) -> tuple[str, list[tuple[int, int, int | None]], set[str]]:
    """Return (book, ranges, partial_verse_labels). Raises ValueError if unparseable."""
    ref = ref.strip()
    ref = re.sub(r"\s*\(.*\)\s*$", "", ref)              # drop "(I: Aleph)" / "( Lent: …)"
    m = _BOOK_RE.match(ref)
    if not m:
        raise ValueError(f"unknown book in {ref!r}")
    book, rest = BOOKS[m.group(1)], m.group(2).strip()
    english = ":" in rest
    ranges: list[tuple[int, int, int | None]] = []
    partial: set[str] = set()
    rest = rest.replace("—", "-").replace("–", "-")
    rest = re.sub(r"\s*-\s*", "-", rest)
    rest = re.sub(r"(\d)\s+([a-c]{1,2})\b", r"\1\2", rest)        # "10 b" → "10b"
    for group in rest.split(";"):
        group = group.strip()
        if not group:
            continue
        if english:
            mm = re.match(r"^(\d+):(.*)$", group)
        else:
            mm = re.match(r"^(\d+),\s*(.*)$", group)
        if mm:
            ch, spec = int(mm.group(1)), mm.group(2)
        else:
            if book == "Ps" and re.match(r"^\d+$", group):     # bare psalm number = whole psalm
                ranges.append((int(group), 1, None))
                continue
            raise ValueError(f"cannot parse {ref!r}")
        if not english:   # Latin cross-chapter "10-62, 5" (next chapter) → "10-62:5"
            spec = re.sub(r"(\d+[a-c]*)-(\d+),\s*(\d+)",
                          lambda m: f"{m.group(1)}-{m.group(2)}:{m.group(3)}" if int(m.group(2)) == ch + 1 else m.group(0),
                          spec)
        parts = re.split(r"[.,]\s*", spec)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            cm = re.match(r"^(\d+)([a-c]*)-(\d+)[:,](\d+)([a-c]*)$", part)  # cross-chapter "10-62:5"
            if cm:
                ranges.append((ch, int(cm.group(1)), None))
                ch = int(cm.group(3))
                ranges.append((ch, 1, int(cm.group(4))))
                continue
            rm = re.match(r"^(\d+)([a-c]*)(?:-(\d+)([a-c]*))?$", part)
            if not rm:
                # Latin cross-chapter written "10 - 62, 5" splits on the comma: "10-62" then "5"
                raise ValueError(f"cannot parse part {part!r} of {ref!r}")
            a, al, b, bl = int(rm.group(1)), rm.group(2), rm.group(3), rm.group(4)
            if al:
                partial.add(f"{a}{al}")
            if bl:
                partial.add(f"{b}{bl}")
            ranges.append((ch, a, int(b) if b else a))
    return book, merge(ranges), partial


def merge(ranges):
    out = []
    for ch, a, b in sorted(ranges, key=lambda r: (r[0], r[1])):
        if out and out[-1][0] == ch and out[-1][2] is not None and a <= out[-1][2] + 1:
            pb = out[-1][2]
            out[-1] = (ch, out[-1][1], None if b is None else max(pb, b))
        else:
            out.append((ch, a, b))
    return out


def fmt(book: str, ranges) -> str:
    out, last_ch = [], None
    for ch, a, b in ranges:
        span = f"{a}" if b == a else (f"{a}-end" if b is None else f"{a}-{b}")
        if book == "Ps":
            out.append(span if last_ch == ch else f"{ch}:{span}")
        else:
            out.append(span if last_ch == ch else f"{ch}:{span}")
        last_ch = ch
    return f"{book} " + ", ".join(out)


def psalm_ranges(base: int, verses: list[str]) -> list[tuple[int, int, int]]:
    """LH psalm unit verse labels (['2','3','3c','10b',…]) → merged whole-verse ranges in chapter=psalm."""
    nums = sorted({int(re.match(r"\(?(\d+)", v).group(1)) for v in verses if re.match(r"\(?\d", v)})
    return merge([(base, n, n) for n in nums])

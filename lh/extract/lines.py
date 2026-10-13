"""L2: turn L1 rows into visual lines made of styled runs, and classify each line by its signature.

See docs/source-pdf-format.md for the style table this encodes.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from lh.extract.spans import open_l1

RED, BLUE, BLACK = "ff0000", "0000ee", "000000"
BOLD, ITALIC = 16, 2

HOUR_HEADERS = {
    "Ad Invitatorium": "INV",
    "Ad Officium lectionis": "OR",
    "Ad Laudes matutinas": "LAUDS",
    "Ad Horam mediam": "MIDDAY",
    "Ad Vesperas": "VESPERS",
    "Ad I Vesperas": "V1",
    "Ad II Vesperas": "V2",
    "Ad Completorium": "COMPLINE",
}
SUBHOURS = {"Ad Tertiam": "TERCE", "Ad Sextam": "SEXT", "Ad Nonam": "NONE"}


@dataclass
class Run:
    text: str
    size: float
    color: str
    flags: int

    @property
    def red(self):
        return self.color == RED

    @property
    def blue(self):
        return self.color == BLUE

    @property
    def italic(self):
        return bool(self.flags & ITALIC)

    @property
    def bold(self):
        return bool(self.flags & BOLD)

    @property
    def verse_no(self):
        return self.size < 7 and self.red


@dataclass
class Line:
    id: int                      # first L1 row id (stable reading order)
    page: int
    block: int
    x0: float
    y0: float
    x1: float
    runs: list[Run]
    link: int | None = None
    page_top: bool = False       # first visual line on its page
    block_start: bool = False    # first line of its PyMuPDF block (stanza/paragraph start)
    kind: str = ""
    l1_ids: list[int] = field(default_factory=list)
    lead_dagger: bool = False    # line begins with a red "†": psalm resumes here after the antiphon's incipit

    @property
    def text(self) -> str:
        return ("† " if self.lead_dagger else "") + norm_space("".join(r.text for r in self.runs))

    @property
    def body(self) -> str:
        """Text without a leading verse number / label run."""
        return norm_space("".join(r.text for r in self.runs if not r.verse_no))

    @property
    def verse(self) -> str | None:
        r = self.runs[0]
        return norm_space(r.text) if r.verse_no else None

    def __repr__(self):
        return f"<{self.kind} p{self.page} x{self.x0:.0f} {self.text[:60]!r}>"


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _merge_runs(runs: list[Run]) -> list[Run]:
    """Merge adjacent runs of identical style (pdftohtml-style fragmenting)."""
    out: list[Run] = []
    for r in runs:
        if out and (out[-1].size, out[-1].color, out[-1].flags) == (r.size, r.color, r.flags):
            out[-1] = Run(out[-1].text + r.text, r.size, r.color, r.flags)
        else:
            out.append(r)
    return out


def classify(L: Line) -> str:
    r0 = L.runs[0]
    text = L.text
    sizes = {r.size for r in L.runs}
    if r0.size >= 20:
        return "week"
    if r0.size >= 16 and r0.bold:
        return "day"
    if r0.size == 14.4 and r0.bold and r0.color == BLACK:
        if text in HOUR_HEADERS:
            return "hour"
        return "subhour"
    if r0.verse_no:
        return "verse"
    if any(r.size == 10.1 and r.red for r in L.runs):
        return "label"  # small-caps red label: HYMNUS, PSALMODIA, LECTIO …, RESPONSORIUM …, PRECES
    if r0.blue:
        return "link"
    if r0.red:
        t = r0.text.strip()
        if t.startswith("Ant."):
            return "ant"
        if t.startswith("℣"):
            return "V"
        if t.startswith("℟"):
            return "R"
        if t == "—":
            return "dash"
        if L.x0 > 140 and all(r.red for r in L.runs):
            return "rubric_c"   # centred red: psalm heading/title, canticle ref, section numeral, Oratio
        return "rubric"
    if all(r.size == 10.8 for r in L.runs) and r0.color == BLACK:
        return "subtitle"
    if r0.italic:
        return "italic"
    if 10.8 in sizes and r0.size == 10.8:
        return "subtitle"
    return "text"


def load_lines(key: str, p0: int | None = None, p1: int | None = None) -> list[Line]:
    con = open_l1(key)
    q = "SELECT id,page,block,x0,y0,x1,spans,link_page FROM line"
    args: tuple = ()
    if p0 is not None:
        q += " WHERE page BETWEEN ? AND ?"
        args = (p0, p1 if p1 is not None else p0)
    q += " ORDER BY id"
    lines: list[Line] = []
    prev_page, prev_block = None, None
    for row in con.execute(q, args):
        runs = [Run(t, s, c, f) for t, s, c, f in json.loads(row["spans"])]
        page, block = row["page"], row["block"]
        if lines and lines[-1].page == page and abs(lines[-1].y0 - row["y0"]) < 4 and row["x0"] > lines[-1].x0:
            # same visual line split by PyMuPDF (e.g. inline verse numbers in prose)
            L = lines[-1]
            sep = [] if L.runs[-1].text.endswith(" ") or runs[0].text.startswith(" ") else [Run(" ", 14.4, BLACK, 0)]
            L.runs = _merge_runs(L.runs + sep + runs)
            L.x1 = row["x1"]
            L.link = L.link or row["link_page"]
            L.l1_ids.append(row["id"])
            continue
        L = Line(row["id"], page, block, row["x0"], row["y0"], row["x1"], _merge_runs(runs), row["link_page"],
                 page_top=page != prev_page, block_start=(page != prev_page or block != prev_block),
                 l1_ids=[row["id"]])
        lines.append(L)
        prev_page, prev_block = page, block
    con.close()
    for L in lines:
        if len(L.runs) > 2 and L.runs[0].verse_no and L.runs[1].red and L.runs[1].text.strip() == "†":
            L.lead_dagger = True        # "2 † Dómine…": verse number, then the intonation mark
            L.runs = [L.runs[0]] + L.runs[2:]
        r0 = L.runs[0]
        if r0.red and r0.text.strip() == "†" and len(L.runs) > 1:
            L.lead_dagger = True
            L.runs = L.runs[1:]
            if not L.runs[0].text.strip():
                L.runs = L.runs[1:] or L.runs
        L.kind = classify(L)
    return lines

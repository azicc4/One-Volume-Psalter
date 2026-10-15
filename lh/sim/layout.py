"""The printed book as the simulator sees it: the page of every label, the spread it falls on, and its section.

Pages come from the LaTeX labels of the last full build (build/latex/book.aux) and the page labels of
book/out/book.pdf; where each text is printed comes from the book generator itself (lh/render/book.py), so the
simulation always follows the book as built.
"""
from __future__ import annotations

import re
from functools import cached_property

import pymupdf

from lh.config import BOOK, BUILD

AUX = BUILD / "latex" / "book.aux"
PDF = BOOK / "out" / "book.pdf"
VIRTUAL = 100_000                                       # page indexes of what-if pages that are not in the book
NEWLABEL = re.compile(r"\\newlabel\{([^}]*)\}\{\{[^}]*\}\{([^}]*)\}")

# section of the book (top-level bookmark) → the ribbon that keeps its place (lh/render/common.py RIBBONS)
SECTION_ROLE = [("Proper of Saints", "S"), ("Commons", "C"), ("The Ordinary", "O"), ("Proper of Time", "T"),
                ("Hymns", "H"), ("The Psalter", "P"), ("Canticles", "P"), ("Readings of the Office of Readings", "R"),
                ("Indexes", "X")]
# the first part of the Proper of Time after the four-week cycle (lh/render/book.py proper_of_time)
TIME_AFTER_GRID = "Ordinary Time: proper to each week"


class Layout:
    def __init__(self, aux=AUX, pdf=PDF, weekly_psalter: bool = False):
        self.weekly_psalter = weekly_psalter
        if not aux.exists() or not pdf.exists():
            raise SystemExit("build the full book first: python -m lh book")
        doc = pymupdf.open(pdf)
        self.n = doc.page_count
        self.index_of_label = {}
        for p in doc:
            self.index_of_label.setdefault(p.get_label(), p.number)
        self.sections = []                              # (first page index, title, role)
        roles = dict(SECTION_ROLE)
        self.time_weeks = None                          # first page after the four-week cycle (Proper of Time)
        for lvl, title, page in doc.get_toc():
            if lvl == 1 and page > 0:
                self.sections.append((page - 1, title, roles.get(title, "X")))
            if lvl == 2 and page > 0 and self.time_weeks is None and title.startswith(TIME_AFTER_GRID):
                self.time_weeks = page - 1
        self.sections.sort()
        self.page_label = {}                            # LaTeX label → page index
        for name, printed in NEWLABEL.findall(aux.read_text(encoding="utf-8", errors="replace")):
            if printed in self.index_of_label:
                self.page_label[name] = self.index_of_label[printed]
        self.labels = [doc[i].get_label() for i in range(self.n)]

    @cached_property
    def book(self):
        """The book generator with every home and alias resolved (as when the book was written)."""
        from lh.render.book import Book
        b = Book(weekly_psalter=self.weekly_psalter)
        b.body()
        return b

    def page(self, label: str) -> int | None:
        return self.page_label.get(label)

    def object_page(self, oid: str) -> int | None:
        b = self.book
        o = b.objs.get(oid)
        if o is None:
            return None
        return self.page(b.anchor(o))

    @staticmethod
    def spread(i: int) -> int:
        return (i + 1) // 2

    def section(self, i: int) -> tuple[str, str]:
        if i >= VIRTUAL:                                # a what-if Psalter in cycle order (lh/sim/whatif.py)
            return ("Psalter in cycle order (what-if)", "P")
        hit = ("Front matter", "X")
        for first, title, role in self.sections:
            if first <= i:
                hit = (title, role)
        return hit

    def role(self, i: int) -> str:
        return self.section(i)[1]

    def time_part(self, i: int) -> str:
        """In the Proper of Time: "TG" the four-week cycle, "TW" what follows it (the weeks of Ordinary Time, the
        days with wholly proper offices). Ribbon 4 keeps the first, ribbon 5 the second, so 5 always lies after 4."""
        return "TW" if self.time_weeks is not None and self.time_weeks <= i < VIRTUAL else "TG"

    def label(self, i: int) -> str:
        return self.labels[i] if 0 <= i < self.n else "?"

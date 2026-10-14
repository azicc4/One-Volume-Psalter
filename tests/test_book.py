"""Layout guarantees of the generated books (run after `python -m lh book --poc` and/or `python -m lh book`).
Each test runs on every book whose PDF and generated LaTeX exist: the proof of concept and the full book."""
import re

import pymupdf
import pytest

from lh.config import BOOK

BOOKS = [name for name in ("poc", "book")
         if (BOOK / "out" / f"{name}.pdf").exists() and (BOOK / "generated" / f"{name}_body.tex").exists()]
pytestmark = pytest.mark.skipif(not BOOKS, reason="run `python -m lh book --poc` or `python -m lh book` first")


def pdf(name):
    return BOOK / "out" / f"{name}.pdf"


def tex(name):
    return (BOOK / "generated" / f"{name}_body.tex").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", BOOKS)
def test_trim_size_6_by_9_25_inches(name):
    doc = pymupdf.open(pdf(name))
    for i in {0, doc.page_count // 2, doc.page_count - 1}:
        r = doc[i].rect
        assert (round(r.width), round(r.height)) == (432, 666)


@pytest.mark.parametrize("name", BOOKS)
def test_margin_notes_do_not_overlap(name):
    """Text blocks in the outer margin (outside the text block) must not intersect on any page."""
    doc = pymupdf.open(pdf(name))
    bad = []
    for page in doc:
        w = page.rect.width
        blocks = [b for b in page.get_text("blocks") if b[6] == 0]
        # outer margin: right of the text block on odd pages, left of it on even pages
        notes = [pymupdf.Rect(b[:4]) for b in blocks if b[0] > w - 1.25 * 72 or b[2] < 1.25 * 72 - 6]
        for i, a in enumerate(notes):
            for b in notes[i + 1:]:
                if a.intersects(b) and (a & b).height > 1.5:
                    bad.append(page.number + 1)
    assert not bad, f"overlapping margin notes on pages {sorted(set(bad))}"


@pytest.mark.parametrize("name", BOOKS)
def test_no_strophe_gap_inside_a_couplet(name):
    """\\psbreak may only precede a line that begins a verse (\\psl) or a couplet (\\psc), never a continuation."""
    assert not re.search(r"\\psbreak\s*\\psk\{", tex(name))


@pytest.mark.parametrize("name", BOOKS)
def test_hour_heads_carry_ribbon_refs(name):
    """Every hour head in the four-week cycle gives the Ordinary page (O); all but Compline also give psalm pages (P)."""
    t = tex(name)
    start = t.index(r"\chapter{Propers of Time}" if name == "poc" else r"\chapter{Proper of Time}")
    end = t.index(r"\chapter{Hymns}") if name == "poc" else t.index(r"\section{Ordinary Time: proper to each week}")
    heads = re.findall(r"\\hourhead\{(.*?)\}\{(.*)", t[start:end])
    assert heads and all(r"\ribbon{O}" in refs for _, refs in heads)
    assert all(r"\ribbon{P}" in refs for title, refs in heads if not title.startswith("Compline"))

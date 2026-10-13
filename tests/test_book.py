"""Layout guarantees of the generated book (run after `python -m lh book --poc`)."""
import re

import pymupdf
import pytest

from lh.config import BOOK

PDF = BOOK / "out" / "poc.pdf"
TEX = BOOK / "generated" / "poc_body.tex"
pytestmark = pytest.mark.skipif(not PDF.exists() or not TEX.exists(), reason="run `python -m lh book --poc` first")


def test_trim_size_6_by_9_25_inches():
    doc = pymupdf.open(PDF)
    r = doc[0].rect
    assert (round(r.width), round(r.height)) == (432, 666)


def test_margin_notes_do_not_overlap():
    """Text blocks in the outer margin (outside the text block) must not intersect on any page."""
    doc = pymupdf.open(PDF)
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


def test_no_strophe_gap_inside_a_couplet():
    """\\psbreak may only precede a line that begins a verse (\\psl) or a couplet (\\psc), never a continuation."""
    tex = TEX.read_text(encoding="utf-8")
    assert not re.search(r"\\psbreak\s*\\psk\{", tex)


def test_hour_heads_carry_ribbon_refs():
    """Every hour head in the Proper of Time gives the Ordinary page (O); all but Compline also give psalm pages (P)."""
    tex = TEX.read_text(encoding="utf-8")
    propers = tex[tex.index(r"\chapter{Propers of Time}"):tex.index(r"\chapter{Hymns}")]
    heads = re.findall(r"\\hourhead\{(.*?)\}\{(.*)", propers)
    assert heads and all(r"\ribbon{O}" in refs for _, refs in heads)
    assert all(r"\ribbon{P}" in refs for title, refs in heads if not title.startswith("Compline"))

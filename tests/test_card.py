"""The Ordinary card (B-14) and whole Compline (B-15), against the last full build (`python -m lh book`)."""
import datetime as dt
import re

import pymupdf
import pytest

from lh.config import BOOK, BUILD

CARD = BOOK / "out" / "card.pdf"
AUX = BUILD / "latex" / "book.aux"
pytestmark = pytest.mark.skipif(not CARD.exists() or not AUX.exists(), reason="run `python -m lh book` first")


def test_card_is_two_cards_printed_on_both_sides():
    doc = pymupdf.open(CARD)
    assert doc.page_count == 4
    assert all((round(p.rect.width), round(p.rect.height)) == (396, 612) for p in doc)     # 5.5 x 8.5 in


def test_card_carries_the_fixed_parts():
    text = " ".join(p.get_text() for p in pymupdf.open(CARD))
    for incipit in ("Veníte, exsultémus", "Deus, in adiutórium", "Benedíctus Dóminus", "Pater noster",
                    "Magníficat", "Nunc dimíttis", "Noctem quiétam", "Te Deum laudámus", "Salve, Regína",
                    "Regína cæli"):
        assert incipit in text, incipit


def test_compline_forms_print_their_psalms_whole():
    aux = AUX.read_text(encoding="utf-8", errors="replace")
    forms = set(re.findall(r"newlabel\{cp:ord:compline:([A-Z0-9]+):o:ps", aux))
    assert {"SAT1", "SUN", "MON", "TUE", "WED", "THU", "FRI", "EASTER"} <= forms


def test_simulated_compline_stays_in_the_form():
    from lh.sim.run import Sim
    sim = Sim()
    _, steps = sim.steps(dt.date(2027, 2, 9))                   # Tuesday: Compline of Tuesday, Ps 143
    comp = [s for s in steps if s.hour == "COMPLINE" and s.slot != "HEAD"]
    first, nxt = sim.L.page("ord:compline:TUE"), sim.L.page("ord:compline:WED")     # the form's own pages
    assert comp and all(first <= s.page <= nxt for s in comp if s.slot not in ("OPENING", "MARIAN")), \
        [(s.slot, sim.L.label(s.page)) for s in comp]

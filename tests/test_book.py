"""Layout guarantees of the generated books (run after `python -m lh book --poc` and/or `python -m lh book`).
Each test runs on every book whose PDF and generated LaTeX exist: the proof of concept and the full book."""
import re

import pymupdf
import pytest

from lh.config import BOOK, BUILD

BOOKS = [name for name in ("poc", "book", "book-weekly")
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
def test_every_page_but_the_title_shows_its_number(name):
    """Section openers and blank pages carry the folio too, and no running head runs into it ("martyrum245")."""
    doc = pymupdf.open(pdf(name))
    missing = [page.get_label() for page in doc
               if page.number and page.get_label() not in {w[4] for w in page.get_text("words")}]
    assert not missing, f"pages without a separate page number: {missing[:20]}"


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
    """Every hour head in the four-week cycle gives its ribbon pages: psalm pages (P) for every hour but Compline and
    the Invitatory (card, front), the Ordinary page (O) for Daytime Prayer and Compline (B-16)."""
    t = tex(name)
    start = t.index(r"\chapter{Propers of Time}" if name == "poc" else r"\chapter{Proper of Time}")
    end = t.index(r"\chapter{Hymns}") if name == "poc" else t.index(r"\section{Ordinary Time: proper to each week}")
    body = re.sub(r"\\objlabel\{hh:[^}]*\}", "", t[start:end])        # invisible hour labels (lh/sim)
    body = re.sub(r"\\hourmark\{[^}]*\}", "", body)                    # footer marks of the day and hour
    heads = re.findall(r"\\hourhead\{(.*?)\}\{(.*)", body)
    assert heads
    for title, refs in heads:                          # the proof of concept too (common.ribbon_refs, B-16)
        if title.startswith("Invitatory"):
            assert r"\cardref{front}" in refs
        elif title.startswith("Compline") or title.startswith("Daytime"):
            assert r"\ribbon{O}" in refs
        if not title.startswith(("Compline", "Invitatory")):
            assert r"\ribbon{P}" in refs, title


@pytest.mark.parametrize("name", [n for n in BOOKS if n != "poc"])
def test_proper_of_time_pages_show_the_day_and_hour(name):
    """Every page of the four-week cycle carries its day and hour in the outer bottom corner ("Wk. 1 Sun: 1st V.")."""
    doc = pymupdf.open(pdf(name))
    toc = [(t[1], t[2] - 1) for t in doc.get_toc() if t[0] == 1]
    start = next(p for t, p in toc if t == "Proper of Time")
    end = next(p for t, p in toc if t.startswith("Proper of Time")) + 300          # the grid: weeks I–IV
    missing = []
    for i in range(start + 1, end):
        page = doc[i]
        foot = " ".join(w[4] for w in page.get_text("words") if w[1] > page.rect.height - 50)
        if not foot.startswith(("Wk.", "OT Wk.")):
            missing.append((page.get_label(), foot))
    assert not missing, missing[:10]


@pytest.mark.parametrize("name", [n for n in BOOKS if n != "poc"])
def test_psalter_margin_notes_keep_a_quarter_inch_from_the_trim(name):
    doc = pymupdf.open(pdf(name))
    toc = [(t[1], t[2] - 1) for t in doc.get_toc() if t[0] == 1]
    a = next(p for t, p in toc if t == "The Psalter")
    b = next(p for t, p in toc if t == "Canticles")
    bad = []
    for i in range(a, b):
        page = doc[i]
        w = page.rect.width
        for x0, y0, x1, y1, *_ in page.get_text("blocks"):
            if (x0 < 17.5 or x1 > w - 17.5) and y1 < page.rect.height - 40:      # 18 pt = 1/4 in, less rounding
                bad.append(page.get_label())
    assert not bad, sorted(set(bad))[:20]


@pytest.mark.parametrize("name", [n for n in BOOKS if n != "poc"])
def test_hymns_section_runs_in_page_high_columns(name):
    """The Hymns section is set in two page-high columns: a hymn runs down the left column to the foot of the page
    and goes on at the top of the right one (not in a short two-column block of its own)."""
    t = tex(name)
    part = t[t.index(r"\chapter{Hymns}"):t.index(r"\chapter", t.index(r"\chapter{Hymns}") + 10)]
    assert r"\begin{hymnflow}" in part and r"\begin{hymn}" not in part
    doc = pymupdf.open(pdf(name))
    toc = doc.get_toc()
    i = next(k for k, e in enumerate(toc) if e[0] == 1 and e[1] == "Hymns")
    end = next(e[2] - 1 for e in toc[i + 1:] if e[0] == 1)
    starts = sorted(e[2] - 1 for e in toc[i + 1:] if e[0] == 2 and e[2] - 1 < end)
    full, short = 0, []
    for a, b in zip(starts, starts[1:] + [end]):
        for p in range(a, b - 1):                       # every page of a part but its last (balanced) one
            page = doc[p]
            mid = page.rect.width / 2
            left = [bl for bl in page.get_text("blocks") if bl[2] < mid + 10 and 60 < bl[1] < page.rect.height - 50]
            if left and max(bl[3] for bl in left) > page.rect.height - 150:
                full += 1
            else:
                short.append(page.get_label())
    assert full and len(short) <= full // 10, short[:10]


@pytest.mark.parametrize("name", [n for n in BOOKS if n != "poc"])
def test_compline_footers_change_on_the_page_where_each_form_begins(name):
    """The outer bottom corner names the form of Compline on the page where its heading is, not on the page before
    ("Sat: Compl." on the last page of Saturday's Compline, not "Sun: Compl.")."""
    aux = BUILD / "latex" / f"{name}.aux"
    if not aux.exists():
        pytest.skip("no aux file")
    labels = dict(re.findall(r"\\newlabel\{ord:compline:(\w+)\}\{\{[^}]*\}\{([^}]*)\}", aux.read_text(encoding="utf-8")))
    doc = pymupdf.open(pdf(name))
    index = {p.get_label(): p.number for p in doc}
    def foot(i):
        page = doc[i]
        return " ".join(w[4] for w in page.get_text("words") if w[1] > page.rect.height - 50 and not w[4].isdigit())
    abbr = {"SAT1": "Sat", "SUN": "Sun", "MON": "Mon", "TUE": "Tue", "WED": "Wed", "THU": "Thu", "FRI": "Fri"}
    for form, short in abbr.items():
        i = index[labels[form]]
        assert foot(i) == f"{short}: Compl.", (form, foot(i))
        assert foot(i - 1) != f"{short}: Compl.", (form, foot(i - 1))


@pytest.mark.parametrize("name", [n for n in BOOKS if n != "poc"])
def test_eastertide_alleluia_is_one_antiphon_with_tp(name):
    """An Eastertide antiphon that only adds an alleluia is not printed again: the antiphon carries "(T.P.
    Allelúia)" (Salva nos at Compline, and the like)."""
    t = tex(name)
    ordinary = t[t.index(r"\chapter{The Ordinary}"):t.index(r"\chapter{Proper of Time}")]
    assert "requiescámus in pace, allelúia" not in ordinary
    assert re.search(r"requiescámus in pace\.\\tp\{Allelúia\}", ordinary)
    assert t.count(r"\tp{") > 200

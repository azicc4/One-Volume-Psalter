# One-Volume Psalter

A single-volume *Liturgia Horarum* (Latin text, English rubrics), 6 × 9.25 in, ten ribbons:

| Ribbon | Section |
|---|---|
| 1 | **Proper of Saints** |
| 2 | **Commons** |
| 3 | **Ordinary** — "Finding the Office", fixed texts; each hour heading gives the pages of its fixed parts |
| 4 | **Proper of Time** — the four-week cycle, every part of every hour with its seasonal variants side by side; each hour heading gives the ribbon pages (O Ordinary · P psalms · R readings) |
| 5 | **Hymns** |
| 6–9 | **Psalter** (+ Canticles) — all 150 psalms, Hebrew numbering (Vulgate in parentheses); the margin marks where each portion is prayed (`I Mon L.1` = Week I, Monday, Lauds, psalm 1) and, below a rule, every other use (feasts); unused verses in smaller type |
| 10 | **Office of Readings readings** and responsories |

(Additional and votive offices follow the Commons once their sources are parsed — see `TODO.md`.)

**Working on this project?** Start with `CLAUDE.md`, then `TODO.md`, `docs/contributing.md`, `docs/architecture.md`.

The book is **generated from a verified database**, never edited by hand. Every text in the source PDFs is extracted
with its page, deduplicated into canonical *objects*, verified, and printed once; everywhere else it is referenced
by page (`\pageref`, so page numbers always stay correct).

## Pipeline

```
sources (8 LH PDFs) → L1 spans → L2 lines → L3 hours/elements → L4 objects → L5 days/hours/slots
                    → L6 verification → L7 reference catalog → L8 book (LuaLaTeX → PDF)
```

| Layer | Code | Output |
|---|---|---|
| L1 extract | `lh/extract/spans.py` | `build/l1/<KEY>.sqlite` (every text line with font/colour, links, outline) |
| L2 lines | `lh/extract/lines.py` | classified visual lines (see `docs/source-pdf-format.md`) |
| L3 parse | `lh/parse/hour.py`, `appendix.py` | hour instances → typed elements with slot codes |
| L4–L5 model | `lh/model/` | `build/lh.sqlite`: `object`, `occurrence`, `day`, `hour_instance`, `psalm*` (+ FTS5 search) |
| L6 verify | `lh/verify/`, `lh/psalter/` | `reports/verification.md`, `reports/psalter_discrepancies.md`, `reports/psalter_coverage.md` |
| L7 catalog | `lh/catalog/` | `reference/index.html` (searchable, links to source PDF pages) |
| L8 book | `lh/render/`, `book/` | `book/out/poc.pdf` |

How the Liturgy of the Hours works, as modelled here: `docs/loth-model.md`.

## Running

Requires Python 3.12 (`py -3.12`) and TeX Live (LuaLaTeX). The eight `LH-*.pdf` files stay in the repo root
(gitignored).

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m lh fetch            # Felix Just tables + Nova Vulgata page → sources/web/ (hashes in sources/manifest.json)
.venv/Scripts/python -m lh all              # build → verify → psalter → export → catalog → book --poc
.venv/Scripts/python -m pytest -q tests     # parser golden tests
```

Individual steps:

```bash
python -m lh build PA LQP ADV:4-1198   # sources: PA = Per annum, LQP = Lent/Easter, ADV:4-1198 = first Advent copy
python -m lh verify                    # round-trip, PDF-index, GILH-structure, psalm consensus, near-duplicates
python -m lh psalter                   # Felix Just cross-check + Nova Vulgata gap fill
python -m lh find ad te orabo          # accent-insensitive search
python -m lh show ant.ad-te-orabo-domine.d967f7
python -m lh hour OT.05.SUN LAUDS      # reassemble an hour from the database
python -m lh catalog                   # reference/index.html
python -m lh book --poc                # book/out/poc.pdf (proof of concept, ~30 s)
python -m lh book                      # book/out/book.pdf: the full book (~8 min) + reports/page_budget.md
```

### Simulating its use

`python -m lh simulate` simulates someone praying every hour of every day of 28 liturgical years from the built
book. It logs each page turn, page-number look-up and ribbon movement, then tries layout and ribbon variants
(an Ordinary card, self-contained Compline, a weekly psalter, …). The results are in `reports/simulation.md`, the
full log in `build/sim/`, and the code in `lh/sim/`.
- **Where texts are:** every text's page is taken from the LaTeX labels of the last `lh book` build, including
  invisible labels at each hour heading.
- **Ribbon models:** the ten ribbons used by section, as the book instructs; used freely (the best case); or not
  used at all.

### Previewing the book as a book

Double-click `preview.bat` (or `preview.bat poc`) to open the built PDF in the browser in the form of a bound book.
- Two-page spreads with page turning.
- The ten ribbons in a bar at the top. Click a ribbon to turn to it. Click it again on its own pages to take it out
  ("loose"). Click a loose ribbon to lay it in the current pages.
- Shift-click a page reference such as `O 675 · P 1673` in an hour heading to lay the matching ribbon there.
- Ribbons on the open spread lie in the gutter, which widens to hold them, so they never cover text.
- The mouse wheel zooms around the pointer; drag to pan; double-click or **F** fits the spread again.
- The sections (PDF bookmarks) on the left, and a page-number box at the bottom.
- A page-edge strip with hover thumbnails.

Ribbon positions are remembered per browser. `tools/viewer/serve.py` serves only `tools/viewer/` and `book/out/*.pdf`
on 127.0.0.1. pdf.js is vendored in `tools/viewer/vendor/pdfjs/`, so the viewer works offline. Keys and rules are
under the **?** button.

The viewer stays light on the 2,800-page book, following SumatraPDF's render cache:
- The PDF is read in byte ranges (HTTP Range), so only the parts for the pages shown are loaded.
- Pages render one at a time from a priority queue: pages on screen first, then the sharp zoom layer, then the
  neighbouring spreads, then the edge thumbnails. Requests for pages you have already turned past are dropped.
- At most 10 rendered pages and 16 thumbnails are kept, and their memory is freed as soon as they are dropped.
- Zooming stretches the page already drawn, then re-renders only the part on screen at full sharpness.

**Online:** <https://azicc4.github.io/One-Volume-Psalter/> serves the same viewer from GitHub Pages.
- **Setup (once):** in the repository's Settings → Pages, set Source to "GitHub Actions".
- **Updates:** `.github/workflows/pages.yml` republishes the viewer whenever `book/out/*.pdf` or `tools/viewer/` changes
  on `main`.
- **Static copy:** `tools/viewer/build_site.py` writes it to `build/site/`, saving as files what `serve.py` would
  answer live.

## Verification

* **Round-trip**: every printed occurrence is rebuilt from its object + occurrence data and compared with the PDF
  text — currently 44,921 / 44,921 exact.
* **PDF index**: parsed days/hours must match each PDF's own index (Per annum: 236 / 236 days).
* **Coverage**: every line of every source PDF is in the database or on a page declared non-content (with a reason)
  in its plug-in `lh/sources/<key>.py` — `reports/coverage_<KEY>.md`. Per annum and Lent/Easter: all lines except 5
  unparsed preces lines each (TODO T-UNP); Advent (first copy): 0 gaps.
* **Structure**: every hour has the slots the GILH requires for it.
* **Consensus**: each psalm verse line is printed many times; divergent printings are listed for review.
* **Felix Just** (catalog of the US LOTH psalter) vs. the Latin LH: every disagreement is reported, none silently fixed.
* Corrections go in `data/overrides/` (with reason and source page; `docs/overrides.md`), never into generated files.

`data/export/*.jsonl` is a committed, diffable snapshot of the database.

## Sources

* Latin *Liturgia Horarum*, editio typica altera — digital edition by J. Diéguez and F. Fernández Labastida from the
  MTF 2010 printing (the eight PDFs).
* Felix Just, S.J., catholic-resources.org/LoH (psalter tables; references only).
* *Nova Vulgata*, vatican.va (psalm verses not used in the LH).
* `data/seed/ordinary_supplement.yaml`: standard Ordinary texts the PDFs only abbreviate (marked as supplement).

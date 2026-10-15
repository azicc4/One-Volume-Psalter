# One-Volume Psalter — instructions for Claude Code sessions

A single-volume Latin *Liturgia Horarum* (English rubrics), generated from a verified database built from eight
source PDFs. Read `README.md` (what and how), `docs/architecture.md` (data model), `docs/contributing.md`
(workflow and gates) and `TODO.md` (the task list) before changing anything.

## The one rule

**The book is generated from the database; the database is generated from the PDFs.** Never hand-edit generated
files: `book/generated/`, `book/out/`, `data/export/`, `reports/`, `reference/`, `build/`. To change content:
- the parser is wrong → fix `lh/parse/`, `lh/extract/` or the source plug-in `lh/sources/<key>.py`;
- the source PDF is wrong → add a reviewed entry in `data/overrides/` (format: `docs/overrides.md`);
- the layout is wrong → fix `book/preamble.tex` or `lh/render/`.
Never silently "fix" a discrepancy: report it in `TODO.md` §3 with the PDF page, and let the project owner decide.

## Commands (run from the repo root)

```bash
.venv/Scripts/python -m lh all            # all eight volumes: build → verify → psalter → export → catalog → book --poc (~2 min)
.venv/Scripts/python -m lh build PA LQP ADV COM SPA SP SQ SADV   # sources (KEY or KEY:firstpage-lastpage)
.venv/Scripts/python -m lh verify PA LQP COM SPA SP SQ SADV   # index checks for those; coverage etc. for all built
.venv/Scripts/python -m pytest -q tests   # parser golden tests + book layout tests
.venv/Scripts/python -m lh book           # full book (book/out/book.pdf + card.pdf, ~5 min) + reports/page_budget.md; --variant weekly; --poc
.venv/Scripts/python -m lh find <words>   # search objects;  lh show <id>;  lh hour OT.05.SUN LAUDS
"preview main.bat" [poc]                   # browser viewer of book/out/book.pdf: spreads, 9 ribbons, the Ordinary card, Main | Experiment (tools/viewer/)
"preview experiment.bat"                   # the same viewer on book-weekly.pdf (lh book --variant weekly; lh/config.py VARIANTS)
.venv/Scripts/python -m lh ribbons        # page arrangement table: each ribbon's page, every hour, next 6 months (also run by lh book)
.venv/Scripts/python -m lh simulate       # simulated readers: page turns + ribbons over 28 years, layout what-ifs -> reports/simulation.md (needs lh book)
```
Source keys: PA (Per annum) · ADV (Advent/Christmas) · LQP (Lent/Easter) · COM (Commons + Office of the Dead) ·
SPA / SADV / SP / SQ (Proper of Saints by season). PDFs live in the repo root (gitignored); `python -m lh fetch`
downloads the web references (Felix Just, Nova Vulgata) into `sources/web/`.

## Environment traps (Windows)

- Use `.venv/Scripts/python` (made from `py -3.12`). Bare `python` on PATH is Inkscape's interpreter.
- LuaLaTeX needs a writable font cache; `lh/render/build_pdf.py` sets `TEXMFCACHE=build/texmf-cache`. If a LaTeX
  build fails with "Undefined control sequence" in the `.aux`, delete `build/latex/poc.aux` (stale macros).
- Fonts are loaded by file name (EB Garamond `.otf` from TeX Live), not by family name.
- Edit code that contains backslashes (regexes, LaTeX) with the Edit/Write tools. Scripted edits through shell
  heredocs have turned `\b` into a backspace and `\f`/`\n` into control characters; check with
  `grep -c $'\x08\|\x0c' <file>`. Long multi-heredoc Bash commands sometimes fail to parse — then nothing ran.

## Picking up work

1. `git fetch && git checkout -b ws/<source>-<topic> origin/main` (or a git worktree per workstream).
2. Claim the item in `TODO.md` (set *Owner* to your branch, status `[~]`), commit that.
3. Work only in the files your item owns (for a source workstream: `lh/sources/<key>.py`, its tests, and parser
   changes behind clearly scoped conditions). Shared core changes (`lh/parse/hour.py`, `lh/model/`) need a note in
   the PR description because other workstreams depend on them.
4. Pass the gates in `docs/contributing.md`, open a PR, link it from `TODO.md`.

## Where things are

| Path | What |
|---|---|
| `lh/extract/` | L1 PDF → lines with style (PyMuPDF); L2 line classification |
| `lh/parse/` | L3 hours and elements (`hour.py`), appendices (`appendix.py`) |
| `lh/sources/` | one plug-in per source PDF: day mapping, non-content pages, duplicate copies |
| `lh/model/` | L4 canonical objects (`canon.py`), DB build (`build.py`, `schema.sql`), overrides, export |
| `lh/verify/` | checks (`checks.py`), coverage (`coverage.py`), report |
| `lh/psalter/` | Felix Just import/compare, Nova Vulgata gap fill, scripture refs |
| `lh/render/` | LaTeX generation (`poc.py`, `latex.py`), PDF build |
| `lh/catalog/` | searchable HTML reference (`reference/index.html`) |
| `docs/` | `loth-model.md` (how the Hours work), `source-pdf-format.md` (parser reference), architecture, contributing, overrides |
| `data/seed/` | hand-made inputs (Felix Just CSV, Ordinary supplement) · `data/overrides/` reviewed corrections · `data/export/` DB snapshot |

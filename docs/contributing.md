# Contributing (people and Claude Code sessions)

## Workflow

1. Pick an open item in `TODO.md`. Claim it: set *Owner* to your branch name and status `[~]`, commit on your branch.
2. Branch from `main`: `ws/<source>-<topic>` for source workstreams (`ws/adv-collapse-copies`), `fix/<topic>`,
   `book/<topic>`, `review/<todo-id>`. Parallel workstreams use one git worktree each.
3. Keep changes inside what your item owns:
   - source workstream → `lh/sources/<key>.py`, tests for that source, parser changes behind source-specific conditions;
   - shared core (`lh/parse/hour.py`, `lh/model/*`, `lh/render/*`) → allowed, but describe the change and its effect on
     the other sources in the PR.
4. Do **not** commit regenerated `data/export/` or `reports/` from a workstream branch; the lead regenerates them after
   merging, which avoids conflicts. (`book/out/poc.pdf` likewise.)
5. Open a PR to `main` using the template below; link it from the `TODO.md` item; set status `[x]` when merged.

## Working in a git worktree

The PDFs, their L1 dumps and the cached web sources are gitignored, so a fresh worktree does not have them. Point the
worktree at the main checkout (read-only use) and reuse its virtualenv:

```bash
export LH_PDF_DIR="<main checkout>"              # the eight LH-*.pdf
export LH_L1_DIR="<main checkout>/build/l1"      # PyMuPDF dumps (all eight already extracted)
export LH_WEB_DIR="<main checkout>/sources/web"  # Felix Just + Nova Vulgata
"<main checkout>/.venv/Scripts/python" -m lh build PA LQP ADV:4-1198 <KEY>   # run from the worktree root
```
Each worktree builds its own `build/lh.sqlite` and `build/latex/`; never write into the shared `build/l1`.

## Verification gates (all must pass before a PR)

```bash
.venv/Scripts/python -m lh build PA LQP ADV:4-1198 <your sources>
.venv/Scripts/python -m lh verify
.venv/Scripts/python -m pytest -q tests
.venv/Scripts/python -m lh book --poc
```

| Gate | Requirement |
|---|---|
| Round-trip | 0 failures (overridden objects are skipped and listed) |
| Coverage | 0 gaps for every source you touched (`reports/coverage_<KEY>.md`); new non-content pages need a reason in the plug-in |
| PDF index | 100 % where the source has an index check |
| Structure | no new failures; any remaining one is explained in `TODO.md` (T-STRUCT) |
| Tests | all pass; a source workstream adds golden tests for ≥ 5 tricky pages (see `docs/source-pdf-format.md`) |
| Book | `lh book --poc` builds with 0 undefined references and 0 missing glyphs |

## PR template

```
## What
<item id(s) from TODO.md and a summary>

## Gates
round-trip: N/N · coverage <KEY>: 0 gaps · index · structure · pytest · book

## Shared-core changes
<files outside your item's scope and why; effect on other sources>

## Findings for review
<source discrepancies found — also added to TODO.md §3 with PDF pages>
```

## Reviewing data discrepancies (TODO.md §3)

Gather evidence (PDF page; `python -m lh show <object>` lists every printing), state a hypothesis (source error /
Felix error / versification difference), and propose an override (`docs/overrides.md`). The project owner decides;
then the override is committed with the decision in its `reason`.

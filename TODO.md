# TODO

The project's shared task list. **Claim an item before starting it**: put your branch name in its *Owner* field,
commit that change on your branch, and set the status. Each item has acceptance criteria; it is done only when they are
met and the verification gates in `docs/contributing.md` pass.

Status: `[ ]` open · `[~]` in progress (owner set) · `[x]` done (link the PR) · `[?]` needs the project owner's decision

Rules that never change (see `CLAUDE.md`): the book is generated from the database; never edit generated files
(`book/generated/`, `data/export/`, `reports/`). Fix the parser, a source plug-in, or add a reviewed override in
`data/overrides/`.

---

## 1. Workstreams — bring every source PDF fully into the database

Order: WS0 first (lead), then WS1–WS5 in parallel (one git worktree + PR each), then WS6, with WS7 ongoing.

| ID | Status | Owner | Scope | Acceptance |
|---|---|---|---|---|
| WS0 | [x] | lead · `feat/lh-database-pipeline` (PR #1) | Per-source plug-ins `lh/sources/<KEY>.py` (day mapping, copy labels, whitelisted non-content pages; stubs for COM/SPA/SADV/SP/SQ); **coverage check** `lh/verify/coverage.py`; overrides mechanism; CLAUDE.md + docs. (`lh build --add` dropped: a full rebuild of the parsed sources takes ~15 s.) | coverage: PA and LQP all lines except T-UNP (5 each), ADV copy 1 = 0 gaps |
| WS1 | [ ] | | **ADV** — Advent/Christmas: collapse the 7 start-date copies (27 Nov … 3 Dec) into one set of objects with copy labels; consensus across copies; Christmas psalter weeks per date; two post-Octave tracks; Immaculate Conception missing from the 1 Dec copy (take from SADV p.65); ADV.1.SUN II Vespers missing Gospel antiphon (T-STRUCT) | coverage 100% of ADV; round-trip 100%; every distinct text present once; tests on ≥5 tricky pages |
| WS2 | [ ] | | **LQP** — Lent/Easter: Triduum, Easter Octave (*Hæc dies*), Ascension dual tracks, Pentecost; T-STRUCT items in LQP; research T-FJ-14 (Easter wk 4 Ps 55/50) | coverage 100%; structure gaps explained or fixed |
| WS3 | [ ] | | **COM** — Commons: 4 seasonal copies → each Common with seasonal variants; sub-variants (*Pro papa, Pro episcopo, Pro virgine…*); Office of the Dead; appendix | coverage 100%; commons keyed `COMMON.<NAME>[.<variant>]` |
| WS4a | [ ] | | **SPA** — Proper of Saints, Ordinary Time: date/title/rank lines; ALTERA sections; Assumption title quirk (SPA 1111); calendar keys/ranks from LitCal; flag post-2010 calendar changes | coverage 100%; every saint mapped to a LitCal key |
| WS4b | [ ] | | **SP, SQ, SADV** — remaining Sanctis files: commemorations in Lent; overlaps across files deduplicated by date | coverage 100%; no saint printed twice |
| WS5 | [~] | `ws/pa-residue` | **PA residue** — Saturday memorial of the BVM office, hymns *ad libitum*, T-UNP | coverage 100% of PA |
| WS6 | [ ] | | **Redundancy engine + full book**: assign each object one home (Ordinary → Psalter → Hymns → Proper of Time → Commons → Saints → Readings); Saints texts equal to a Common become "de Communi" references; generate all sections in book order; page-budget report | full book builds; 0 undefined refs; page budget per section reported |
| WS7 | [ ] | lead + owner | Resolve the review items in §3 via `data/overrides/` with evidence | each item closed with an override or a "no change" note |

## 2. Book and layout

| ID | Status | Owner | Item |
|---|---|---|---|
| B-1 | [x] | lead | 6 × 9.25 in trim; body 10 pt |
| B-2 | [x] | lead | Margin notes stacked (memoir `\marginpar`), never overlapping; other uses (feasts) listed in the margin under the four-week-cycle codes |
| B-3 | [x] | lead | Book order Saints · Commons · Ordinary · Proper of Time · Hymns · Psalter · Readings; 10 ribbons; ribbon pages (O, P, R) at every hour head in the Proper of Time and fixed-part pages at the Ordinary's hour heads; `hour_refs` table |
| B-4 | [x] | lead | Indentation hierarchy in the Proper of Time (hour · slot · variant · condition) |
| B-5 | [x] | lead | Scripture citation beside every reading title (short reading, responsory, readings) |
| B-6 | [x] | lead | Psalter: left-aligned lines, original line breaks, strophe gaps only at couplet starts, psalms may start at a page bottom if heading + one verse fit |
| B-7 | [ ] | | Full Psalter (all 150 psalms) and all canticles, not only those used in the POC |
| B-8 | [ ] | | Invitatory psalms 100, 67, 24 with their refrain marks |
| B-9 | [ ] | | Compact long margin notes (e.g. Ps 118: many feasts repeat the same verse range — print the range once per group) |
| B-10 | [ ] | | Indexes: psalms (Hebrew + Vulgate), canticles, hymns (first lines), saints (by date and name), readings |
| B-11 | [ ] | | Front matter: title page, calendar tables (Easter dates, psalter week per Sunday), how-to-use |
| B-12 | [?] | owner | Page budget: decide after WS6's report whether the Office of Readings readings become a companion volume |
| B-13 | [ ] | | Superscription of Ps 9 prints NV's `*` ("Mut labben *"); render NV titles without pointing marks |

## 3. Data review (needs evidence; resolve via `data/overrides/` or a "no change" note)

### T-FJ — Felix Just psalter vs. Liturgia Horarum (from `reports/psalter_discrepancies.md`)

Felix Just's tables follow the US LOTH (NAB versification); the LH follows the Nova Vulgata. For each row decide:
*source error* (override the DB), *Felix error* (note only), or *versification difference* (note only).

| ID | Status | Week/Day/Hour/Slot | Felix Just | Liturgia Horarum | LH pages (Per annum unless noted) | Hypothesis |
|---|---|---|---|---|---|---|
| T-FJ-1 | [ ] | I Sat Daytime PS1 | Ps 119:333-40 | Ps 119:33-40 | 256, 978… | Felix typo |
| T-FJ-2 | [ ] | I/II/III/IV Sun 2V PS3 | Rev 19:1-7 | Rev 19:1-2, 5-7 | 834, 291, 476, 657… | Felix simplifies; LH omits 3-4 |
| T-FJ-3 | [ ] | I Tue Lauds PS2 | Tob 13:1-8 | Tob 13:2-8 | 152… | versification |
| T-FJ-4 | [ ] | IV Fri Lauds PS2 | Tob 13:8-11, 13-15 | Tob 13:8-11, 13-14ab, 15-16ab | 772… | versification |
| T-FJ-5 | [ ] | I Wed Lauds PS2 | Jdt 16:2-3a, 13-15 | Jdt 16:1-2, 13-15 | 177… | versification (NV vs NAB) |
| T-FJ-6 | [ ] | II Mon Lauds PS2 | Sir 36:1-5, 10-13 | Sir 36:1-7, 13-16 | 306… | versification |
| T-FJ-7 | [ ] | II Thu OR PS3 & IV Thu OR PS3 | Ps 44:18-27 | Ps 44:18-26 | 379, 743… | LH leaves the last couplet (v. 27) unnumbered — source labelling gap |
| T-FJ-8 | [ ] | II Thu Vespers PS1 | Ps 72:2-11 | Ps 72:1-11 | 395… | NV counts the title in v.1 |
| T-FJ-9 | [ ] | IV Sun OR PS2 | Ps 66:2-12 | Ps 66:1-12 | 639… | NV counts the title in v.1 |
| T-FJ-10 | [ ] | IV Wed Daytime PS3 | Ps 94:12-23 | Ps 94:12-24 | 729… | LH typo: a line labelled "24" (Ps 94 has 23 verses) |
| T-FJ-11 | [ ] | IV Fri OR PS1/PS2 | Ps 55:2-10a / 10b-15 | Ps 55:2-9 / 10-15 | 766… | different split point |
| T-FJ-12 | [ ] | III Sun Daytime PS3 | Ps 118:19-29 | 19-29, but 19-22, 24-29 in one printing | p.1190 (vs 471…) | LH drops the "23" label in one week |
| T-FJ-13 | [ ] | letters only (7 rows) | e.g. Exod 15:1-4a | Ex 15, 1-4 b | see report | note only, unless a/b split differs materially |
| T-FJ-14 | [ ] | IV Fri & Sat OR PS1-3 (seasonal) | Ps 78 (Advent/Lent) | Ps 55 / Ps 50 in Easter week 4 | LQP 1877-1878, 1903-1904 | GILH 130 reserves Ps 78 for seasons; check whether Easter uses the per annum psalms here |
| T-FJ-15 | [ ] | Ps 72:20 | omitted | not printed; also absent from vatican.va NV page | — | note only |

### Other review queues

| ID | Status | Owner | Item | Where |
|---|---|---|---|---|
| T-CONS | [ ] | | 38 psalm lines whose printings disagree (e.g. Ps 88:16-17 lacks `*` in 8 of 42 printings; Ps 55:17-18 comma; Ps 126:5 mis-numbered once). Majority reading is used meanwhile | `reports/verification.md` → "Psalm lines with divergent readings" |
| T-DUP | [ ] | | 443 near-duplicate object pairs (punctuation variants, intonation daggers, genuinely different texts). Triage: merge via override, or mark distinct | `reports/verification.md` → "Near-duplicate objects"; catalog flags them "review" |
| T-STRUCT | [ ] | WS1/WS2 | 10 seasonal hours missing GILH slots: EAS.1.SUN OR (Easter Vigil replaces it — template exception), EAS.2.THU & EAS.5.SUN Daytime versicles, SOL.ASCENSION V1/OR conclusion, ADV.1.SUN II Vespers Gospel antiphon, SOL.IMMACULATE_CONCEPTION V1/V2 PS3 & Lauds conclusion, FEAST.BAPTISM V1 opening. (EAS.7.FRI Vespers preces: fixed with T-UNP.) MEM.BVM_SATURDAY passes: its psalmody, versicle and first reading are "de sabbato currente" (rubric, PA 6271/6274), its second reading is given by `LECT2` links | `python -m lh verify` |
| T-UNP | [~] | `ws/pa-residue` | Unparsed preces second halves ("— …" lines) where something interrupts the PRECES section: 5 in the Saturday BVM office (PA 6278), 5 in Easter wk 7 Friday Vespers (LQP 2522; also causes the EAS.7.FRI PRECES structure gap). Fixed: a text block containing "— …" lines is parsed as preces wherever it occurs (PA 6277 "Vel aliæ:" → second PRECES with `cond.alt`; LQP 2522 preces printed without their label) | `reports/coverage_PA.md`, `coverage_LQP.md` |
| T-PA-1 | [ ] | | LQP 2522 (EAS.7.FRI Vespers): the PRECES label is missing in the source — the preces follow the repeated Magnificat antiphon directly. Parsed as PRECES anyway; note only (no override needed) | LQP 2522 |
| T-PA-2 | [ ] | | PA 6267–6268: the hymns *Salve dies* and *Dies ætásque* (Sunday I Vespers ad libitum, weeks II–XXXIII) are printed without a heading, after *Peccatrícem qui* inside the Vespers of "Hymni ad libitum dicendi in feriis hebdomadæ XXXIV". In the DB they are hymns of `PROP.HYMNS_AD_LIBITUM` VESPERS; the weeks reach them through `HYMN_ALT` links (`link_target`). WS6: print them as Sunday I Vespers alternatives, not as week XXXIV hymns | PA 6264–6268 |
| T-PA-3 | [ ] | | BVM on Saturday: the rubrics announcing the extra second readings differ in punctuation between the Office of Readings and the reading appendix ("…Beatæ Mariæ Virginis," / "aut de die 16 iulii." at PA 6272 vs "…Virginis:" / "…iulii:" at PA 6288–6289) → two rubric objects each. Note only | PA 6272, 6288–6289 |
| T-PA-4 | [ ] | | Parser: a reading's source citation set as a non-centred red line ("(Sermo 1 in Assumptione…)", PA 6281; "(Cap. 1: Opera omnia…)" in ADV/LQP) goes to the reading body instead of `meta`, so some reading ids read `lec.cap-1-opera-omnia…`. A one-line fix in `parse_reading` (treat a red line starting with "(" before the body as meta) changes 26 reading objects (28 printings) in ADV/LQP/PA — left out of the WS5 shared-core diff for WS1/WS2/WS6 to coordinate | `lh/parse/hour.py` `parse_reading` |
| T-PA-5 | [ ] | | Links target pages only (the PDFs store no position), so `link_target` rows with how = `page` are approximate: e.g. "Memoria ad libitum Sanctæ Mariæ" after the psalmody of OT Saturday Lauds (PA 253 → 6274) means the BVM short reading but resolves to the first element on 6274 (hymn *Ave, maris stella*); the hour (`hour_id`) is right. Ps 94 without refrains (PA 6262, target of "Quando sequens psalmus…") sits in the `ORD.MARIAN` chapter | `link_target` |
| T-SUPP | [ ] | | Verify `data/seed/ordinary_supplement.yaml` (Pater noster, full opening verses, prayer conclusions) against a printed *Ordinarium* | seed file |
| T-NV | [ ] | | Nova Vulgata gap verses have no accents or pointing; add them (or accept unaccented small type) | `psalm_verse.source = 'NV'` |

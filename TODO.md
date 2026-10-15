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
| WS1 | [x] | `ws/adv-full-volume` (merged PR #8 https://github.com/azicc4/One-Volume-Psalter/pull/8) | **ADV** — Advent/Christmas: collapse the 7 start-date copies (27 Nov … 3 Dec) into one set of objects with copy labels; consensus across copies; Christmas psalter weeks per date; two post-Octave tracks; Immaculate Conception missing from the 1 Dec copy (take from SADV p.65); ADV.1.SUN II Vespers missing Gospel antiphon (T-STRUCT) | coverage 100% of ADV; round-trip 100%; every distinct text present once; tests on ≥5 tricky pages |
| WS2 | [x] | `ws/lqp-complete` (merged PR #4 https://github.com/azicc4/One-Volume-Psalter/pull/4) | **LQP** — Lent/Easter: Triduum, Easter Octave (*Hæc dies*), Ascension dual tracks, Pentecost; T-STRUCT items in LQP; research T-FJ-14 (Easter wk 4 Ps 55/50) | coverage 100%; structure gaps explained or fixed |
| WS3 | [x] | `ws/com-commons` (merged PR #7 https://github.com/azicc4/One-Volume-Psalter/pull/7) | **COM** — Commons: 4 seasonal copies → each Common with seasonal variants; sub-variants (*Pro papa, Pro episcopo, Pro virgine…*); Office of the Dead; appendix | coverage 100%; commons keyed `COMMON.<NAME>[.<variant>]` |
| WS4a | [x] | `ws/spa-saints` (merged PR #6 https://github.com/azicc4/One-Volume-Psalter/pull/6) | **SPA** — Proper of Saints, Ordinary Time: date/title/rank lines; ALTERA sections; Assumption title quirk (SPA 1111); calendar keys/ranks from LitCal; flag post-2010 calendar changes | coverage 100%; every saint mapped to a LitCal key |
| WS4b | [x] | `ws/sanctis-seasons` (merged PR #5 https://github.com/azicc4/One-Volume-Psalter/pull/5) | **SP, SQ, SADV** — remaining Sanctis files: commemorations in Lent; overlaps across files deduplicated by date | coverage 100%; no saint printed twice |
| WS5 | [x] | `ws/pa-residue` (merged PR #3 https://github.com/azicc4/One-Volume-Psalter/pull/3) | **PA residue** — Saturday memorial of the BVM office, hymns *ad libitum*, T-UNP | coverage 100% of PA |
| WS6 | [~] | `ws/full-book` (PR #11 https://github.com/azicc4/One-Volume-Psalter/pull/11) | **Redundancy engine + full book**: assign each object one home (Ordinary → Psalter → Hymns → Proper of Time → Commons → Saints → Readings); Saints texts equal to a Common become "de Communi" references; generate all sections in book order; page-budget report | full book builds; 0 undefined refs; page budget per section reported |
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
| B-7 | [x] | `ws/full-book` | Full Psalter (all 150 psalms) and all canticles, not only those used in the POC (full book: 150 psalms with margin uses; canticles grouped by reference, printing variants labelled at the consensus text) |
| B-8 | [x] | `ws/full-book` | Invitatory psalms 100, 67, 24 with their refrain marks (full book: Ordinary, Invitatory — Pss 95, 100, 67, 24 as printed in PA's *Ad Invitatorium*) |
| B-9 | [ ] | | Compact long margin notes (e.g. Ps 118: many feasts repeat the same verse range — print the range once per group). Full book meanwhile: Commons/Saints/Dead uses collapse to one code per hour ("Saints L.1"), and "other uses" are capped at 10 lines ("+ N more") |
| B-10 | [~] | `ws/full-book` | Indexes: psalms (Hebrew + Vulgate), canticles, hymns (first lines), saints (by date and name), readings. **Done in the full book except the readings index** |
| B-11 | [ ] | | Front matter: title page, calendar tables (Easter dates, psalter week per Sunday), how-to-use |
| B-12 | [?] | owner | Page budget: decide after WS6's report whether the Office of Readings readings become a companion volume — see `reports/page_budget.md` (WS6) |
| B-13 | [ ] | | Superscription of Ps 9 prints NV's `*` ("Mut labben *"); render NV titles without pointing marks |
| B-14 | [x] | `book/card-compline-ribbons` | **Ordinary card** (`book/out/card.pdf`, `lh/render/card.py`): two cards 5.5 × 8.5 in printed on both sides — Invitatory and Ps 95, opening verses, Benedictus, Magnificat, Nunc dimittis, Pater noster, prayer endings, dismissals, blessing, Te Deum, Marian antiphons; built after the book (`lh book`, or `lh book --card`) |
| B-15 | [x] | `book/card-compline-ribbons` | **Compline printed whole**: each weekly form and the Easter Octave print their psalms, hymns, shared responsory and Nunc dimittis in full (copies labelled `cp:`); +24 pages |
| B-16 | [x] | `book/card-compline-ribbons` | **Ribbons by use** ("Finding the Office", hour headings, viewer): 1 Saints, 2 Commons, 3 Ordinary (Compline, Daytime Prayer), 4–6 Proper of Time (the hour, where it continues, the week), 7 Hymns, 8–9 Psalter and Canticles, 10 Readings — 19.7 look-ups a day against 22.4 by section (`reports/simulation.md`) |
| B-17 | [~] | `exp/weekly-psalter` | Experiment: psalms and hymns of the four-week cycle printed at each hour (as the four-volume breviary), in addition to the Psalter in biblical order — measured on its branch |
| B-18 | [?] | owner | Proposal (`reports/simulation.md`): **psalmody blocks** — the Psalter in the order of the four-week cycle with each hour's antiphons beside its psalms; psalms the cycle does not use follow in biblical order; index by number. No text added; ~15 % less handling |
| B-19 | [?] | owner | Proposal: **thumb-index tabs** on the fore-edge for the seven parts (bleed tabs in the page style); no pages, faster look-ups |

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
| T-FJ-14 | [?] | IV Fri & Sat OR PS1-3 (seasonal) | Ps 78 (Advent/Lent) | Ps 55 / Ps 50 in Easter week 4 | LQP 1877-1878, 1903-1904 | **WS2 finding: source error in LQP.** GILH 130 reserves Ps 77 (78), 104 (105), 105 (106) for "Advent, Christmas, Lent and Eastertide", and LQP itself applies this elsewhere in Eastertide (Ps 105 on EAS.5.SAT p.2085; Ps 106 on EAS.2.SAT p.1537 and EAS.6.SAT pp.2268/2347, replacing the per annum Ps 131-132/136). On EAS.4.FRI/SAT the **antiphons are those of Ps 78** (Easter forms with alleluia): Fri *Patres nostri narravérunt…*, *Fílii Israel manducavérunt manna…*, *Rememoráti sunt quia Deus adiútor…*; Sat *Redémit eos Dóminus de manu tribulántis*, *Indúxit eos Dóminus in montem sanctificatiónis suæ*, *Elégit tribum Iuda…* — identical (bar alleluia) to LENT.4.FRI/SAT (pp.773-775, 799-801) and ADV.DEC23/24 (ADV 669-672, 696-698), which print Ps 78:1-39 / 40-72. But the psalm bodies printed under them are the per annum Ps 54 (55) and 49 (50) (= OT.04.FRI/SAT, PA 765-767, 791-792, whose antiphons are different). No rubric on those pages. Proposal: override EAS.4.FRI OR PS1-3 → Ps 78:1-16 / 17-31 / 32-39 and EAS.4.SAT → 40-51 / 52-64 / 65-72 (objects as printed at LQP 773-775, 799-801); Felix Just's "Advent/Lent" label then also covers Easter. Data not changed — owner to decide. |
| T-FJ-15 | [ ] | Ps 72:20 | omitted | not printed; also absent from vatican.va NV page | — | note only |

### Other review queues

| ID | Status | Owner | Item | Where |
|---|---|---|---|---|
| T-CONS | [ ] | | 77 psalm lines (all eight volumes) whose printings disagree (e.g. Ps 88:16-17 lacks `*` in 8 of 42 printings; Ps 55:17-18 comma; Ps 126:5 mis-numbered once). Majority reading is used meanwhile. With all sources (PA LQP ADV COM SPA SP SQ SADV) in the build: 77 lines (T-SPA-8, T-COM-4) | `reports/verification.md` → "Psalm lines with divergent readings" |
| T-DUP | [ ] | | 1,153 near-duplicate object pairs (punctuation variants, intonation daggers, genuinely different texts). Triage: merge via override, or mark distinct | `reports/verification.md` → "Near-duplicate objects"; catalog flags them "review" |
| T-STRUCT | [x] | WS1/WS2 | Seasonal hours missing GILH slots. **LQP done (`ws/lqp-complete`)**: EAS.1.SUN OR = Easter Vigil, parsed as LECT1-4 + chants + prayers + Te Deum and checked against a template exception (GILH 212, `lh/verify/checks.py` TEMPLATE_EXCEPTIONS); EAS.2.THU Daytime: parser infers the missing "Ad Tertiam" header (LQP 1500); EAS.5.SUN Daytime None versicle and SOL.ASCENSION V1 opening/conclusion + OR conclusion are source omissions, excused in `lh/sources/lqp.py` STRUCTURE_EXCEPTIONS (GILH 79 / 41, 54 / 69; T-LQP-1, T-LQP-2); EAS.7.FRI Vespers preces: fixed with T-UNP. **ADV done (`ws/adv-full-volume`)**: ADV.1.SUN II Vespers Gospel antiphon = Year A/B/C antiphons printed without "Ant." (ADV 37), now parsed (`nolabel`); SOL.IMMACULATE_CONCEPTION V1/V2 PS3 = one-line heading "Canticum Eph 1, 3-10" (ADV 286), now parsed; Immaculate Conception Lauds conclusion, FEAST.BAPTISM V1 opening, four Christmas Daytime conclusions and the truncated 7 Jan Vespers (1 Dec copy) are source omissions excused in `lh/sources/adv.py` STRUCTURE_EXCEPTIONS (T-ADV-4/5/6). MEM.BVM_SATURDAY passes: its psalmody, versicle and first reading are "de sabbato currente" (rubric, PA 6271/6274), its second reading is given by `LECT2` links. **SPA (`ws/spa-saints`)**: Proper of Saints hours are checked against rank templates (`RANK_REQUIRED` in `lh/verify/checks.py`: memorials print no psalmody/OR versicle/first reading — "de feria", GILH 234-236; feasts take the weekday psalms at Daytime Prayer, GILH 231-233); the 10 remaining SPA gaps are source omissions excused in `lh/sources/spa.py` (T-SPA-2) | `python -m lh verify` |
| T-UNP | [x] | `ws/pa-residue` (merged PR #3 https://github.com/azicc4/One-Volume-Psalter/pull/3) | Unparsed preces second halves ("— …" lines) where something interrupts the PRECES section: 5 in the Saturday BVM office (PA 6278), 5 in Easter wk 7 Friday Vespers (LQP 2522; also causes the EAS.7.FRI PRECES structure gap). Fixed: a text block containing "— …" lines is parsed as preces wherever it occurs (PA 6277 "Vel aliæ:" → second PRECES with `cond.alt`; LQP 2522 preces printed without their label) | `reports/coverage_PA.md`, `coverage_LQP.md` |
| T-COPIES | [~] | WS6 | `reports/lqp_copies.md`: 9 of 10 hours printed on both Ascension tracks differ (expected where the tracks really diverge — check each); `reports/adv_copies.md` / `com_copies.md`: review the remaining explained differences before choosing printed texts | reports — **WS6:** the full book prints the first printing and, under each slot, every other printing whose texts differ, labelled ("Advent from 28 Nov; Epiphany on Sunday", "Ascension on Sunday", "Eastertide", "Alternative office (Virgo)", "Commemoration"); review of the differences themselves still open |
| T-PA-1 | [ ] | | LQP 2522 (EAS.7.FRI Vespers): the PRECES label is missing in the source — the preces follow the repeated Magnificat antiphon directly. Parsed as PRECES anyway; note only (no override needed) | LQP 2522 |
| T-PA-2 | [x] | | PA 6267–6268: the hymns *Salve dies* and *Dies ætásque* (Sunday I Vespers ad libitum, weeks II–XXXIII) are printed without a heading, after *Peccatrícem qui* inside the Vespers of "Hymni ad libitum dicendi in feriis hebdomadæ XXXIV". In the DB they are hymns of `PROP.HYMNS_AD_LIBITUM` VESPERS; the weeks reach them through `HYMN_ALT` links (`link_target`). WS6: print them as Sunday I Vespers alternatives, not as week XXXIV hymns | PA 6264–6268 — **WS6:** done: the grid's Sunday First Vespers lists them as *Ad libitum* hymns (from the `HYMN_ALT` link targets) and the Hymns section prints them under "Hymns ad libitum" with the rubric |
| T-PA-3 | [ ] | | BVM on Saturday: the rubrics announcing the extra second readings differ in punctuation between the Office of Readings and the reading appendix ("…Beatæ Mariæ Virginis," / "aut de die 16 iulii." at PA 6272 vs "…Virginis:" / "…iulii:" at PA 6288–6289) → two rubric objects each. Note only | PA 6272, 6288–6289 |
| T-PA-4 | [ ] | | Parser: a reading's source citation set as a non-centred red line ("(Sermo 1 in Assumptione…)", PA 6281; "(Cap. 1: Opera omnia…)" in ADV/LQP) goes to the reading body instead of `meta`, so some reading ids read `lec.cap-1-opera-omnia…`. A one-line fix in `parse_reading` (treat a red line starting with "(" before the body as meta) changes 26 reading objects (28 printings) in ADV/LQP/PA — left out of the WS5 shared-core diff for WS1/WS2/WS6 to coordinate | `lh/parse/hour.py` `parse_reading` |
| T-PA-5 | [ ] | | Links target pages only (the PDFs store no position), so `link_target` rows with how = `page` are approximate: e.g. "Memoria ad libitum Sanctæ Mariæ" after the psalmody of OT Saturday Lauds (PA 253 → 6274) means the BVM short reading but resolves to the first element on 6274 (hymn *Ave, maris stella*); the hour (`hour_id`) is right. Ps 94 without refrains (PA 6262, target of "Quando sequens psalmus…") sits in the `ORD.MARIAN` chapter | `link_target` |
| T-SUPP | [ ] | | Verify `data/seed/ordinary_supplement.yaml` (Pater noster, full opening verses, prayer conclusions) against a printed *Ordinarium* | seed file |
| T-NV | [ ] | | Nova Vulgata gap verses have no accents or pointing; add them (or accept unaccented small type) | `psalm_verse.source = 'NV'` |

### T-LQP — source discrepancies in LH-Quadragesimae_et_Paschae.pdf (found by WS2)

Overrides cannot add missing occurrences; the structure check excuses these via `lh/sources/lqp.py`
STRUCTURE_EXCEPTIONS until the owner decides (e.g. the book supplies the element from the Ordinary / another printing).

| ID | Status | Item | LQP pages | Evidence / proposal |
|---|---|---|---|---|
| T-LQP-1 | [?] | Ascension: I Vespers prints no opening verse, no PSALMODIA label and no "Conclusio Horæ" link; the Office of Readings has no "Conclusio Horæ" link | 2286, 2290, 2301 | Every other I Vespers (e.g. Pentecost 2544-2548) and OR prints them (GILH 41, 54, 69). Propose: book supplies the standard opening/conclusion; no data change |
| T-LQP-2 | [?] | EAS.5.SUN Hora media: None has no versicle after its short reading | 1946 | All other Easter Sundays print ℣. *Mane nobíscum, Dómine, allelúia.* ℟. *Quóniam advesperáscit, allelúia.* at None (e.g. EAS.4.SUN, EAS.6.SUN). Propose: supply that versicle (`vr.mane-nobiscum-domine-alleluia.2128a3`) |
| T-LQP-3 | [?] | EAS.2.THU Hora media: the "Ad Tertiam" sub-header before Terce's short reading is missing | 1500 | Parser infers Terce (`HourParser.infer_terce`); note only |
| T-LQP-4 | [ ] | Punctuation variants in the RB antiphons: *Hæc dies … allelúia* without final full stop at every Compline (1217-1403, 2611-2614) vs with it at Lauds/Vespers; *Christus factus est … exaltávit illum, et dedit* (Sat Lauds 1174) vs *illum et dedit* (Sat Vespers/Compline 1185, 1189) | see pages | Part of T-DUP; propose merge to the majority reading |
| T-LQP-5 | [?] | EAS.4.FRI/SAT Office of Readings: Ps 78 antiphons over Ps 55 / Ps 50 bodies | 1877-1878, 1903-1904 | See T-FJ-14 |

### T-ADV — source discrepancies in LH-Adventus_et_Nativitatis.pdf (found by WS1)

The seven start-date copies are compared day/hour by day/hour in `reports/adv_copies.md` (`lh/verify/copies.py`);
every difference that is not a calendar difference is listed here. Structure gaps that are source omissions are excused
in `lh/sources/adv.py` STRUCTURE_EXCEPTIONS; cross-copy differences are annotated in its COPY_NOTES / CALENDAR_NOTES.

| ID | Status | Item | ADV pages | Evidence / proposal |
|---|---|---|---|---|
| T-ADV-1 | [?] | Immaculate Conception missing from the 1 Dec copy: 8 Dec is the Second Sunday of Advent, so the solemnity moves to Monday 9 Dec, where the copy prints *Feria II hebdomadæ II Adventus* instead | 5216 (copy 5003-6273) | SADV 65-96 prints the office under the same key `SOL.IMMACULATE_CONCEPTION` (T-SANCT-9), so the day is in the database when SADV is built. Propose: book uses that office for 9 Dec in a 1 Dec year; keep ADV.2.MON for the case it is not transferred. SADV vs ADV: identical except Compline (SADV adds an alternative oration) and II Vespers (T-ADV-11) |
| T-ADV-2 | [?] | 28 Nov copy, Epiphany-on-6-Jan track: the first two weekdays after Epiphany (7, 8 Jan) print the *pre*-Epiphany invitatory *Christus natus est nobis* | 2383, 2409 | Every other printing of these days has *Christus appáruit nobis* (e.g. 1118, 2233, 3626). Propose override: replace by `ant.christus-apparuit-nobis-venite.0144da` |
| T-ADV-3 | [?] | 28 Nov copy, Epiphany-Sunday track, Tuesday 4 Jan (= 2nd weekday after Epiphany, texts of 8 Jan): Vespers short reading is that of 27 Dec Vespers (*Deus Fílium suum mittens…*) | 2279 | All other printings of the day (3522, 3672, 4766, 4918, 6014, 6163, 7258) read *Erámus natúra fílii iræ…* (`lb.eramus-natura-filii-irae.e5d534`). Propose override |
| T-ADV-4 | [?] | 1 Dec copy, Epiphany-on-6-Jan track, 7 Jan (Tuesday) Vespers breaks off after the psalmody: no short reading, responsory, Magnificat, preces, Pater noster, oration | 6135-6138 | The other printings of the day are complete (Vespers at 2250, 2400, 3493, 3644, 4737, 4888, 5985, 7229). Propose: book takes the missing parts from them (same day key `CHR.POSTEPI.JAN07`); structure check excused |
| T-ADV-5 | [?] | Missing *Conclusio Horæ, ut in Ordinario.*: Lauds of the Immaculate Conception (all six printings); Daytime Prayer at the Christmas-track branch points, where a navigation link ("Sollemnitas Epiphaniae Domini (in regionibus…)", "Festum Baptismatis Domini") replaces it or nothing is printed | 304, 1474, 2713, 3957, 6447, 7545; 3361, 3439, 3625, 8297 | GILH 54/79; SADV's Immaculate Conception Lauds has the link. Propose: book prints the standard conclusion; no data change (excused) |
| T-ADV-6 | [?] | I Vespers of the Baptism of the Lord prints no opening verse *Deus, in adiutórium* (all six copies that have I Vespers) | 1137, 2428, 3697, 4968, 6239, 7362 | GILH 41. Propose: book supplies the opening (as T-LQP-1); excused |
| T-ADV-7 | [?] | Compline after I Vespers of the Second Sunday after the Nativity is subtitled *POST II VESPERAS DOMINICÆ…* (content: Saturday Compline, Ps 4 + 133), so it is coded COMPLINE, not COMPLINE1; a stray *Conclusio Horæ* link follows a Compline | 3367, 4637, 5910; 3396 | The 28 Nov copy has no such Compline. Propose: an hour-code override (COMPLINE1) once the override mechanism supports it |
| T-ADV-8 | [?] | Typo in *Te lucis*: *saumalo lúbrem* for *salúbrem* (Friday Compline, Week I of Advent, 1 Dec copy) | 5160 | 357 other printings read *Vitam salúbrem tríbue*. Propose override → `hym.te-lucis-ante-terminum.4b5024` |
| T-ADV-9 | [?] | Cross-copy variants: 21 Dec Daytime Prayer oration ends *Per Dóminum.* (28 Nov) vs *Per Christum.* (others); 24 Dec invitatory *véniet Dóminus, et mane* (695, 1864, 7941) vs *véniet Dóminus: et mane* (3106, 4350, 5599, 6846); 22 Dec Office of Readings reference *1, 46-55* (647) vs *1,46-55* | 1804; 695…; 647 | Short conclusion is right for Daytime Prayer (cf. GILH 197); punctuation: majority reading. Part of T-DUP |
| T-ADV-10 | [?] | Layout/index omissions: Office of Readings oration printed without its *Oratio* heading (parsed as text); *Ad Tertiam* heading missing before the Terce hymn; copy indexes label the 2nd weekday after Epiphany *Die 7 ianuarii* twice (29 Nov, 30 Nov, 1 Dec indexes); the 27 Nov index links the Epiphany-Sunday Baptism to the Sunday printing (1137) instead of the Monday printing (1172-1198), and the 28 Nov index omits *1v cp* for that Baptism | 7217; 2422; 2463-2464, 3732-3733, 5003-5004; 5; 1200 | Note only (indexes are not printed in the book) |
| T-ADV-11 | [?] | Immaculate Conception II Vespers in every ADV copy: the short responsory's versicle lacks its ℣ sign, and Eph 1, 3-10 is printed without its title *De Deo salvatore* and with verse 8 run into the line above | 310, 1480, 2719, 3963, 7551; 309… | SADV 91 prints ℣. and the title. Propose: take the SADV printing (T-ADV-1) as the text of this hour |

### T-SANCT — source discrepancies in the seasonal Sanctis volumes SP / SQ / SADV (found by WS4b)

Pages: SP = LH-Sanctis-Paschae, SQ = LH-Sanctis-Quadragesimae, SA = LH-Sanctis-Adventus_et_Nativitatis. Omissions
are excused in the structure check by the plug-ins' STRUCTURE_EXCEPTIONS until the owner decides; cross-volume text
differences come from `reports/sanctis_overlaps.md` (all four volumes from the database since WS4a; day keys are now LitCal keys, e.g. `SANCT.02-05.StAgatha`).

| ID | Status | Item | Pages | Evidence / proposal |
|---|---|---|---|---|
| T-SANCT-1 | [?] | Vespers without the "Conclusio Horæ, ut in Ordinario." link: St George, St Fidelis, St Peter Chanel; St Lucy | SP 146, 164, 194; SA 133 | Every other Vespers of the volumes prints it (GILH 54); St Lucy's ALTERA printing (SA 202) has it. Propose: book supplies the standard conclusion; no data change |
| T-SANCT-2 | [?] | St Gregory VII Vespers prints "Hora media de feria currente." where the psalmody rubric "Antiphonæ et psalmi de feria currente." belongs (the Hora media rubric is also, correctly, at the end of Lauds) | SP 360 | Copy error in the source. Propose: override the rubric text to "Antiphonæ et psalmi de feria currente." |
| T-SANCT-3 | [?] | Cyril and Methodius, ALTERA (feast) Lauds: the hymn *Hi sacerdótes Dómini sacráti* is printed without its HYMNUS label (also SPA 259, 2067, 2357, T-SPA-3) | SQ 153 | **Parser now recovers it as the hymn** (`HourParser.missing_label`, `ws/spa-saints`); SQ structure exception removed. Note only |
| T-SANCT-4 | [?] | The volumes' own indexes: SP index lists St Barnabas as "OL LD VP" but the feast prints a Hora media; SA index lists the Holy Name as "LD VP" but it also prints an Office of Readings reading; title typos "S. Francisca Romana" (printed FRANCISCÆ ROMANÆ) and "S. Thomas Becket" (printed THOMÆ) | SP 9 vs 477-480; SA 7 vs 180-181; SQ 5 vs 58; SA 6 vs 165 | Index only (not printed in the book). Recorded as INDEX_ERRATA / `index_title` notes. Note only |
| T-SANCT-5 | [?] | Sts Charles Lwanga and companions, OR responsory: the versicle is printed with ℟ instead of ℣ (two ℟ lines); SPA prints ℣ | SP 432 (SPA 528) | Propose: override the responsory's second pair to V |
| T-SANCT-6 | [?] | St Barnabas Vespers preces: "da, ut omni creatúræ Evangélium prædicémus" (SP) vs "prædicétur" (SPA); "constituísti," vs "constituísti" | SP 485, SPA 574 | Check the editio typica; propose the SPA reading (*prædicétur*, matching "nuntiétur" in the same petition) |
| T-SANCT-7 | [?] | St Scholastica Vespers antiphon *Veni, sponsa Christi … præparávit* (SQ) vs *præparábit* (SPA) | SQ 18, SPA 243 | The Common of Virgins reads *præparávit*; propose override of the SPA text (WS4a) |
| T-SANCT-8 | [?] | Different Gospel antiphons for the same saint in two volumes (both plausible; not alleluia-only): St Josephine Bakhita Vespers (SQ *Veni, sponsa Christi* vs SPA *In una hóstia dúplicem…*), St John of God Lauds and Vespers (SQ 57 vs SPA 335/337), St Vincent Ferrer Vespers (SQ *Omnibus ómnia factus sum* vs SP *Iste est fidélis…*) | SQ 16, 57, 139; SPA 235, 335, 337; SP 100 | The commemoration (SQ) may take a different Common antiphon; owner to decide whether one book text serves both seasons |
| T-SANCT-9 | [ ] | Immaculate Conception: SA 65-96 prints the whole solemnity (keyed `SOL.IMMACULATE_CONCEPTION`, like ADV). The SADV printing passes the structure check where ADV's copy fails (V1/V2 PS3, Lauds conclusion: ADV 284, 298, 307) — WS1 can take the 1 Dec copy's missing day and the missing slots from it | SA 65-96 | WS1: the V1/V2 PS3 gaps were an ADV parser issue (fixed); the Lauds conclusion is an ADV omission (T-ADV-5); the 1 Dec gap is documented as supplied by SADV (T-ADV-1, `lh build … ADV SADV`) |
| T-SANCT-10 | [ ] | Parser refinements enabled for the Sanctis volumes only (SPA/SP/SQ/SADV, COM since WS3, ADV since WS1; `lh/parse/hour.py` SANCTIS_SOURCES; SPA added by WS4a, which also uses it for "vel:" / "Extra ipsam Basilicam Lateranensem:" + second oratio): inline "Vel: <antiphon>" alternatives (LQP 39×, PA 1× print the same pattern and currently get a rubric + TEXT), "Vel, si … dominica:" alternative prayers (PA 2×, ADV 2×), antiphons continued across a block/page break | — | WS1/WS2/WS6: opt in by adding the source key |

### T-COM — source discrepancies in LH-Communia.pdf (found by WS3)

Pages are LH-Communia.pdf pages; copies ADV 4–416, LENT 417–817, EAS 818–1207, OT 1208–1640. Omissions are excused in
the structure check by `lh/sources/com.py` STRUCTURE_EXCEPTIONS; differences between the four copies are listed in full
in `reports/com_copies.md` (regenerate with `python -m lh.sources.com`).

| ID | Status | Item | Pages | Evidence / proposal |
|---|---|---|---|---|
| T-COM-1 | [?] | Ordinary formulas not printed: Common of Doctors Lauds ends without "Conclusio Horæ, ut in Ordinario." (all four copies); Common of Doctors Hora media has no opening "℣. Deus, in adiutórium" (ADV, LENT, OT copies; the EAS copy has it); Saturday BVM Lauds ends without "Conclusio Horæ" (PA 6279 has it) | 260, 666, 1061, 1484; 260, 666, 1484; 1304 | Every other Common prints them (GILH 41, 54). Propose: the book supplies the standard opening/conclusion; no data change |
| T-COM-2 | [?] | Layout only: in Compline after II Vespers the second half-line of v. 1 of Ps 90 (91) ("sub umbra Omnipoténtis commorábitur.") and of the Nunc dimittis ("secúndum verbum tuum in pace,") is set flush-left instead of indented, in the ADV, LENT and OT copies of every Common → objects `ps.091.1-16.e904` (30 printings) and `cant.lc2_29-32.94b1` (70) besides the usual `…3fff` / `…fb46`. Also the Virgins' short reading citation "(1 Cor 7, 32 b. 34 a)" (ADV, OT) vs "(1 Cor 7, 32b.34a)" (LENT, EAS) | e.g. 40, 451, 1244 (Ps 90); 41, 453, 1245; 276, 681, 1076, 1500 | The EAS copy and every other volume indent the line. Propose: override merging the two objects into the common one (no text change) |
| T-COM-3 | [?] | Texts printed in some copies only: (a) BVM II Vespers preces: alternative response "Vel: Plenam grátia intuére (,) et exáudi nos." only in the OT copy (both preces sets); (b) Common of Several Martyrs, Office of Readings: the reading for a prolonged vigil ("Ubi vigilia protrahitur:", Sap 5, 1-15 + responsory) only in the ADV and LENT copies | (a) 1283 vs 76, 486-487, 887; (b) 128, 537 vs 935, 1350-1351 | (a) I Vespers prints the alternative in every copy (47, 459, 859, 1251): likely dropped in three copies — propose the book prints it once. (b) Rubric-level option; propose the book prints it once in the Common |
| T-COM-4 | [ ] | Psalm text: 34 psalm lines printed in the Commons / Office of the Dead read differently from every other printing (psalm consensus 38 → 72 divergent lines): mostly no comma before the mediant `*` or flex `†` (Ps 19:2-3, 6-7; 40:2, 6, 13; 51:5, 9, 10, 15, 17; 85:12-13; 86:9, 14; 113:4; 117:2; 118:1, 28; 147:20; 149:4; 130:7; 121:6), Ps 2:10 "intellégite;" (";" for ","), Ps 11:1 "sicut passer?" (others "!"), Ps 11:3 printed as one line "evertúntur,* iustus quid fáciat?»."; Ps 147:17 and 130:5 broken at a different place | 43, 91, 135, 153-154, 164-165, 284, 1643-1667 (and the same places in the other copies) | The consensus check keeps the majority reading. Owner: accept as punctuation variants (no change) or override the minority printings |
| T-COM-5 | [~] | Parser notes for other workstreams: (a) an antiphon continued at the top of the next page by a capitalised line (or after a full stop) is cut in two outside COM — 11 hours (ADV CHR.DEC29 Lauds, FEAST.BAPTISM Lauds, SOL.EPIPHANY Lauds/V2, SOL.MARY_MOTHER_OF_GOD Lauds/V1; LQP EAS.3.SUN V1, HOLY.MON Midday, LENT.3.SUN V2; PA OT.22.SUN V2, OT.25.SUN Lauds) get a `text` tail and an unrecognised repeat; the COM rule in `parse_ant` (a flush-left page-top line continues the antiphon) fixes all 11 and nothing else, but is limited to COM to keep this diff additive. (b) Pre-existing: after a repeated Sunday Gospel antiphon (`Anno C`, emitted with keep_cond) `cond.year` stays set and is copied onto PRECES / PATER / ORATIO / CONCLUSION (PA 95, LQP 32, ADV 12 occurrences) | — | WS1/WS2/WS5/WS6 | **(b) fixed on `lead/post-workstreams`: the year of a Sunday Gospel antiphon no longer leaks to the preces, prayer and closing slots (1,284 spurious conditions removed; regression test). (a) open.**

### T-SPA — LH-Sanctis-Per_annum.pdf vs. the current General Roman Calendar, and source omissions (found by WS4a)

Calendar data: Liturgical Calendar API (`lh fetch` → `sources/web/litcal/`, Missale Romanum 1970/2002/2008 + decrees,
pinned commit in `lh/fetch.py`). All 170 SPA celebrations map to a LitCal key (one hand-made key, T-SPA-6); for all of
them the printed rank line (none / *Memoria* / *Festum* / *Sollemnitas*) agrees with LitCal's current grade. The title
page says "MTF 2010", but the volume already has the 2014 additions (John XXIII, John Paul II) and Mary Magdalene as a
feast (2016): it is a ~2016 state of the calendar, not 2010.

| ID | Status | Item | SPA pages | Evidence / proposal |
|---|---|---|---|---|
| T-SPA-1 | [?] | Celebrations added to the General Roman Calendar after the volume and falling in its range, **absent from SPA**: *Mary, Mother of the Church* (memorial, Monday after Pentecost, 2018), *Paul VI* (29 May, 2019), *Faustina Kowalska* (5 Oct, 2020), *Gregory of Narek* (27 Feb, 2021), *John of Ávila* (10 May, 2021; usually Easter Time → SP), *Hildegard of Bingen* (17 Sep, 2021), *Teresa of Calcutta* (5 Sep, decree 2024), *John Henry Newman* (9 Oct, decree 2025) | — | LitCal `decrees.json`. Propose (WS6): add day rows from LitCal with the office "de Communi" (commons named in the decrees); Mary, Mother of the Church has a proper office (decree 2018) to be sourced separately |
| T-SPA-2 | [?] | Source omissions excused by `lh/sources/spa.py` STRUCTURE_EXCEPTIONS: no opening verse at Conversion of Paul Daytime Prayer (103), St Lawrence OR (1055) and Lauds (1062); no "Conclusio Horæ" link at Vespers of Perpetua & Felicity (330), John of God (339), Josemaría Escrivá (661), Margaret Mary Alacoque (1635), Lauds of St Lawrence (1067), Exaltation of the Cross (1351), Archangels (1496), Luke Daytime Prayer (1660) | see item | Every other hour prints them (GILH 41, 54, 79). Propose: book supplies the standard opening/conclusion; no data change |
| T-SPA-3 | [ ] | Labels missing in the source, recovered by the parser: HYMNUS before *Hi sacerdótes Dómini sacráti* at Lauds of Cyril & Methodius (259; its place taken by the misplaced rubric "Antiphona ad Benedictus est huius memoriæ propria."), of its ALTERA *Festum* (2067) and of Pontian & Hippolytus ALTERA *Pastores* (2357); RESPONSORIUM BREVE at Bernardine of Siena Vespers (414); LECTIO ALTERA at Holy Name of Mary OR (1314); "Responsorium breve" set in black roman at Guardian Angels Vespers (1540) | see item | Note only |
| T-SPA-4 | [?] | *St Martha* (29 Jul): since 2021 *Saints Martha, Mary and Lazarus* (new title and texts, decree 26 Jan 2021); SPA prints *S. MARTHÆ* (910) | 910–918 | Day title follows LitCal (current); the printed office is the old one. Owner: keep, or source the 2021 texts |
| T-SPA-5 | [ ] | *St Irenaeus* declared Doctor of the Church (2022); SPA title *S. IRENÆI, EPISCOPI ET MARTYRIS* (671) | 671–676 | Note only (title; collect unchanged) |
| T-SPA-6 | [?] | *St Josemaría Escrivá* (26 Jun) is printed in SPA but is not in the General Roman Calendar (LitCal has no key); keyed `SANCT.06-26.StJosemariaEscriva`, optional memorial, from `EVENTS` in `lh/sources/spa.py` | 653–661 | Owner: keep (as a proper/national celebration) or drop from the book |
| T-SPA-7 | [ ] | *St Jane Frances de Chantal* printed on 12 Aug (her date since the Missale Romanum 2002); LitCal's 1970 data still has 12 Dec | 1086 | Keyed by the printed date `SANCT.08-12.…`; note only |
| T-SPA-8 | [ ] | Psalm consensus additions from SPA (T-CONS: 64 lines with PA LQP ADV COM SP SQ SADV, 77 with SPA added), e.g. Ps 138:7 set as one line + two (1501), Ps 126:5 numbering in the complementary psalmody (2617–2630, as PA 1270) | see `reports/verification.md` | Part of T-CONS |

### T-WS6 — findings while generating the full book (WS6, `ws/full-book`)

| ID | Status | Item | Where | Evidence / proposal |
|---|---|---|---|---|
| T-WS6-1 | [ ] | Near-duplicate objects are printed once *each*: e.g. Lauds Ant. 3 Week II Wed *Dóminus regnávit, exsúltet terra.* (Per annum, Lent) vs *Dóminus regnávit! Exsúltet terra.* (Advent); the Sunday collect of most Ordinary Time weeks is a different object at the weekdays' Office of Readings (punctuation), so the weekly propers print a second "Collect (weekdays, Office of Readings)" | book: Proper of Time; `reports/verification.md` near-duplicates | Part of T-DUP: every merge override removes a printed text from the book |
| T-WS6-2 | [ ] | Printing variants of one canticle (punctuation, line breaks; T-COM-2) are labelled at the most printed variant instead of being printed again; variants whose line count differs by more than 2 are printed separately | Canticles chapter | Owner: confirm that a consensus text is acceptable for canticles as for psalms (T-CONS) |
| T-WS6-3 | [ ] | The Communia appendix chapter *Ad Invitatorium* (`COM.ORD.INVITATORY`, 3 instances) also contains the complementary psalmody; the book takes it from PA's *Psalmodia complementaris* (attribution priority), so nothing is lost | COM 1675–1699 | Note only (COM plug-in chapter boundaries) |
| T-WS6-4 | [?] | Page budget: 2,809 pages in one volume (1,725 without the readings) (see `reports/page_budget.md`); the Office of Readings readings alone are ~1,080 pages | `reports/page_budget.md` | Owner decides B-12 (companion volume / smaller type / alleluia rule) |

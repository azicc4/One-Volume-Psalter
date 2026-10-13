# Workstream briefs (for subagents / collaborating sessions)

Each source PDF is brought into the database by one workstream, running in its own git worktree and opening its own
PR to `main` (see `docs/contributing.md`). The lead session merges, then regenerates `data/export/` and `reports/`.
These briefs are written to be pasted as the prompt of a subagent (Agent tool, `isolation: "worktree"`) or read by a
new Claude Code session. Every brief implies: read `CLAUDE.md`, `docs/architecture.md`, `docs/source-pdf-format.md`
first; claim the item in `TODO.md`; pass all gates; report source discrepancies in `TODO.md` §3, never fix them silently.

## Common definition of done

- `python -m lh build PA LQP ADV:4-1198 <KEY…>` succeeds; `python -m lh verify` shows round-trip 0 failures and
  coverage 0 gaps for every source of the workstream (non-content pages declared with a reason in the plug-in).
- Every day/hour of the volume's own index is present (add an index check for the volume if its index differs from
  Per annum's — `lh/verify/checks.py: expected_from_index`).
- Structure check: no unexplained failures (exceptions documented in `TODO.md` T-STRUCT with the GILH reason).
- ≥ 5 golden tests in `tests/test_<key>.py` on tricky pages.
- Duplicate printings inside the volume collapse to the same objects (check `n_occ` and the near-duplicate report).
- PR description lists shared-core changes and findings.

## WS1 — ADV (Advent and Christmas Time)

Plug-in `lh/sources/adv.py` (day mapping exists for copy 1; `COPIES` lists the 7 start-date copies with page ranges).
1. Build with the whole volume (`ADV`, not `ADV:4-1198`); every copy's hours get `copy` = its start date.
2. Verify the copy boundaries and the per-copy index pages (`NON_CONTENT`).
3. Confirm that copies collapse: the same day/hour in different copies must yield the same objects except where the
   calendar genuinely differs (e.g. Holy Family replacing St Stephen; Sunday-dependent psalter weeks in Christmas Time).
   Report any text that differs between copies for the same day (consensus).
4. Christmas Time: record the weekday/psalter week each copy implies for dated days (subtitle "FERIA II" etc.).
5. Traps: Immaculate Conception missing from the 1 Dec copy (pages 5003–6273) — take from SADV p.65 (coordinate with
   WS4b); two post-Octave tracks (Epiphany on 6 Jan vs on Sunday) share pages 935–1198; ADV.1.SUN II Vespers lacks a
   Gospel antiphon slot (T-STRUCT); the ALIA EX ORDINARIO appendix (8388–8414) and vigil canticles/Gospels (8415–8420).

## WS2 — LQP (Lent, Holy Week, Triduum, Easter Time)

Plug-in `lh/sources/lqp.py` (day mapping exists). Already 100 % covered except T-UNP (LQP 2522).
1. Fix T-UNP (preces interrupted) and the LQP T-STRUCT items: Easter Vigil replacing the Office of Readings of Easter
   Sunday (template exception), Easter-week Daytime versicles, Ascension Vespers/Office of Readings conclusions.
2. Ascension printed on two tracks (Thursday vs transferred to Sunday): label the tracks meaningfully
   (`copy` = "Ascension Thu" / "Ascension Sun") instead of `#2`.
3. Model *Loco responsorii dicitur* (Hæc dies / Christus factus est) and the inline Regina cæli explicitly.
4. Research T-FJ-14: Easter week 4 Friday/Saturday Office of Readings prints Ps 55/50 where Advent/Lent print Ps 78.

## WS3 — COM (Commons and the Office of the Dead)

Plug-in `lh/sources/com.py` (stub). Four seasonal copies: Advent/Christmas 4–416, Lent 417–817, Easter 818–1207,
Per annum 1208–1640; Office of the Dead 1641–1675; ALIA EX ORDINARIO 1675–1699.
1. Day keys `COMMON.<NAME>[.<VARIANT>]`: DEDICATION, BVM, APOSTLES, MARTYRS.SEVERAL, MARTYRS.ONE (+ VIRGIN),
   PASTORS (+ POPE, BISHOP, PRIEST, SEVERAL, FOUNDER, MISSIONARY), DOCTORS, VIRGINS, HOLY_MEN (+ RELIGIOUS,
   EDUCATOR, WORKS_OF_MERCY), HOLY_WOMEN, BVM_SATURDAY; DEAD for the Office of the Dead. Season as `copy`.
2. Sub-variant rubrics ("Pro papa:", "Pro episcopo:", "Vel alia, præsertim pro episcopo:") become `cond` values.
3. The four copies must collapse to one set of objects plus seasonal variants (Easter alleluias).
4. Name placeholder "N." stays as text.

## WS4a — SPA (Proper of Saints, Ordinary Time)

Plug-in `lh/sources/spa.py` (stub). Outline: date → title and hours as siblings.
1. Day header: date line (14.4 bold), title (16.6 bold, may wrap), rank (14.4 italic red; none = optional memorial),
   biography → store rank/bio from `source_line` (role day_extra) on the day.
2. Day keys `SANCT.MM-DD.<litcal_key>` using the Liturgical Calendar API data (`propriumdesanctis` JSON, Apache-2.0)
   for keys and ranks; flag saints added or re-ranked after 2010 (LitCal `decrees.json`) in TODO §3.
3. ALTERA sections (2002–2596, unoutlined): alternative offices (Pastor/Virgo/…) — key them to their saint.
4. Traps: Assumption title non-bold (SPA 1111); two-line titles; "Eodem die …"; feasts without I Vespers.
5. Commons are already filled in the printed offices: leave detection of "de Communi" to WS6, but keep provenance.

## WS4b — SP, SQ, SADV (Proper of Saints: Easter, Lent, Advent/Christmas)

Plug-ins `lh/sources/sp.py`, `sq.py`, `sadv.py` (stubs). Same day-key scheme as WS4a.
1. SQ: commemorations ("Pro commemoratione": antiphon + prayer, extra reading) — model as rank `commemoration`.
2. Overlaps: SQ ∩ SPA (Feb–Mar), SQ ∩ SP (19 Mar, 25 Mar, 2–13 Apr), SP ∩ SPA (May–June), SADV ∩ SPA (St Andrew):
   the same saint printed in two volumes must resolve to one day with season-dependent variants (report differences).
3. SADV 26–28 Dec give only Vespers (rubric SA 149); Immaculate Conception (SA 65) also feeds WS1.

## WS5 — PA residue

Plug-in `lh/sources/pa.py`. Fix T-UNP in the Saturday memorial of the BVM (PA 6278); model the hymns *ad libitum*
(PROP chapters) as hymn alternatives of the weeks they name; confirm coverage stays 100 %.

## WS6 — redundancy engine and full book (lead, after WS1–WS5)

Assign every object one home (see `docs/architecture.md`), turn saints' texts equal to a Common into references,
generate all sections in book order for the whole year, and produce a page-budget report per section.

## WS7 — data review (lead + owner)

Work through `TODO.md` §3: for each item gather evidence (`lh show <id>`, PDF pages), propose an override, owner decides.

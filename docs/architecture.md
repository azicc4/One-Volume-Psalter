# Architecture

```
L0 sources        8 PDFs (repo root) + web references (sources/web/, lh fetch)
L1 extract        lh/extract/spans.py   build/l1/<KEY>.sqlite: every text line, spans (size/colour/flags), links, outline
L2 lines          lh/extract/lines.py   visual lines (same-baseline merge), kind = week|day|hour|subhour|label|verse|ant|V|R|…
L3 parse          lh/parse/hour.py      hour instances → typed elements with slot codes; lh/parse/appendix.py for appendices
L4 canonical      lh/model/canon.py     element → OBJECT (text identical wherever printed) + occurrence EXTRA
L5 model          lh/model/build.py     build/lh.sqlite (schema.sql) + overrides (data/overrides/)
L6 verification   lh/verify/            round-trip, PDF index, coverage, GILH structure, psalm consensus, near-duplicates
                  lh/psalter/           Felix Just cross-check, Nova Vulgata gap fill
L7 catalog        lh/catalog/           reference/index.html
L8 book           lh/render/, book/     LuaLaTeX → book/out/*.pdf
```

## Database (`lh/model/schema.sql`)

| Table | One row per | Key columns |
|---|---|---|
| `source` | source PDF in the build | key, pdf, sha256, page scope (p0, p1) |
| `day` | liturgical day (or appendix chapter) | key (`OT.05.SUN`…), season, week, weekday, psalter_week, rank, precedence, short |
| `hour_instance` | printed hour | source, day_key, hour, pages, copy (duplicate label), l1_first/l1_last |
| `occurrence` | element printed in an hour | hour_id, seq, type, slot, sub, cond, object_id, page, source_text, extra |
| `object` | canonical text | id (readable + hash), type, payload (JSON with `<r> <i> <v>` markup), n_occ, status, home |
| `object_fts` | FTS5 index | accent-insensitive search |
| `psalm`, `psalm_verse` | psalm; verse line | Hebrew number, Vulgate label; line text, source LH/NV/NVT, consensus counts |
| `psalm_use` | psalm portion use | unit, verses, day/hour/slot, psalter week — drives Psalter margin notes |
| `hour_refs` | hour | Ordinary anchor, psalm units (≤3), readings — drives ribbon page refs |
| `link_target` | printed link | target page → hour instance, element and object (how = text: the link names it; page: first element there) |
| `source_line` | line outside any hour | role heading/day_extra/front — used by coverage |
| `psalter_compare` | Felix Just row | status match/range_diff/… |
| `check_result`, `override_log` | check finding / applied override | |

## Objects and occurrences

`canon(element)` returns the object (what is the same in every printing) and the occurrence *extra* (what may vary:
antiphon number, intonation dagger, printed Gloria Patri, heading lines, strophe breaks caused by page breaks).
`restore(object, extra)` must reproduce the printed text; that is the round-trip check. Object ids are readable:
`ant.ad-te-orabo-domine.d967f7`, `ps.063.2-9.aa45` (Hebrew psalm number, verse range, hash), `cant.dan3_57-8856.a1b8`.

## Day keys

`OT.NN.DOW` · `ADV.N.DOW` · `ADV.DEC17` … `ADV.DEC24` · `CHR.DEC26` … `CHR.JAN07` · `LENT.0.WED` (Ash Wednesday) ·
`LENT.N.DOW` · `HOLY.DOW` · `TRIDUUM.THU/FRI/SAT` · `EAS.1.SUN` · `EAS.OCT.DOW` · `EAS.N.DOW` · `SOL.<NAME>` ·
`FEAST.<NAME>` · `ORD.<CHAPTER>` (Ordinary appendix; other sources prefixed `LQP.ORD.…`) · `PROP.<CHAPTER>` (proper
appendix, e.g. `PROP.HYMNS_AD_LIBITUM`) · `MEM.BVM_SATURDAY` (Saturday memorial of the BVM, PA 6269; appendix chapters
that are real days are mapped in the plug-in's `APPENDIX_DAYS`) · planned: `COMMON.<NAME>[.<variant>]`,
`SANCT.MM-DD.<litcal_key>`. DOW = SUN MON TUE WED THU FRI SAT.

## Slot codes

Opening/Invitatory: `OPENING`, `PREP_PRAYER`, `INV_ANT`, `INV_PSALM` (links). Psalmody: `ANT1..3`, `ANT` (single or
per-hour seasonal), `PS1..3` (psalm/canticle units; a section I/II/III is its own unit), `*_R` (repeated antiphon).
Office of Readings: `OR_VERSE`, `LECT1`, `RESP1`, `LECT2`, `RESP2`, `TE_DEUM`. Lauds/Vespers/Compline: `LB`, `RB`,
`GOSPEL_ANT`, `GOSPEL_CANT`, `PRECES`, `PATER`, `ORATIO`, `CONCLUSION`, `BLESSING`, `MARIAN`. Daytime Prayer: `sub`
= TERCE/SEXT/NONE on hymn, antiphon, `LB`, `V`, `ORATIO`; psalmody shared (`sub` empty). Links: `HYMN_ALT` (alternative
hymn printed elsewhere: "Vel alter", "Ad libitum dici potest hymnus …"), `MEMORIAL` ("Memoria ad libitum Sanctæ Mariæ"),
`LECT1`/`LECT2` (a reading given by reference), `CONCLUSION`, `MARIAN`, `COMPLEMENTARY`, `SUBST`, `LINK`; each resolved in
`link_target`. Conditions in `cond`: `{"year": "A"}`, `{"variant": "night"}`, `{"alt": "Vel:"}`, `{"choice": "3"}`
(numbered alternatives "1 …" … "6 …": Gospel antiphons and prayers of the BVM on Saturday).
Substitutions: in the Triduum and the Easter Octave the `RB` slot holds an antiphon (*Loco responsorii dicitur:
Christus factus est / Hæc dies*); in Eastertide Compline the `MARIAN` slot holds the *Regína cæli* printed in full
(a `text` object) instead of a link. Easter Sunday's Office of Readings is the Easter Vigil (GILH 212): `LECT1..4`,
each followed by its chant (`PS1..3`) and prayer, then `TE_DEUM`, `ORATIO`.

## Attribution ("home") — WS6

Each object is printed once, at the first applicable home: Ordinary → Psalter (psalms and canticles) → Hymns →
Proper of Time (four-week grid with seasonal variants) → Commons → Proper of Saints → Office of Readings readings.
Every other use is a page reference. Saints' texts identical to a Common become "de Communi" references; saints'
psalms equal to the ferial psalter become "psalmi de feria".

## Book order and ribbons

Proper of Saints (1) · Commons (2) · Ordinary (3) · Proper of Time (4) · Hymns (5) · Psalter with Canticles
(6–9: up to three psalms per hour + the invitatory psalm) · Office of Readings readings (10).

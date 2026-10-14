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
| `day` | liturgical day (or appendix chapter) | key (`OT.05.SUN`…), season, week, weekday, psalter_week, rank, precedence, short, extra (JSON, plug-in specific: Sanctis printed preamble + LitCal data) |
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

`OT.NN.DOW` · `ADV.N.DOW` · `ADV.DEC17` … `ADV.DEC24` · `CHR.DEC26` … `CHR.DEC31` · `CHR.JAN02` … `CHR.JAN07`
(weekdays before Epiphany, texts by date) · `CHR.POSTEPI.JAN07` … `CHR.POSTEPI.JAN12` (the k-th weekday after Epiphany
takes the texts of (6+k) January, whatever its date — see `lh/sources/adv.py`) · `CHR.2.SUN` · `LENT.0.WED` (Ash Wednesday) ·
`LENT.N.DOW` · `HOLY.DOW` · `TRIDUUM.THU/FRI/SAT` · `EAS.1.SUN` · `EAS.OCT.DOW` · `EAS.N.DOW` · `SOL.<NAME>` ·
`FEAST.<NAME>` · `ORD.<CHAPTER>` (Ordinary appendix; other sources prefixed `LQP.ORD.…`) · `PROP.<CHAPTER>` (proper
appendix, e.g. `PROP.HYMNS_AD_LIBITUM`) · `MEM.BVM_SATURDAY` (Saturday memorial of the BVM, PA 6269; appendix chapters
that are real days are mapped in the plug-in's `APPENDIX_DAYS`) · `SANCT.MM-DD.<litcal_key>` (Proper of Saints, all
four Sanctis volumes: printed date + Liturgical Calendar API event key, e.g. `SANCT.01-13.StHilaryPoitiers`,
`SANCT.03-19.StJoseph`; movable `SANCT.MOVABLE.ImmaculateHeart`; a celebration without a LitCal match would fall back
to a title slug; saints the Proper of Time prints keep its key: `SOL.IMMACULATE_CONCEPTION`, `CHR.DEC26`) ·
`COMMON.<NAME>[.<variant>]` (Commons: `COMMON.DEDICATION`, `COMMON.BVM`,
`COMMON.APOSTLES`, `COMMON.MARTYRS.SEVERAL`, `COMMON.MARTYRS.ONE`, `COMMON.PASTORS`, `COMMON.DOCTORS`, `COMMON.VIRGINS`,
`COMMON.HOLY_MEN`, `COMMON.HOLY_WOMEN`; the seasonal printing is `hour_instance.copy` = ADV / LENT / EAS / OT; the
Commons' sub-variants — pope, bishop, virgin martyr … — are `cond.for`, not day keys) · `DEAD` (Office of the Dead).
DOW = SUN MON TUE WED THU FRI SAT.

Advent/Christmas printings are told apart by `copy` = start date of the copy (`27 Nov` … `3 Dec`), plus the Christmas
track for days printed on one track only (`28 Nov, Epiphany Sunday` / `28 Nov, Epiphany 6 Jan`); `reports/adv_copies.md`
compares the copies and lists each dated day's weekday and psalter week per copy.

Sanctis days (`lh/sources/sanctis.py`) take rank and precedence from LitCal's current grade, the same in every volume;
`day.extra` keeps what is printed (date line, title, rank line, rubrics, biography; other printings under `copies`) and
the LitCal key, grade and decrees. Printings of one day are told apart by `hour_instance.source` and `copy`:
`commemoratio` (Lenten / late-Advent / Christmas-octave commemoration, its own structure template), `propria` (proper
parts only), `altera <label>` (unoutlined ALTERA alternative offices, labelled as in the volume's index),
`sollemnitas` (SADV 26-28 Dec Vespers).

## Slot codes

Opening/Invitatory: `OPENING`, `PREP_PRAYER`, `INV_ANT`, `INV_PSALM` (links). Psalmody: `ANT1..3`, `ANT` (single or
per-hour seasonal), `PS1..3` (psalm/canticle units; a section I/II/III is its own unit), `*_R` (repeated antiphon).
Office of Readings: `OR_VERSE`, `LECT1`, `RESP1`, `LECT2`, `RESP2`, `TE_DEUM`, `GOSPEL` (Christmas vigil, Adv 8418). Lauds/Vespers/Compline: `LB`, `RB`,
`GOSPEL_ANT`, `GOSPEL_CANT`, `PRECES`, `PATER`, `ORATIO`, `CONCLUSION`, `BLESSING`, `MARIAN`. Daytime Prayer: `sub`
= TERCE/SEXT/NONE on hymn, antiphon, `LB`, `V`, `ORATIO`; psalmody shared (`sub` empty). Links: `HYMN_ALT` (alternative
hymn printed elsewhere: "Vel alter", "Ad libitum dici potest hymnus …"), `MEMORIAL` ("Memoria ad libitum Sanctæ Mariæ"),
`LECT1`/`LECT2` (a reading given by reference), `CONCLUSION`, `MARIAN`, `COMPLEMENTARY`, `SUBST`, `LINK`; each resolved in
`link_target`. Conditions in `cond`: `{"year": "A"}`, `{"variant": "night"}`, `{"alt": "Vel:"}`, `{"choice": "3"}`
(numbered alternatives "1 …" … "6 …": Gospel antiphons and prayers of the BVM on Saturday), `{"for": "Pro papa"}`
(sub-variant rubric of the Commons / Office of the Dead: "Pro papa:", "Pro pluribus:", "In ipsa ecclesia dedicata:",
"Tempore Adventus:", "Vel alia, præsertim pro episcopo:" → `for` + `alt`; a reading's `for` also marks its responsory;
the common stanzas printed after the last of several one-stanza hymn variants are split off and keep the hymn's own `for`).
Substitutions: in the Triduum and the Easter Octave the `RB` slot holds an antiphon (*Loco responsorii dicitur:
Christus factus est / Hæc dies*); in Eastertide Compline the `MARIAN` slot holds the *Regína cæli* printed in full
(a `text` object) instead of a link. Easter Sunday's Office of Readings is the Easter Vigil (GILH 212): `LECT1..4`,
each followed by its chant (`PS1..3`) and prayer, then `TE_DEUM`, `ORATIO`.

## Attribution ("home") — WS6

Each object is printed once, at the first applicable home: Ordinary → Psalter (psalms and canticles) → Hymns →
Proper of Time (four-week grid with seasonal variants) → Commons → Proper of Saints → Office of Readings readings.
Every other use is a page reference. Saints' texts identical to a Common become "de Communi" references; saints'
psalms equal to the ferial psalter become "psalmi de feria".

`lh/model/attribute.py` (run by `lh build` after the overrides) sets `object.home` (section: ordinary, psalter,
hymns, time, commons, saints, readings; `inline` for rubrics and links, which are printed where they stand) and
`object.home_label` (location). Hymns, psalms/canticles (invitatory psalms with refrains and Gospel canticles: the
Ordinary), Te Deum and the readings/responsories of the Office of Readings have their section by type; every other
object goes to the first location, in priority order, where it is used:

| Location | Where in the book |
|---|---|
| `ord:fixed`, `ord:<CHAPTER>:<hour>` | Ordinary: abbreviated opening verses; appendix chapters (INVITATORY, COMPLEMENTARY, DISMISSAL, MARIAN …; `ADV.ORD.X`, `SPA.ORD.DIMISSIO` … normalised) |
| `ord:compline:<FORM>` | weekly Compline: SAT1 (after I Vespers), SUN, MON … FRI from the grid days; EASTER from the Easter Octave |
| `time:grid:<pw>.<DOW>:<hour>` | the 28 psalter days, every season's text side by side |
| `time:otweek:<NN>` | Ordinary Time week NN: Sunday Gospel antiphons (A/B/C) and collect (also the weekdays' Office of Readings prayer) |
| `time:day:<DAY>:<hour>` | wholly proper days (17–24 Dec, Christmas Time, Ash Wednesday–Saturday, Holy Week, Triduum, Easter Octave, Ascension, Pentecost, solemnities of the Lord) |
| `com:<DAY>:<hour>` | Commons (`COMMON.*`, seasonal copies as variants), `DEAD`, `MEM.BVM_SATURDAY` |
| `sanct:<DAY>:<hour>` | Proper of Saints (`SANCT.*`, `SOL.IMMACULATE_CONCEPTION`) |
| `read:<DAY>` | Office of Readings readings, first day in liturgical order |

Table `reference(hour_id, slot, sub, object_id, kind, target, target_home)` records the printings replaced by a named
reference: `de_communi` (a saint's text equal to a Common's in the same hour and slot; target = the Common),
`de_feria` (a saint's or Common's psalmody equal to a psalter-week cell), `grid` (a seasonal grid day's text equal to
the Per annum text of the cell). The book generator (`lh/render/book.py`) prints an object in full where it meets its
home location for the first time and gives `\seepage{…}` everywhere else; printing variants of one psalm, canticle,
invitatory psalm or Te Deum (punctuation/line breaks, T-DUP) are labelled at the consensus text. `\budget{…}` labels
feed `reports/page_budget.md`.

## Book order and ribbons

Proper of Saints (1) · Commons (2) · Ordinary (3) · Proper of Time (4) · Hymns (5) · Psalter with Canticles
(6–9: up to three psalms per hour + the invitatory psalm) · Office of Readings readings (10).

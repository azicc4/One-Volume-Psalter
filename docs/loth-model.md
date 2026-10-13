# How the Liturgy of the Hours works (for the data model)

Distilled from the *General Instruction of the Liturgy of the Hours* (GILH) and the *Universal Norms on the
Liturgical Year and the Calendar* (UNLY). Paragraph numbers in brackets. These rules drive
`data/seed/hour_templates.yaml`, `data/seed/psalter_week_map.yaml` and the slot fallback chains in the DB.

Sources: GILH (EWTN full text) <https://www.ewtn.com/catholicism/library/general-instruction-on-the-liturgy-of-the-hours-28969>;
UNLY <https://www.liturgyoffice.org/Calendar/Info/GNLY.pdf>; Felix Just <https://catholic-resources.org/LoH/>.

## 1. Element order of each hour

Common opening (all hours except the Invitatory): *Deus, in adiutorium… Gloria Patri… Sicut erat… Alleluia*
(Alleluia omitted in Lent) [41, 60, 79, 85]. Omitted from whichever hour the Invitatory precedes.

Every psalm/canticle unit: antiphon → psalm → Gloria Patri → antiphon [113–125]. Long psalms are divided
into sections (I, II, III) each with antiphon and Gloria [115, 124]. Psalm title, NT/patristic sentence and
psalm-prayer are optional aids [111–112]. Dan 3:57-88,56 has **no Gloria Patri**.

| Hour | Slots in order | GILH |
|---|---|---|
| **Invitatory** (INV) | ℣ *Domine, labia mea aperies* · antiphon · Ps 95 (or 100, 67, 24) with antiphon repeated · Gloria | 34–36 |
| **Office of Readings** (OR) | opening · hymn (OT: night/day series) · 3 ant+psalm · ℣ · lectio prior (Scripture) + responsory · lectio altera (patristic/hagiographic) + responsory · *Te Deum* (conditional) · oratio · (in common) *Benedicamus Domino* | 55–69 |
| OR vigil extension (Sun/solemnity/feast, optional) | after 2nd reading: 3 canticles under one antiphon · Gospel · (homily) · Te Deum · oratio | 73 |
| **Lauds** / **Vespers** | opening · hymn · psalmody (Lauds: morning psalm, OT canticle, praise psalm; Vespers: 2 psalms + NT canticle) · lectio brevis · responsorium breve · Benedictus / Magnificat + antiphon · preces · Pater noster · oratio · dismissal | 41–54 |
| **Daytime** (TERCE/SEXT/NONE) | opening · hymn proper to the hour · 3 psalms/sections (current or complementary) · lectio brevis · ℣/℟ · oratio · (in common) *Benedicamus* | 74–83 |
| **Compline** | opening · examen (penitential act) · hymn · 1–2 psalms (weekly cycle) · lectio brevis · ℟ *In manus tuas* · Nunc dimittis + ant *Salva nos* · oratio (psalter, per day) · blessing *Noctem quietam* · Marian antiphon | 84–92 |

Fixed texts (→ Ordinary): opening verses, invitatory psalms, Te Deum, Benedictus, Magnificat, Nunc dimittis,
Gloria Patri, dismissals/blessings, *In manus tuas*, complementary psalm texts, Marian antiphons.

Special substitutions: Easter Octave — *Hæc dies* replaces the short responsory; Triduum — *Christus factus est*.
Lent Sunday Vespers NT canticle = 1 Pet 2:21-24 (instead of Rev 19); Epiphany & Transfiguration = 1 Tim 3:16.

## 2. Where each slot comes from, by rank

Model every slot as a **fallback chain**, e.g. `proper_of_day → common → psalter(week, day, hour)`,
with special targets where the rules say so.

| Rank | I Vespers | Invitatory / OR | Lauds | Daytime | Vespers | Compline |
|---|---|---|---|---|---|---|
| **Solemnity** [225–230] | yes: proper→common; psalms = 2 Laudate psalms (113, 117, 135, 146, 147) + NT canticle | all proper (psalms, readings), Te Deum | proper→common; **psalms = Sunday Wk I** | weekday hymn; **complementary** psalms with proper ant (Sunday Wk I psalms if on Sunday); LB + oratio proper | proper psalms; preces proper→common | Sunday Compline (after I V: Ps 4+134; after II V: Ps 91) |
| **Feast** [231–233] | no (except feasts of the Lord on Sunday) | as solemnity, Te Deum | as solemnity (Sunday Wk I psalms) | weekday hymn; **ferial** psalms+ants; LB + oratio proper | proper | of the day |
| **Memorial** [234–236] | — | psalms+ants ferial (unless proper); invitatory ant/hymn proper→common→ferial; lectio prior ferial; lectio altera of the saint; **no Te Deum** | psalms ferial; hymn, LB, RB, Benedictus ant, preces proper→common→ferial; **oratio of the saint** | entirely ferial | as Lauds | ferial |
| **Commemoration** (Lent weekdays, Dec 17–24, Christmas Octave) [238–239] | — | after seasonal patristic reading: saint's reading + resp + oratio may be added | after the day's oratio: saint's antiphon + oratio | — | as Lauds | — |
| **Sunday** [204–206] | from psalter (current week) | current week Sunday; Te Deum except Lent | current week; seasonal Sundays have proper ants [116]; Gospel ants per Year A/B/C | Sunday psalter | Sunday psalter | Sunday |
| **OT weekday** | — | psalter; OR readings of the day; OR oratio = Sunday collect of the week | everything from the psalter incl. oratio [199] | psalter incl. per-hour oratio [200] | psalter | weekly cycle |
| **Seasonal weekday** (Advent ≤16 Dec, Christmas, Easter) | — | psalter psalms | psalms from psalter; hymn, LB, Gospel ant, preces, oratio from Proper of Seasons | | | |

Memorials are **ignored** on Sundays, solemnities, feasts, Ash Wednesday, Holy Week, Easter Octave [237].
Saturday BVM memorial on OT Saturdays without an obligatory memorial [240].
Te Deum [68]: Sundays outside Lent, both octaves, solemnities, feasts. Alleluia added to antiphons in Eastertide [120].

## 3. Psalter-week mapping (GILH 133)

| Period | Psalter week |
|---|---|
| Advent weeks 1–4 | I–IV |
| Christmas Time | varies by date (Week I from the Sunday 25–31 Dec, Week II from the Sunday 1–7 Jan unless OT 1 starts) |
| Ordinary Time week N | ((N−1) mod 4) + 1 (week 34 → II) |
| Ash Wednesday – Saturday | IV |
| Lent weeks 1–5 | I, II, III, IV, I |
| Holy Week Mon–Thu | II |
| Triduum, Easter Octave | proper |
| Easter weeks 2–7 | II, III, IV, I, II, III |

Seasonal psalter variants: Pss 78, 105, 106 reserved for Advent/Christmas/Lent/Easter (OR on Sat Wk I, Sat Wk II,
Fri Wk IV, Sat Wk IV). Pss 58, 83, 109 omitted entirely [131]; Ps 119 spread over Daytime Prayer [132].

**Complementary psalmody** (Hebrew numbering): Terce 120–122 · Sext 123–125 · None 126–128.

**Compline weekly cycle**: Sat (after I V) Ps 4 + 134 · Sun Ps 91 · Mon Ps 86 · Tue Ps 143:1-11 ·
Wed Ps 31:2-6 + 130 · Thu Ps 16 · Fri Ps 88.

## 4. Table of Liturgical Days (UNLY 59) — precedence numbers stored on each day

I. 1 Paschal Triduum · 2 Nativity, Epiphany, Ascension, Pentecost; Sundays of Advent, Lent, Easter; Ash Wednesday;
Holy Week Mon–Thu; Easter Octave · 3 General-calendar solemnities; All Souls · 4 proper solemnities.
II. 5 Feasts of the Lord · 6 Sundays of Christmas & OT · 7 Feasts of BVM/saints · 8 proper feasts ·
9 Advent 17–24 Dec; Christmas Octave; Lent weekdays.
III. 10 Obligatory memorials · 11 proper obligatory memorials · 12 optional memorials ·
13 Advent weekdays to 16 Dec; Christmas weekdays 2 Jan–Sat after Epiphany; Easter weekdays; OT weekdays.

Occurrence (UNLY 60): higher wins; impeded solemnities transfer; others lapse. Concurrence (61): higher rank's
Vespers; if equal, the current day's.

## 5. Traditional organisation of breviaries

- **Breviarium Romanum** (1568/1911/1961): Ordinarium · Psalterium (by weekday and hour) · Proprium de Tempore ·
  Proprium Sanctorum · Commune · Officium parvum BMV · Officium defunctorum · appendices. Before 1911 the psalter
  ran essentially in numerical order (Matins 1–108, Vespers 109–147) — precedent for our numerical Psalter.
- **Liturgia Horarum** (1971/1985), each volume: Proper of Seasons · Ordinary · 4-week Psalter · Compline ·
  Complementary psalmody · Proper of Saints · Commons · Office for the Dead · appendices.
- **BCP 1979**: Daily Office (ordinaries) · Great Litany · Collects (Seasons, Holy Days, Commons, Various
  Occasions) · Proper Liturgies · … · Psalter · Prayers · … · Daily Office Lectionary.

This book: Psalter · Hymns · Ordinaries · Propers of Time · Commons · Proper of Saints · Additional · Votive ·
OR Readings.

## 6. Psalm numbering

US/ICEL LOTH and Felix Just use **Hebrew** numbering (primary in this book). The Latin LH prints the
Vulgate number first: `Psalmus 62 (63), 2-9`. Verse numbers are Hebrew-style in both.

| Hebrew | Vulgate | LH heading form |
|---|---|---|
| 1–8 | 1–8 | |
| 9 + 10 | 9 | `9 A (9)`, `9 B (10)` |
| 11–113 | 10–112 | |
| 114 + 115 | 113 | `113 A (114)`, `113 B (115)` |
| 116:1-9 / 116:10-19 | 114 / 115 | `114 (116 A)`, `115 (116 B)` |
| 117–146 | 116–145 | |
| 147:1-11 / 147:12-20 | 146 / 147 | `146 (147 A)`, `147 (147 B)` |
| 148–150 | 148–150 | |

## 7. Finding the Office of the day (order of checking)

1. Calendar → season, week, celebrations of the date.
2. Resolve precedence (UNLY 59–60) and evening concurrence (61).
3. Psalter week (from the season/week table above).
4. Take what the rank requires from Proper of Seasons / Proper of Saints.
5. Fill gaps from the indicated Common.
6. Fill the rest from the psalter (current week & day, or Sunday Wk I / complementary as directed).
7. Fixed texts from the Ordinary.

Ribbons (traditional): Proper of Seasons · Psalter · Proper of Saints · Commons · Ordinary (+ card for hymns).

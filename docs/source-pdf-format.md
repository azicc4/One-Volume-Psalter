# Source PDF format (parser reference)

The 8 PDFs are calibre 3.21 conversions (2018) of the Diéguez / Fernández Labastida Latin *Liturgia Horarum*
ebooks (from MTF's 2010 printing). Not scans: clean Unicode, LiberationSerif + `LHSimb` (only ℣ ℟).
No running heads, no page numbers, no hyphenation. Page numbers below are 1-based PDF pages
(PA = Per annum, Adv = Adventus et Nativitatis, L/E = Quadragesimae et Paschae, SPA/SP/SA/SQ = Sanctis files).

**Everything is printed in full at every use** (psalms, canticles, Te Deum…). Only some Ordinary items are
held back in an unoutlined **ALIA EX ORDINARIO** appendix at the end of each PDF, reached via blue links.

## Tooling

Use **PyMuPDF** (`.venv`): `get_text("dict")` (spans with bbox, size, color, flags; bold=16, italic=2),
`get_links()` (0-based target pages), `get_toc()` (outline). Avoid default `pdftotext` (scrambles verse
numbers) and `pdftohtml -xml` coordinates (`top` broken, ~93 on every line; anchors misattached).

Outline: temporale = week → day → hour; Sanctis = date → (title, hours as siblings). Not outlined: ALTERA
sections, ALIA EX ORDINARIO, the Assumption title (SPA 1111, set non-bold).

## Style signatures (PyMuPDF pt; red = #ff0000, blue = #0000ee link text)

| Signature | Meaning | Example |
|---|---|---|
| 20.2 bold | week / section heading | `HEBDOMADA I` (PA 118) |
| 20.2 regular | season divider | `TEMPUS PER ANNUM`, `ALTERA`, `ALIA EX ORDINARIO` |
| 16.6 bold | day / feast title (may wrap) | `FERIA II HEBDOMADÆ I` (PA 119) |
| 14.4 bold | hour header; Sanctis date line | `Ad Laudes matutinas`; `Die 20 ianuarii` |
| 10.8 regular | per-hour subtitle repeating the day | `FERIA II HEBDOMADÆ I` |
| 14.4 red, left | rubric / labels | `Ant. 1`, `Oratio`, `Quæ tamen omittuntur…` |
| 14.4 red, centred | psalm heading, title, canticle ref, section numeral | `Psalmus 9 A (9)`, `I` |
| 14.4 + 10.1 red | small-caps labels (split "H"+"YMNUS") | HYMNUS, PSALMODIA, LECTIO PRIOR/ALTERA/BREVIS, RESPONSORIUM [BREVE], CANTICUM EVANGELICUM, PRECES |
| 14.4 italic red | Sanctis rank line; reading titles | `Memoria`, `Festum`, `Sollemnitas`, `Pro commemoratione` |
| 14.4 italic black | psalm epigraph; preces response | |
| 10.8 red LHSimb | ℣ / ℟ | |
| 5.8 red | verse number | `2`, `3c`, `(19)`, `5,9` |
| blue | link label | `Venite…`, `Vel alter`, `Conclusio`, `Ad alias` |

x-positions: 72 = couplet start / prose continuation; 76–80 = first line after a verse number;
94 = paragraph start; 104 = psalm continuation / second half.

## Formulas and markers

- Opening `℣. Deus, in adiutórium. Glória Patri. Sicut erat. Allelúia.` (Lent: no Allelúia), then
  `Quæ tamen omittuntur quando Invitatorium immediate præcedit.`
- Closing `Conclusio Horæ, ut in Ordinario.`; prayer endings abbreviated `Per Dóminum.` / `Qui vivit.` …;
  `Pater noster.` incipit only.
- Alternates: `Vel:` (printed alternative), `Vel alter` (link to appendix hymn), `Vel alia:`,
  OR hymn `I. Quando Officium lectionis dicitur noctu…` / `II. … diurno tempore:`.
- Sunday Gospel antiphons: black `Anno` + red ` A/B/C`, then `Ant.`.
- Cross-refs: `ut in Ordinario`, `… de feria currente`, `Psalmodia complementaris…`,
  `Si vero occurrat dominica…`, `Quando sequens psalmus adhibitus est ad Invitatorium…`.
- Gloria Patri printed only once (after Ps 6, PA 121) with the rubric that it is said after every psalm;
  exception rubric `In fine huius cantici non dicitur Glória Patri.` (Dan 3).

## Psalm encoding

Heading (red, centred): `Psalmus 6`, `Psalmus 9 A (9)`, `Psalmus 109 (110), 1-5. 7`,
`Psalmus 34 (35), 1-2. 3 c. 9-19. 22-23. 27-28`, `Psalmus 21 (22), 2-23 [24-32]`; Ps 118 adds `XIX (Coph)`.
Then red title, italic epigraph + citation (often omitted in Sanctis/Communia), optional section numeral.
Verse number = 5.8pt red span before its line; continuation at x=104; a new couplet within the same verse
starts at x=72 with no number. Omitted verses: numbers simply jump. `*` mediant, `†` flex at line end;
a leading `†` / trailing `†` on an antiphon = intonation mark, not flex. Dan 3 numbers every half-line.

## Hora media layouts

A psalter weekday (PA 131–136): hymns per hour + `Vel alter` · PSALMODIA Ant 1–3 · `Ad alias Horas,
psalmodia complementaris` · per-hour LB / ℣℟ / Oratio. A′ Advent/Lent: per-hour Ant after each hymn,
psalms without ants; Easter: single `Allelúia…` antiphon. B temporale solemnity. C Sanctis/Communia per hour.
D memorial `Hora media de feria currente.` E Office of the Dead. F Triduum.
Trap: `Ad Tertiam` appears twice (hymn sub-header and reading section).

## Duplication to collapse

Advent ×7 by start date (27 Nov 4–1198 · 28 Nov 1199–2462 · 29 Nov 2463–3731 · 30 Nov 3732–5002 ·
1 Dec 5003–6273 · 2 Dec 6274–7396 · 3 Dec 7397–8387); Communia ×4 by season (Adv 4–416, Lent 417–817,
Easter 818–1207, Per annum 1208–1640); Office of the Dead Communia 1641–1675; Sanctis overlaps across files.
Communia (`lh/sources/com.py`, WS3): each copy opens with a one-page index (links + two general rubrics); the Per annum
copy alone has the Saturday BVM memorial (1289–1304, same office as PA 6269, key `MEM.BVM_SATURDAY`); the Office of
the Dead has no 16.6pt title; ALIA EX ORDINARIO 1676–1699 (its substitute complementary psalms are headed
"Psalmus 121 (122), vel 128 (129)", red + blue link). Sub-variants are red rubrics ("Pro papa:") before a hymn stanza,
reading, oration or short responsory, or inline before an antiphon ("Pro virgine: Veni, sponsa Christi…", no "Ant.").
The red name placeholder "N." can open a line of prayer text (COM 1595). What differs between the four copies is
listed in `reports/com_copies.md` (`python -m lh.sources.com`).

Ascension tracks in L/E (index p.5 lists Easter week VI twice; `lh/sources/lqp.py` COPIES):
*Ascension Sun* (transferred to Sunday VII) = Wed Vespers/Compline 2206–2215, Thu 2216, Fri 2242, Sat 2267, then the
Ascension 2286 with I Vespers on Saturday evening; *Ascension Thu* = Fri 2321, Sat 2346 after the Ascension 2286
(I Vespers on Wednesday evening) → Sunday VII 2365. Week VI Sun–Wed Hora media and the Ascension itself are shared.

## Ordinary texts location (PA)

Invitatory psalms 6233–6237 · Ps 94 without refrains 6262 · alternate Hora media hymns 6238–6241 ·
complementary psalmody 6242–6253 · Ps 117 Sunday Wk I 6254–6256 · Compline hymns 6257–6258 ·
DIMISSIO 6259–6260 · Marian antiphons 6260–6261 · ALIA EX PROPRIO (Dies iræ, Salve dies, Saturday BVM) 6264–6290.

## Known traps

Immaculate Conception missing in the 1 Dec Advent copy (transferred to 9 Dec; supplied by SA 65-96) · Assumption
title non-bold (SPA 1111) · Christmas & Ascension dual tracks (Adv: each copy index lists the two Christmas tracks;
weekdays after Epiphany are printed under their date but carry the texts of 7, 8 … January) · centred date lines
above a day title (`Die 25 decembris`, Adv 713; plug-in `PRE_TITLE_LINES`) · Year A/B/C Gospel antiphons without
"Ant." (Adv 37) · `Canticum Eph 1, 3-10` on one line (Adv 286) and numbered `Canticum I` (Adv 8416) · psalm
heading wrapped after the comma (`Psalmus 68 (69),` / `2-22. 30-37`, Adv 1685, L/E 595) · antiphon continued on
the next page with a capital (Adv 1748) · heading typos (`FERIA II HEBDOMADA XXVIII`, `SACRUUM TRIDUUM`,
`ALIA EX PROPIO`, `QUARESIMÆ`) · black em dash inside psalm text (PA 732) · wrapped preces first halves at
x=72 (SPA 2000) · verse number on a continuation line (Ps 7:9) · `(19)` omitted-verse label (PA 124) ·
chapter,verse labels (`5,9`) · optional `[24-32]` (L/E 1136) · alleluia canticle layout (PA 291) ·
numbered repeat antiphon (SPA 631) · two-line day titles (Adv 514) · preces without their PRECES label (L/E 2522) or
resumed after "Vel aliæ:" (PA 6277) · numbered alternatives: red "1 " + black text, classified rubric (PA 6272, 6276) ·
alternative short reading introduced by "Vel (Ap 12, 1):" instead of a label (PA 6275) · texts after an appendix hour's
"Conclusio" (BVM second readings, PA 6280–6290) · Salve dies / Dies ætásque printed without a heading (PA 6267–6268) ·
Easter Vigil as Office of Readings with
`LECTIO PRIMA … QUARTA` and a two-psalm chant heading `Psalmi 41 (42) …; 42 (43) …` (L/E 1192–1198) ·
`Loco responsorii dicitur:` + antiphon (L/E 1129–1403) · Regína cæli under `ANTIPHONA FINALIS …` (L/E, COM, SP) ·
missing `Ad Tertiam` before Terce's short reading (L/E 1500) · Ascension I Vespers without opening, PSALMODIA
label and conclusion (L/E 2286–2290).

Sanctis (all four volumes parsed by `lh/sources/sanctis.py`; SPA examples): date line is 14.4 bold like a sub-hour
header, and twice lacks "Die" (`16 septembris`, `29 septembris`, SPA 1379, 1483) · "Eodem die …" for a second saint on the same date · movable
`Sabbato post dominicam II post Pentecosten` (Immaculate Heart, SPA 501) · rubric `Infra memoria ut martyr, vel altera …`
with a link to the ALTERA office, before the biography · the volume index (SPA 3–22) names each ALTERA variant
(`Pastor OL LD VP`) — the only place the variant is printed · `Vel: <antiphon>` (red + black) alternative antiphons and
`Vel: <response>` in preces (SPA 145, 254) · `vel:` / `Extra ipsam Basilicam Lateranensem:` + a second oratio (SPA 691,
1821) · `Vel alia:` + an alternative first reading after a link (All Souls, SPA 1774) · hymn stanzas numbered in red
(SPA 1784) · canticle 1 Tim 3 with `℟. Laudáte Dóminum, omnes gentes.` refrains (SPA 1012) · Daytime Prayer of
solemnities with one psalmody per sub-hour (layout C, SPA 639–650) · complementary psalm headings
`Psalmus 126 (127) vel 130 (131)` with a link (SPA 2606–2631) · labels missing (HYMNUS 259/2067/2357, RESPONSORIUM
BREVE 414, LECTIO ALTERA 1314) or set in black roman (`Responsorium breve`, SPA 1540).

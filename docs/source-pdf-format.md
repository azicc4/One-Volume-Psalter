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

## Ordinary texts location (PA)

Invitatory psalms 6233–6237 · Ps 94 without refrains 6262 · alternate Hora media hymns 6238–6241 ·
complementary psalmody 6242–6253 · Ps 117 Sunday Wk I 6254–6256 · Compline hymns 6257–6258 ·
DIMISSIO 6259–6260 · Marian antiphons 6260–6261 · ALIA EX PROPRIO (Dies iræ, Salve dies, Saturday BVM) 6264–6290.

## Known traps

Immaculate Conception missing in the 1 Dec Advent copy (use SA 65) · Assumption title non-bold (SPA 1111) ·
Christmas & Ascension dual tracks · heading typos (`FERIA II HEBDOMADA XXVIII`, `SACRUUM TRIDUUM`,
`ALIA EX PROPIO`, `QUARESIMÆ`) · black em dash inside psalm text (PA 732) · wrapped preces first halves at
x=72 (SPA 2000) · verse number on a continuation line (Ps 7:9) · `(19)` omitted-verse label (PA 124) ·
chapter,verse labels (`5,9`) · optional `[24-32]` (L/E 1136) · alleluia canticle layout (PA 291) ·
numbered repeat antiphon (SPA 631) · two-line day titles (Adv 514) · preces without their PRECES label (L/E 2522) or
resumed after "Vel aliæ:" (PA 6277) · numbered alternatives: red "1 " + black text, classified rubric (PA 6272, 6276) ·
alternative short reading introduced by "Vel (Ap 12, 1):" instead of a label (PA 6275) · texts after an appendix hour's
"Conclusio" (BVM second readings, PA 6280–6290) · Salve dies / Dies ætásque printed without a heading (PA 6267–6268).

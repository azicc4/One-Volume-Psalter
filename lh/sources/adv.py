"""ADV — LH-Adventus_et_Nativitatis.pdf: Advent and Christmas Time.

The volume prints Advent–Baptism once for each possible date of the First Sunday of Advent (27 Nov … 3 Dec);
see COPIES. Every copy opens with its own two-page index, whose links define the copy and, after the Octave, the two
tracks of Christmas Time: Epiphany celebrated on 6 January, or on the Sunday between 2 and 8 January
("TEMPUS NATIVITATIS POST OCTAVAM (quando Epiphania celebratur die 6 / die dominica)"). Days printed for one track
only get that track in their copy label (TRACKS); days on both tracks keep the plain start-date label.

Day keys (docs/architecture.md): ADV.N.DOW, ADV.DEC17 … ADV.DEC24, CHR.DEC26 … CHR.DEC31, CHR.JAN02 … CHR.JAN07
(weekdays *before* Epiphany, texts by date), CHR.POSTEPI.JAN07 … CHR.POSTEPI.JAN12 (weekdays *after* Epiphany, with
their own texts: invitatory "Christus appáruit nobis", Epiphany hymn …), CHR.2.SUN, SOL.*, FEAST.*.
After Epiphany the proper texts go by the day's position after the solemnity, not by its date: the k-th weekday after
Epiphany takes the texts printed for "die (6+k) ianuarii" when Epiphany is on 6 January (k = 1 … 6). So the volume's
"DIE 3 IANUARII" after Epiphany on Sunday 2 January (28 Nov copy, p. 2233) carries the texts of 7 January and is keyed
CHR.POSTEPI.JAN07 (verified: its orations equal those of every other first day after Epiphany, adv_copies.md).
The weekday (and so the psalter) of a dated day depends on the copy; reports/adv_copies.md lists it per copy
(lh/verify/copies.py).
"""
from __future__ import annotations

import re

from lh.model.days import DAY_NAMES, roman, special_day, weekday_of

KEY = "ADV"
TITLE = "Proprium de Tempore — Tempus Adventus et Nativitatis"
NON_CONTENT = [
    (1, 3, "cover, title page, index of start dates (links to the seven copies)"),
    # each start-date copy opens with its own two-page index ("Adventus incipit 27 novembris / HEBDOMADA I ADVENTUS /
    # Dominica 1v cp ol ld hm vp cp …", then the two Christmas tracks and links to the appendix); all link lines,
    # no liturgical text. Checked against the copy boundaries by tests/test_adv.py.
    (4, 5, "copy index (27 Nov)"), (1199, 1200, "copy index (28 Nov)"), (2463, 2464, "copy index (29 Nov)"),
    (3732, 3733, "copy index (30 Nov)"), (5003, 5004, "copy index (1 Dec)"), (6274, 6275, "copy index (2 Dec)"),
    (7397, 7398, "copy index (3 Dec)"),
]
COPIES = [
    (4, 1198, "27 Nov"), (1199, 2462, "28 Nov"), (2463, 3731, "29 Nov"), (3732, 5002, "30 Nov"),
    (5003, 6273, "1 Dec"), (6274, 7396, "2 Dec"), (7397, 8387, "3 Dec"),
]
# first page of the Epiphany in each copy: a "DIE n IANUARII" printed after it is a weekday after Epiphany
EPIPHANY = {"27 Nov": 1082, "28 Nov": 2197, "29 Nov": 3440, "30 Nov": 4684, "1 Dec": 5932, "2 Dec": 7176, "3 Dec": 8298}
E6, ESUN = "Epiphany 6 Jan", "Epiphany Sunday"
# Pages printed for one Christmas track only (from each copy's index: days linked under one track heading only).
# The 2 Dec copy has a single track (6 January is a Sunday). Boundaries are day-title pages.
TRACKS = [
    (1038, 1081, ESUN),   # 27 Nov: 6 and 7 Jan before Epiphany on Sunday 8 Jan
    (1118, 1136, E6),     # 27 Nov: 7 Jan after Epiphany on Friday 6 Jan
    (1137, 1171, E6),     # 27 Nov: Baptism on Sunday 8 Jan
    (1172, 1198, ESUN),   # 27 Nov: Baptism on Monday 9 Jan ("Feria II post sollemnitatem Epiphaniæ")
    (2102, 2196, E6),     # 28 Nov: Second Sunday after the Nativity (2 Jan), 3–5 Jan
    (2233, 2382, ESUN),   # 28 Nov: 3–8 Jan after Epiphany on Sunday 2 Jan
    (2383, 2427, E6),     # 28 Nov: 7–8 Jan after Epiphany on Thursday 6 Jan
    (3362, 3439, E6),     # 29 Nov: Second Sunday (3 Jan), 4–5 Jan
    (3476, 3625, ESUN),   # 29 Nov: 4–9 Jan after Epiphany on Sunday 3 Jan
    (3626, 3696, E6),     # 29 Nov: 7–9 Jan after Epiphany on Wednesday 6 Jan
    (4632, 4683, E6),     # 30 Nov: Second Sunday (4 Jan), 5 Jan
    (4720, 4869, ESUN),   # 30 Nov: 5–10 Jan after Epiphany on Sunday 4 Jan
    (4870, 4967, E6),     # 30 Nov: 7–10 Jan after Epiphany on Tuesday 6 Jan
    (5905, 5931, E6),     # 1 Dec: Second Sunday (5 Jan)
    (5968, 6117, ESUN),   # 1 Dec: 6–11 Jan after Epiphany on Sunday 5 Jan
    (6118, 6238, E6),     # 1 Dec: 7–11 Jan after Epiphany on Monday 6 Jan
    (8281, 8297, ESUN),   # 3 Dec: 6 Jan before Epiphany on Sunday 7 Jan
    (8334, 8360, E6),     # 3 Dec: Baptism on Sunday 7 Jan
    (8361, 8387, ESUN),   # 3 Dec: Baptism on Monday 8 Jan
]
# Differences between copies that are explained (lh/verify/copies.py marks them "explained"; "*" = every hour).
# Calendar differences are legitimate; source discrepancies point to their TODO.md §3 row.
COPY_NOTES = {
    ("ADV.3.SUN", "*"): "Calendar: in the 3 Dec copy the Third Sunday is 17 December, so it takes the texts of the second "
                        "part of Advent (hymns, invitatory, Office of Readings, O antiphon 'O Sapientia' …).",
    ("ADV.4.SUN", "*"): "Calendar: the Fourth Sunday falls on 18–24 December; the Office of Readings verse/readings and the "
                        "Magnificat antiphons (O antiphons) are those of the date; in the 3 Dec copy it is 24 December "
                        "(invitatory, Lauds, Daytime Prayer and oration of 24 December, no II Vespers).",
    ("CHR.2.SUN", "OR"): "Calendar: the Second Sunday after the Nativity (2–5 January) takes the Office of Readings verse, "
                         "readings and responsories of its date.",
    ("CHR.2.SUN", "COMPLINE"): "Source: Compline after I Vespers is subtitled 'POST II VESPERAS' in the 29 Nov, 30 Nov and "
                               "1 Dec copies (pp. 3367, 4637, 5910; Saturday Compline, Ps 4 and 133), so it is coded "
                               "COMPLINE. TODO §3 T-ADV-7.",
    ("FEAST.BAPTISM", "MIDDAY"): "Calendar: Daytime Prayer takes the psalter of the day — Sunday when the feast is on "
                                 "Sunday, Monday when it is moved to Monday (Epiphany on 7/8 January: pp. 1185, 8374), "
                                 "and another psalter week's Sunday in the 3 Dec copy (Sunday 7 January, p. 8347).",
    ("ADV.1.FRI", "COMPLINE"): "Source typo 'saumalo lúbrem' for 'salúbrem' in Te lucis, p. 5160. TODO §3 T-ADV-8.",
    ("ADV.DEC21", "MIDDAY"): "Source: the 28 Nov copy ends the Daytime oration with 'Per Dóminum.' (p. 1804); every other "
                             "copy has the short conclusion 'Per Christum.'. TODO §3 T-ADV-9.",
    ("ADV.DEC22", "OR"): "Source: reference '1, 46-55' (p. 647) vs '1,46-55' in the other copies. TODO §3 T-ADV-9.",
    ("ADV.DEC24", "INV"): "Source: 'véniet Dóminus, et mane' (pp. 695, 1864, 7941) vs 'véniet Dóminus: et mane' "
                          "(pp. 3106, 4350, 5599, 6846). TODO §3 T-ADV-9.",
    ("CHR.POSTEPI.JAN07", "INV"): "Source: the 28 Nov copy's 6-January track prints the pre-Epiphany invitatory "
                                  "'Christus natus est nobis' (p. 2383). TODO §3 T-ADV-2.",
    ("CHR.POSTEPI.JAN08", "INV"): "Source: as 7 January, p. 2409. TODO §3 T-ADV-2.",
    ("CHR.POSTEPI.JAN07", "OR"): "Source: the oration is printed without its 'Oratio' heading (p. 7217), so it parses as "
                                 "text. TODO §3 T-ADV-10.",
    ("CHR.POSTEPI.JAN07", "VESPERS"): "Source: 1 Dec copy, 6-January track, Vespers breaks off after the psalmody "
                                      "(pp. 6135–6138). TODO §3 T-ADV-4.",
    ("CHR.POSTEPI.JAN08", "MIDDAY"): "Source: 'Ad Tertiam' heading missing before the Terce hymn (p. 2422). TODO §3 T-ADV-10.",
    ("CHR.POSTEPI.JAN08", "VESPERS"): "Source: the 28 Nov copy (Epiphany-Sunday track, p. 2279) prints the short reading of "
                                      "27 December Vespers ('Deus Fílium suum mittens') instead of 'Erámus natúra fílii "
                                      "iræ'. TODO §3 T-ADV-3.",
}
# Findings of the calendar check (copies.py) with their explanation
CALENDAR_NOTES = {
    ("1 Dec", "SOL.IMMACULATE_CONCEPTION"): "Not printed in this copy: 8 December is the Second Sunday of Advent, so the "
        "solemnity moves to Monday 9 December, where the copy prints the Monday of Week II (p. 5216) instead. The office "
        "is supplied by SADV pp. 65–96 (same day key SOL.IMMACULATE_CONCEPTION; it matches the ADV printings except as "
        "noted in TODO §3 T-ADV-1/T-ADV-11). TODO §3 T-ADV-1.",
    ("1 Dec", "ADV.2.MON"): "Printed on 9 December in place of the transferred Immaculate Conception (see above).",
}
# Hours that lack a GILH slot because the source does not print it (lh/verify/checks.py check_structure)
STRUCTURE_EXCEPTIONS = {
    ("SOL.IMMACULATE_CONCEPTION", "LAUDS"): {
        "missing": ["CONCLUSION"],
        "reason": "Lauds of the Immaculate Conception ends with the oration in all six printings (pp. 304, 1474, 2713, "
                  "3957, 6447, 7545): no 'Conclusio Horæ' link (GILH 54). TODO §3 T-ADV-5."},
    ("FEAST.BAPTISM", "V1"): {
        "missing": ["OPENING"],
        "reason": "I Vespers of the Baptism prints no opening verse 'Deus, in adiutórium' (GILH 41) in any copy "
                  "(pp. 1137, 2428, 3697, 4968, 6239, 7362). TODO §3 T-ADV-6."},
    ("CHR.JAN02", "MIDDAY"): {
        "missing": ["CONCLUSION"],
        "reason": "29 Nov copy p. 3361: the Christmas-track navigation link replaces 'Conclusio Horæ' (GILH 79). "
                  "TODO §3 T-ADV-5."},
    ("CHR.JAN05", "MIDDAY"): {
        "missing": ["CONCLUSION"],
        "reason": "29 Nov copy p. 3439: Daytime Prayer ends with the oration before the Epiphany. TODO §3 T-ADV-5."},
    ("CHR.JAN06", "MIDDAY"): {
        "missing": ["CONCLUSION"],
        "reason": "3 Dec copy p. 8297: Daytime Prayer ends with the oration before the Epiphany. TODO §3 T-ADV-5."},
    ("CHR.POSTEPI.JAN12", "MIDDAY"): {
        "missing": ["CONCLUSION"],
        "reason": "29 Nov copy p. 3625: the link 'Festum Baptismatis Domini' replaces 'Conclusio Horæ'. TODO §3 T-ADV-5."},
    ("CHR.POSTEPI.JAN07", "VESPERS"): {
        "missing": ["LB", "RB", "GOSPEL_ANT", "GOSPEL_CANT", "PRECES", "PATER", "ORATIO"],
        "reason": "1 Dec copy pp. 6135–6138: Vespers breaks off after the psalmody (GILH 39-54 parts not printed); "
                  "complete in every other printing of the day (e.g. p. 2400). TODO §3 T-ADV-4."},
}
# centred date/occasion lines above a day title ("Die 25 decembris", "Dominica infra octavam Nativitatis") belong to
# that day's preamble, not to the end of the previous hour (lh/parse/hour.py segment)
PRE_TITLE_LINES = True
MONTHS = {"NOVEMBRIS": 11, "DECEMBRIS": 12, "IANUARII": 1}
SPECIAL = {
    "IN CONCEPTIONE IMMACULATA BEATÆ MARIÆ / VIRGINIS": ("SOL.IMMACULATE_CONCEPTION", "Immaculate Conception of the BVM", "solemnity", 3),
    "IN NATIVITATE DOMINI": ("SOL.CHRISTMAS", "Nativity of the Lord", "solemnity", 2),
    "SANCTÆ FAMILIÆ IESU, MARIÆ ET IOSEPH": ("FEAST.HOLY_FAMILY", "Holy Family", "feast", 5),
    "In octava Nativitatis Domini / SANCTÆ DEI GENETRICIS MARIÆ": ("SOL.MARY_MOTHER_OF_GOD", "Mary, Mother of God", "solemnity", 3),
    "IN EPIPHANIA DOMINI": ("SOL.EPIPHANY", "Epiphany of the Lord", "solemnity", 2),
    "IN BAPTISMATE DOMINI": ("FEAST.BAPTISM", "Baptism of the Lord", "feast", 5),
    "DOMINICA II POST NATIVITATEM": ("CHR.2.SUN", "Second Sunday after the Nativity", "sunday", 6),
}


def day_info(section: str, day: str) -> dict:
    sp = special_day(SPECIAL, day)
    if sp:
        if sp["key"] == "CHR.2.SUN":
            sp["weekday"] = "SUN"
        return sp
    m = re.match(r"^DIE (\d+) (DECEMBRIS|IANUARII)", day)
    if m:
        dd, mon = int(m.group(1)), MONTHS[m.group(2)]
        if mon == 12 and 17 <= dd <= 24:
            # week and weekday as printed in the first copy that has this date; they differ per copy (adv_copies.md)
            wk = re.search(r"HEBDOMADÆ ([IVX]+) ADVENTUS", day)
            w = roman(wk.group(1)) if wk else None
            return {"key": f"ADV.DEC{dd}", "season": "ADV", "week": w, "weekday": weekday_of(day), "psalter_week": w,
                    "title": f"{dd} December (Advent)", "rank": "privileged_weekday", "precedence": 9}
        octave = mon == 12 or (mon == 1 and dd == 1)
        return {"key": f"CHR.{'DEC' if mon == 12 else 'JAN'}{dd:02d}", "season": "CHR", "week": None, "weekday": None,
                "psalter_week": None, "title": f"{dd} {'December' if mon == 12 else 'January'} (Christmas Time)",
                "rank": "octave_day" if octave else "weekday", "precedence": 9 if octave else 13}
    m = re.search(r"HEBDOMADA ([IVX]+) ADVENTUS", section)
    if m:
        wk = roman(m.group(1))
        wd = "SUN" if day == "DOMINICA" else weekday_of(day)
        return {"key": f"ADV.{wk}.{wd}", "season": "ADV", "week": wk, "weekday": wd, "psalter_week": wk,
                "title": f"{DAY_NAMES[wd]} of Week {wk} of Advent", "rank": "sunday" if wd == "SUN" else "weekday",
                "precedence": 2 if wd == "SUN" else 13}
    raise ValueError(f"unmapped Advent/Christmas section {section!r} / day {day!r}")


# ------------------------------------------------------------------------------------------------ calendar

# a year whose First Sunday of Advent falls on each copy's start date (any such year gives the same calendar)
YEAR = {"27 Nov": 2022, "28 Nov": 2021, "29 Nov": 2020, "30 Nov": 2025, "1 Dec": 2024, "2 Dec": 2018, "3 Dec": 2023}
DOW = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]          # datetime.weekday() order


def calendar(copy: str) -> list[tuple]:
    """The days a copy must print, from its start date (General Roman Calendar, GNLYC 1969 / LH 2nd ed.):
    [(date, day key, weekday, track)] with track None when the day is the same on both Christmas tracks.
    Immaculate Conception falling on the Second Sunday of Advent is transferred to Monday 9 December."""
    import datetime as dt
    y = YEAR[copy]
    dd, mon = copy.split()
    adv1 = dt.date(y, 11 if mon == "Nov" else 12, int(dd))
    assert adv1.weekday() == 6, copy
    day = dt.timedelta(days=1)
    out = []

    def add(d, key, t=None):
        out.append((d, key, DOW[d.weekday()], t))

    d = adv1
    while d <= dt.date(y, 12, 24):
        wk, wd = (d - adv1).days // 7 + 1, DOW[d.weekday()]
        imm = dt.date(y, 12, 8) if dt.date(y, 12, 8).weekday() != 6 else dt.date(y, 12, 9)
        if d == imm:
            add(d, "SOL.IMMACULATE_CONCEPTION")
        elif wd == "SUN":
            add(d, f"ADV.{wk}.SUN")
        elif d.day >= 17 and d.month == 12:
            add(d, f"ADV.DEC{d.day}")
        else:
            add(d, f"ADV.{wk}.{wd}")
        d += day
    add(dt.date(y, 12, 25), "SOL.CHRISTMAS")
    sundays = [dt.date(y, 12, n) for n in range(26, 32) if dt.date(y, 12, n).weekday() == 6]
    holy_family = sundays[0] if sundays else dt.date(y, 12, 30)
    for n in range(26, 32):
        d = dt.date(y, 12, n)
        add(d, "FEAST.HOLY_FAMILY" if d == holy_family else f"CHR.DEC{n}")
    add(dt.date(y + 1, 1, 1), "SOL.MARY_MOTHER_OF_GOD")
    jan = lambda n: dt.date(y + 1, 1, n)                                    # noqa: E731
    tracks: dict[str, list] = {E6: [], ESUN: []}
    # Epiphany on 6 January; Baptism on the following Sunday
    for n in range(2, 6):
        tracks[E6].append((jan(n), "CHR.2.SUN" if jan(n).weekday() == 6 else f"CHR.JAN{n:02d}"))
    tracks[E6].append((jan(6), "SOL.EPIPHANY"))
    bap = next(jan(n) for n in range(7, 14) if jan(n).weekday() == 6)
    tracks[E6] += [(jan(n), f"CHR.POSTEPI.JAN{n:02d}") for n in range(7, bap.day)] + [(bap, "FEAST.BAPTISM")]
    # Epiphany on the Sunday between 2 and 8 January; Baptism on the next Sunday, or on Monday after 7/8 January
    s = next(jan(n) for n in range(2, 9) if jan(n).weekday() == 6)
    tracks[ESUN] += [(jan(n), f"CHR.JAN{n:02d}") for n in range(2, s.day)] + [(s, "SOL.EPIPHANY")]
    bap = s + day if s.day >= 7 else s + 7 * day
    # the k-th weekday after Epiphany takes the texts of (6+k) January (module docstring)
    tracks[ESUN] += [(jan(n), f"CHR.POSTEPI.JAN{6 + n - s.day:02d}") for n in range(s.day + 1, bap.day)]
    tracks[ESUN] += [(bap, "FEAST.BAPTISM")]
    both = set(tracks[E6]) & set(tracks[ESUN])
    for d, key in sorted(both):
        add(d, key)
    for t, items in tracks.items():
        for d, key in items:
            if (d, key) not in both:
                add(d, key, t)
    return sorted(out, key=lambda r: (r[0], r[3] or ""))


def track(page: int) -> str | None:
    for p0, p1, lab in TRACKS:
        if p0 <= page <= p1:
            return lab
    return None


def refine_hour(hr, info: dict, copy: str | None) -> tuple[dict, str | None]:
    """Build hook (lh/model/build.py): weekdays after Epiphany get their own key; one-track days get the track."""
    if copy not in EPIPHANY:             # appendix (ALIA EX ORDINARIO, vigil canticles)
        return info, copy
    t = track(hr.page_start)
    m = re.match(r"^CHR\.JAN(\d\d)$", info["key"])
    if m and hr.page_start > EPIPHANY[copy]:
        n = 6 + int(m.group(1)) - _epiphany_day(copy, t)      # texts of n January
        info = {**info, "key": f"CHR.POSTEPI.JAN{n:02d}", "title": f"Weekday after Epiphany ({n} January)"}
    return info, (f"{copy}, {t}" if t else copy)


def _epiphany_day(copy: str, t: str | None) -> int:
    """Day of January on which this copy/track celebrates the Epiphany."""
    return next(d.day for d, k, _, tr in _calendar(copy) if k == "SOL.EPIPHANY" and tr in (t, None))


_CAL: dict = {}


def _calendar(copy: str) -> list[tuple]:
    if copy not in _CAL:
        _CAL[copy] = calendar(copy)
    return _CAL[copy]

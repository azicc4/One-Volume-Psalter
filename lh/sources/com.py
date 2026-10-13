"""COM — LH-Communia.pdf: the Commons (Communia) and the Office of the Dead (Officium Defunctorum).

Layout (1699 pages; see docs/source-pdf-format.md §5):
  * the ten Commons are printed four times, once per season (COPIES): Advent/Christmas 4–416, Lent 417–817,
    Easter 818–1207, Per annum 1208–1640. Each copy opens with a one-page index (blue links to its Commons plus two
    general rubrics). The Per annum copy alone adds the Saturday memorial of the BVM (1289–1304).
  * each Common is a 16.6pt title ("COMMUNE PASTORUM", "COMMUNE MARTYRUM: / PRO UNO MARTYRE") followed by its hours
    (I Vespers, Compline after I Vespers, Invitatory, Office of Readings, Lauds, Daytime Prayer, II Vespers,
    Compline after II Vespers);
  * sub-variants of a Common (Pro papa:, Pro episcopo:, Pro virgine:, In ipsa ecclesia dedicata: …) are red rubrics
    inside the hours; the parser turns them into `cond = {"for": "Pro papa"}` on the following element(s);
  * the Office of the Dead (20.2pt "OFFICIUM DEFUNCTORUM", 1641–1675) has no 16.6pt title: hours follow directly;
  * the volume ends with the unoutlined ALIA EX ORDINARIO appendix (1676–1699), parsed by lh/parse/appendix.py.

Day keys: COMMON.<NAME>[.<VARIANT>], DEAD, and MEM.BVM_SATURDAY (shared with PA); the seasonal copy is
hour_instance.copy (ADV / LENT / EAS / OT).
"""
from __future__ import annotations

import re

KEY = "COM"
TITLE = "Communia et Officium Defunctorum"
NON_CONTENT = [
    (1, 3, "cover, title page and volume index (links to the four seasonal copies and the Office of the Dead)"),
    # each seasonal copy opens with a one-page index of links to its Commons; its two general rubrics are recorded
    # as day_extra lines (source_line) and so count as covered
    (4, 4, "copy index (Advent/Christmas)"), (417, 417, "copy index (Lent)"), (818, 818, "copy index (Easter)"),
    (1208, 1208, "copy index (Per annum)"),
]
COPIES = [(4, 416, "ADV"), (417, 817, "LENT"), (818, 1207, "EAS"), (1208, 1640, "OT")]
SEASON_NAMES = {"ADV": "Advent and Christmas Time", "LENT": "Lent", "EAS": "Easter Time", "OT": "Ordinary Time"}

# 16.6pt day title (lines joined with " / ") -> (key, English name)
COMMONS = {
    "COMMUNE DEDICATIONIS ECCLESIÆ": ("COMMON.DEDICATION", "Common of the Dedication of a Church"),
    "COMMUNE BEATÆ MARIÆ VIRGINIS": ("COMMON.BVM", "Common of the Blessed Virgin Mary"),
    "COMMUNE APOSTOLORUM": ("COMMON.APOSTLES", "Common of Apostles"),
    "COMMUNE MARTYRUM: / PRO PLURIBUS MARTYRIBUS": ("COMMON.MARTYRS.SEVERAL", "Common of Several Martyrs"),
    "COMMUNE MARTYRUM: / PRO UNO MARTYRE": ("COMMON.MARTYRS.ONE", "Common of One Martyr"),
    "COMMUNE PASTORUM": ("COMMON.PASTORS", "Common of Pastors"),
    "COMMUNE DOCTORUM ECCLESIÆ": ("COMMON.DOCTORS", "Common of Doctors of the Church"),
    "COMMUNE VIRGINUM": ("COMMON.VIRGINS", "Common of Virgins"),
    "COMMUNE SANCTORUM VIRORUM": ("COMMON.HOLY_MEN", "Common of Holy Men"),
    "COMMUNE SANCTARUM MULIERUM": ("COMMON.HOLY_WOMEN", "Common of Holy Women"),
}

# ------------------------------------------------------------------------------------- structure (lh/verify/checks.py)
# (day_key, hour) -> {"missing": [slots excused], "reason": …}: hours where the Commons do not print a GILH slot.
_ONE_ORATION = ("GILH 236: at Terce, Sext and None the prayer is that of the day; the Commons print it once, after None, "
                "for all three hours (layout C/E in docs/source-pdf-format.md).")
_APOSTLES = ("GILH 234-235: the Common of Apostles gives no oration (every Apostle has his own) and refers to the "
             "Proper: 'Oratio, ut in Proprio de Sanctis.'")
STRUCTURE_EXCEPTIONS = {
    **{(k, "MIDDAY"): {"missing": ["ORATIOx3"], "reason": _ONE_ORATION}
       for k in ("COMMON.DEDICATION", "COMMON.BVM", "COMMON.MARTYRS.SEVERAL", "COMMON.MARTYRS.ONE", "COMMON.PASTORS",
                 "COMMON.VIRGINS", "COMMON.HOLY_MEN", "COMMON.HOLY_WOMEN", "DEAD")},
    ("COMMON.APOSTLES", "V1"): {"missing": ["ORATIO"], "reason": _APOSTLES},
    ("COMMON.APOSTLES", "V2"): {"missing": ["ORATIO"], "reason": _APOSTLES},
    ("COMMON.APOSTLES", "MIDDAY"): {"missing": ["ORATIO", "ORATIOx3"], "reason": _APOSTLES},
    ("COMMON.APOSTLES", "LAUDS"): {
        "missing": ["HYMN", "ORATIO"],
        "reason": _APOSTLES + " Lauds: 'HYMNUS, ut in Proprio de Sanctis.' in the Advent and Per annum copies (COM 95, "
                  "1318); Lent and Easter print a seasonal hymn."},
    ("COMMON.APOSTLES", "OR"): {
        "missing": ["HYMN", "LECT2", "RESP2", "ORATIO"],
        "reason": _APOSTLES + " Office of Readings: 'Lectio altera sumitur e Proprio de Sanctis.' (GILH 166); the "
                  "Lent and Easter copies also take the hymn from the Proper (COM 500, 900)."},
    # source omissions of Ordinary formulas (no proper text lost): TODO.md §3 T-COM-1
    ("COMMON.DOCTORS", "LAUDS"): {
        "missing": ["CONCLUSION"],
        "reason": "Lauds of the Common of Doctors ends with the oration, no 'Conclusio Horæ, ut in Ordinario.' (GILH 54), "
                  "in all four copies (COM 260, 666, 1061, 1484). TODO §3 T-COM-1."},
    ("COMMON.DOCTORS", "MIDDAY"): {
        "missing": ["OPENING", "ORATIOx3"],
        "reason": "No opening verse (GILH 41) before 'Ad Tertiam' in COM 1484, 666 and 260 (the Easter copy, 1061, has "
                  "it); " + _ONE_ORATION + " TODO §3 T-COM-1."},
    ("MEM.BVM_SATURDAY", "LAUDS"): {
        "missing": ["CONCLUSION"],
        "reason": "COM 1304: the Saturday BVM Lauds ends with the orations, no 'Conclusio Horæ' (GILH 54); the same "
                  "office in PA (6279) has it. TODO §3 T-COM-1."},
}
# No index check: the volume's index pages (3, 4, 417, 818, 1208, 1641) list the Commons by name only, without the
# hour codes check_index reads; the outline (level 3 = hours of each Common) is checked by tests/test_com.py.


def classify_lines(lines) -> None:
    """Hook called by lh/extract/lines.py: a line of prayer text that opens with the red name placeholder "N." or
    "N. et N." (COM 1595 "N. intercéssio tríbuat…", at a page top) is text, not a rubric (the placeholder stays as text)."""
    for L in lines:
        r0 = L.runs[0]
        if L.kind == "rubric" and r0.red and r0.text.strip() in ("N.", "N. et N."):
            rest = [r for r in L.runs[1:] if not r.red and r.text.strip()]
            if rest:
                L.kind = "italic" if rest[0].italic else "text"


def day_info(section: str, day: str) -> dict:
    if section == "OFFICIUM DEFUNCTORUM":
        # no 16.6pt title: the hours follow the 20.2pt section heading directly (day still holds the last Common)
        return {"key": "DEAD", "season": "DEAD", "week": None, "weekday": None, "psalter_week": None,
                "title": "Office for the Dead", "rank": "office_of_the_dead", "precedence": None}
    if day == "MEMORIA SANCTÆ MARIÆ IN SABBATO":
        # the same office as PA's appendix (PA 6269–6290, lh/sources/pa.py APPENDIX_DAYS): same day key, so that the
        # two printings collapse; here it is a day of the Per annum copy (COM 1289–1304)
        from lh.sources.pa import APPENDIX_DAYS
        return dict(APPENDIX_DAYS[day])
    if day in COMMONS:
        key, name = COMMONS[day]
        return {"key": key, "season": "COMMON", "week": None, "weekday": None, "psalter_week": None,
                "title": name, "rank": "common", "precedence": None}
    raise ValueError(f"unmapped Communia section {section!r} / day {day!r}")


# ------------------------------------------------------------------------------- seasonal copies: reports/com_copies.md

COPY_ORDER = ["ADV", "LENT", "EAS", "OT"]
_SKIP_TYPES = ("label", "marker", "rubric", "link", "ordinary_ref")
_COMMON_ORDER = ["COMMON.DEDICATION", "COMMON.BVM", "COMMON.APOSTLES", "COMMON.MARTYRS.SEVERAL", "COMMON.MARTYRS.ONE",
                 "COMMON.PASTORS", "COMMON.DOCTORS", "COMMON.VIRGINS", "COMMON.HOLY_MEN", "COMMON.HOLY_WOMEN"]
_HOUR_ORDER = ["V1", "COMPLINE1", "INV", "OR", "LAUDS", "MIDDAY", "V2", "COMPLINE"]


def _fold_alleluia(text: str) -> str:
    """Text without accents, punctuation and allelúia: Easter-copy variants differ from the others only by alleluias."""
    from lh.model.canon import fold
    return " ".join(re.findall(r"[a-z0-9]+", fold(text).replace("alleluia", " ")))


def copies_report(db=None) -> dict:
    """Align each Common's hours across the four seasonal copies (element by slot, sub-hour, condition and order) and
    list what differs. Writes reports/com_copies.md; returns the summary counts."""
    import collections
    import sqlite3

    from rapidfuzz import fuzz

    from lh.config import DB_PATH, REPORTS
    con = sqlite3.connect(db or DB_PATH)
    rows = con.execute(
        """SELECT h.day_key, h.hour, h.copy, o.slot, o.sub, coalesce(o.cond, ''), o.object_id, o.page, ob.plain
           FROM occurrence o JOIN hour_instance h ON h.id = o.hour_id JOIN object ob ON ob.id = o.object_id
           WHERE h.source = 'COM' AND h.copy IN ('ADV', 'LENT', 'EAS', 'OT') AND o.type NOT IN (%s)
           ORDER BY o.id""" % ",".join("?" * len(_SKIP_TYPES)), _SKIP_TYPES).fetchall()
    days = dict(con.execute("SELECT key, title FROM day").fetchall())
    con.close()
    # (day, hour) -> (slot, sub, cond, n-th) -> copy -> (object, page, plain)
    table: dict = collections.defaultdict(lambda: collections.defaultdict(dict))
    seen: collections.Counter = collections.Counter()
    for day, hour, copy, slot, sub, cond, oid, page, plain in rows:
        k = (day, hour, copy, slot, sub, cond)
        seen[k] += 1
        table[(day, hour)][(slot, sub, cond, seen[k])][copy] = (oid, page, plain)
    stats: collections.Counter = collections.Counter()
    out: dict = collections.defaultdict(list)
    for dh, elems in table.items():
        copies_here = {c for e in elems.values() for c in e}
        if len(copies_here) < 2:
            continue                                     # printed in one copy only (Saturday BVM)
        for key, per in elems.items():
            stats["elements"] += 1
            if len(per) < len(copies_here):
                kind = "only in " + "/".join(c for c in COPY_ORDER if c in per)
                stats["partial"] += 1
            elif len({v[0] for v in per.values()}) == 1:
                stats["identical"] += 1
                continue
            elif len({v[2].lower().count("allelúia") for v in per.values()}) > 1 and (
                    len({_fold_alleluia(v[2]) for v in per.values()}) == 1
                    or len({frozenset(_fold_alleluia(v[2]).split()) for v in per.values()}) == 1):
                kind = "alleluia"     # same words; Easter short responsories also move the "*" ("… * Allelúia, allelúia")
                stats[kind] += 1
            elif min(fuzz.ratio(_fold_alleluia(a[2]), _fold_alleluia(b[2]))
                     for a in per.values() for b in per.values()) >= 90:
                kind = "variant"      # nearly the same text: a spelling/punctuation/word variant between copies
                stats[kind] += 1
            else:
                kind = "text"
                stats[kind] += 1
            out[dh].append((key, kind, per))
    L = ["# Commons — differences between the four seasonal copies", "",
         "Generated by `python -m lh.sources.com` from `build/lh.sqlite` (after `python -m lh build … COM`). "
         "LH-Communia.pdf prints every Common four times: Advent/Christmas (ADV, pp. 4–416), Lent (LENT, 417–817), "
         "Easter (EAS, 818–1207), Per annum (OT, 1208–1640). Elements are aligned by hour, slot, sub-hour, condition "
         "(`cond`: sub-variant, alternative) and order. An element that is the same object in every copy has collapsed "
         "and is not listed.", "",
         "| | Elements |", "|---|---|",
         f"| Aligned elements (Commons × hours × slots) | {stats['elements']:,} |",
         f"| Identical in every copy (one object) | {stats['identical']:,} |",
         f"| Differ only by *allelúia* (Easter copy; Lent openings without *Allelúia*) | {stats['alleluia']:,} |",
         f"| Nearly identical: spelling, punctuation or a word (source discrepancy to review) | {stats['variant']:,} |",
         f"| Different texts (seasonal hymns, antiphons, readings, Compline of Sunday …) | {stats['text']:,} |",
         f"| Printed in some copies only | {stats['partial']:,} |", "",
         "Kind: **alleluia** = the same words apart from *allelúia* (Easter short responsories also move the `*`); "
         "**variant** = nearly the same text (≥ 90 % similar) — see TODO.md §3 T-COM-2; **text** = different texts; "
         "**only in …** = the element exists only in the copies named. `= ADV` = the same object as printed in that copy. "
         "Pages are LH-Communia.pdf pages.", ""]

    def cell(v):
        return f"{v[2][:100].replace('|', '/')}{'…' if len(v[2]) > 100 else ''} (p. {v[1]})"

    def sort_key(dh):
        return (_COMMON_ORDER.index(dh[0]) if dh[0] in _COMMON_ORDER else 99,
                _HOUR_ORDER.index(dh[1]) if dh[1] in _HOUR_ORDER else 99)

    for dh in sorted(out, key=sort_key):
        L += [f"## {days.get(dh[0], dh[0])} — {dh[1]} (`{dh[0]}`)", "",
              "| Slot | Kind | " + " | ".join(COPY_ORDER) + " |", "|---|---|" + "---|" * len(COPY_ORDER)]
        for (slot, sub, cond, n), kind, per in out[dh]:
            label = slot + (f"@{sub}" if sub else "") + (f" {cond}" if cond else "") + (f" #{n}" if n > 1 else "")
            shown: dict = {}                     # object -> first copy where its text is shown
            cells = []
            for c in COPY_ORDER:
                if c not in per:
                    cells.append("—")
                elif per[c][0] in shown:
                    cells.append(f"= {shown[per[c][0]]} (p. {per[c][1]})")
                else:
                    shown[per[c][0]] = c
                    cells.append(cell(per[c]))
            L.append(f"| {label.replace('|', '/')} | {kind} | " + " | ".join(cells) + " |")
        L.append("")
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "com_copies.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return dict(stats)


if __name__ == "__main__":
    print(f"[com] reports/com_copies.md: {copies_report()}")

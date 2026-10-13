"""Compare Felix Just's psalter (seed) with the psalmody actually printed in the LH sources.

For every (psalter week, weekday, hour, slot) the LH side is gathered from all Ordinary-Time days that use that
psalter week (e.g. Week I = OT weeks 1, 5, 9 … 33) — they must agree with each other AND with Felix.
Writes table psalter_compare and reports/psalter_discrepancies.md.
"""
from __future__ import annotations

import collections
import json
import re
import sqlite3

from lh.config import DB_PATH, REPORTS
from lh.model.days import DAY_NAMES, HOUR_NAMES
from lh.psalter.felix import load_felix
from lh.model.canon import unit_verses
from lh.psalter.refs import fmt, parse_ref, psalm_ranges

STATUS_ORDER = ["different_text", "range_diff", "lh_inconsistent", "missing_lh", "letters_only", "match", "pending_seasonal"]
STATUS_LABEL = {
    "match": "Match",
    "letters_only": "Match (differs only in partial-verse letters a/b/c)",
    "range_diff": "Same psalm/canticle, different verses",
    "different_text": "Different psalm/canticle",
    "missing_lh": "Not found in LH extraction",
    "lh_inconsistent": "LH prints different texts in different weeks",
    "pending_seasonal": "Seasonal variant (checked when Advent/Lent/Easter volumes are parsed)",
}


def lh_units(con, seasons=("OT",)) -> dict:
    """(week, day, hour, slot) → {normalized ref string: {'ref':…, 'heading':…, 'pages':[…], 'partial':set}}"""
    q = """SELECT d.psalter_week, d.weekday, h.hour, o.slot, ob.type, ob.payload, o.extra, o.page, o.hour_id
           FROM occurrence o JOIN object ob ON ob.id=o.object_id JOIN hour_instance h ON h.id=o.hour_id
           JOIN day d ON d.key=h.day_key
           WHERE d.season IN ({}) AND d.rank IN ('sunday','weekday','privileged_weekday')
             AND d.psalter_week IS NOT NULL AND ob.type IN ('psalm','canticle')
             AND o.slot GLOB 'PS[0-9]*'"""
    out: dict = collections.defaultdict(dict)
    rows = con.execute(q.format(",".join(f"'{x}'" for x in seasons))).fetchall()
    # a unit that starts mid-verse means the previous unit of the same psalm (same hour) ends mid-verse
    starts = {}
    for pw, wd, hour, slot, otype, payload, extra, page, hid in rows:
        if otype == "psalm":
            p = json.loads(payload)
            starts[(hid, slot)] = (p["psalm"], unit_verses(p["lines"])[1])
    for pw, wd, hour, slot, otype, payload, extra, page, hid in rows:
        p, x = json.loads(payload), json.loads(extra or "{}")
        if otype == "psalm":
            base = int(re.match(r"\d+", p["psalm"]).group(0))
            verses, starts_mid = unit_verses(p["lines"])
            if starts_mid and verses and re.match(r"\d+", verses[0]):
                verses.insert(0, f"{int(re.match(r'\d+', verses[0]).group(0)) - 1}b")
            nxt = starts.get((hid, f"PS{int(slot[2:]) + 1}"))
            if nxt and nxt[0] == p["psalm"] and nxt[1] and verses:
                verses[-1] = re.sub(r"[a-c]*$", "a", verses[-1])
            whole = not x.get("range") and not x.get("section") and p["psalm"].isdigit()
            ranges = [(base, 1, None)] if whole else psalm_ranges(base, verses)
            partial = {v for v in verses if re.match(r"^\d+[a-c]+$", v)}
            heading = f"Psalmus {p['vulg']} ({p['psalm']})" + (f", {x['range']}" if x.get("range") else "")
            heading += f" {x['section']}" if x.get("section") else ""
            book = "Ps"
        else:
            try:
                book, ranges, partial = parse_ref(p["ref"])
            except ValueError:
                book, ranges, partial = "?", [], set()
            heading = p["ref"]
        hour_key = "COMPLINE" if hour == "COMPLINE" else hour
        key = (pw if hour not in ("COMPLINE", "COMPLINE1") else "*", wd, hour_key, slot)
        norm = fmt(book, ranges)
        ent = out[key].setdefault(norm, {"ref": norm, "book": book, "ranges": ranges, "heading": heading, "pages": [],
                                         "partial": set(partial), "vulg": p.get("vulg")})
        ent["pages"].append(page)
    return out


def lh_compline_lb(con) -> dict:
    q = """SELECT d.weekday, h.hour, ob.payload, o.page FROM occurrence o JOIN object ob ON ob.id=o.object_id
           JOIN hour_instance h ON h.id=o.hour_id JOIN day d ON d.key=h.day_key
           WHERE h.hour IN ('COMPLINE','COMPLINE1') AND o.slot='LB' AND d.season='OT' AND d.rank IN ('sunday','weekday')"""
    out: dict = collections.defaultdict(dict)
    for wd, hour, payload, page in con.execute(q):
        ref = json.loads(payload).get("ref", "").strip("() ")
        out[("*", wd, hour, "LB")].setdefault(ref, {"ref": ref, "heading": ref, "pages": [], "partial": set()})["pages"].append(page)
    return out


def classify(felix_ref: str, lh: dict) -> tuple[str, str]:
    if not lh:
        return "missing_lh", ""
    try:
        fb, fr, fp = parse_ref(felix_ref)
    except ValueError as e:
        return "different_text", f"unparseable Felix ref: {e}"
    if len(lh) > 1:
        return "lh_inconsistent", "; ".join(f"{k} (pp. {', '.join(map(str, v['pages'][:4]))})" for k, v in lh.items())
    ent = next(iter(lh.values()))
    if ent["book"] != fb:
        return "different_text", ""
    lr = ent["ranges"]
    if fb == "Ps" and {r[0] for r in fr} != {r[0] for r in lr}:
        return "different_text", ""
    f_whole = len(fr) == 1 and fr[0][2] is None
    l_whole = len(lr) == 1 and lr[0][2] is None
    if f_whole and l_whole:
        return "match", ""
    if f_whole != l_whole:
        return "range_diff", "one side gives the whole psalm, the other a verse range"
    if fmt(fb, fr) == fmt(fb, lr):
        return ("match", "") if fp == ent["partial"] else ("letters_only", f"Felix {sorted(fp)} vs LH {sorted(ent['partial'])}")
    return "range_diff", ""


def compare(db=DB_PATH) -> dict:
    con = sqlite3.connect(db)
    con.execute("DROP TABLE IF EXISTS psalter_compare")
    con.execute("""CREATE TABLE psalter_compare (week TEXT, day TEXT, hour TEXT, slot TEXT, felix_ref TEXT, season TEXT,
                   lh_ref TEXT, lh_heading TEXT, pages TEXT, status TEXT, detail TEXT)""")
    lh = lh_units(con)
    lh.update(lh_compline_lb(con))
    seasonal = lh_units(con, ("ADV", "LENT", "EAS"))
    results = []
    for r in load_felix():
        if r["hour"].startswith("COMPLEMENTARY"):
            continue   # checked against the Ordinary appendix (lh/parse/appendix.py)
        week = r["week"] if r["week"] == "*" else int(r["week"])
        key = (week, r["day"], r["hour"], r["slot"])
        units = lh.get(key, {})
        if r["season"] == "seasonal":
            units = seasonal.get(key, {})
            status, detail = classify(r["ref"], units) if units else ("pending_seasonal", "")
            if units:
                detail = (detail + " " if detail else "") + "(checked against Advent/Lent/Easter weeks)"
        elif r["slot"] == "LB":
            ent = next(iter(units.values()), None)
            try:
                same = ent and fmt(*parse_ref(r["ref"].replace("1 Peter", "1 Pet"))[:2]) == fmt(*parse_ref(ent["ref"])[:2])
            except ValueError:
                same = False
            status, detail = ("match", "") if same else ("range_diff" if ent else "missing_lh", "")
        else:
            status, detail = classify(r["ref"], units)
        ent = next(iter(units.values()), {})
        row = {"week": str(week), "day": r["day"], "hour": r["hour"], "slot": r["slot"], "felix_ref": r["ref"],
               "season": r["season"], "lh_ref": "; ".join(units) if units else "",
               "lh_heading": ent.get("heading", ""), "pages": ",".join(map(str, sorted(set(ent.get("pages", [])))[:12])),
               "status": status, "detail": detail or r.get("note", "")}
        results.append(row)
    con.executemany("INSERT INTO psalter_compare VALUES (:week,:day,:hour,:slot,:felix_ref,:season,:lh_ref,:lh_heading,:pages,:status,:detail)", results)
    con.commit()
    con.close()
    write_report(results)
    return collections.Counter(r["status"] for r in results)


def write_report(results: list[dict]) -> None:
    REPORTS.mkdir(exist_ok=True)
    counts = collections.Counter(r["status"] for r in results)
    L = ["# Psalter cross-check: Felix Just vs. Liturgia Horarum (Per annum)", "",
         "Generated by `python -m lh psalter`. Seed: `data/seed/felix_just_psalter.csv` (from catholic-resources.org/LoH, "
         "US LOTH, Hebrew numbering). LH side: every Ordinary-Time week that uses the given psalter week must print the "
         "same psalm portion (Week I = OT 1, 5, 9 … 33). Page numbers are pages of `LH-Per_annum.pdf`.", "",
         "| Status | Rows |", "|---|---|"]
    for s in STATUS_ORDER:
        if counts.get(s):
            L.append(f"| {STATUS_LABEL[s]} | {counts[s]} |")
    L += ["", f"Total rows compared: {len(results)}", ""]
    for s in STATUS_ORDER:
        rows = [r for r in results if r["status"] == s]
        if not rows or s in ("match", "pending_seasonal"):
            continue
        L += [f"## {STATUS_LABEL[s]} ({len(rows)})", "", "| Week | Day | Hour | Slot | Felix Just | LH (Hebrew numbering) | LH heading | PDF pages | Note |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            L.append(f"| {r['week']} | {DAY_NAMES.get(r['day'], r['day'])} | {HOUR_NAMES.get(r['hour'], r['hour'])} | {r['slot']} | "
                     f"{r['felix_ref']} | {r['lh_ref']} | {r['lh_heading']} | {r['pages']} | {r['detail']} |")
        L.append("")
    pend = [r for r in results if r["status"] == "pending_seasonal"]
    if pend:
        L += ["## Seasonal variants not yet checked", "",
              "Felix marks these Office of Readings rows as used only in Advent/Christmas/Lent/Easter (vols. 1–2). They will be "
              "verified when `LH-Adventus_et_Nativitatis.pdf` and `LH-Quadragesimae_et_Paschae.pdf` are parsed.", ""]
        L += [f"- Week {r['week']} {DAY_NAMES.get(r['day'])} {r['slot']}: {r['felix_ref']}" for r in pend]
    (REPORTS / "psalter_discrepancies.md").write_text("\n".join(L) + "\n", encoding="utf-8")

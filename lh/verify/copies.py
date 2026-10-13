"""Duplicate copies inside one source: do they collapse to the same objects?

A source plug-in with COPIES prints the same days several times (ADV: once per possible start date of Advent,
27 Nov … 3 Dec). Every hour instance carries its copy label in hour_instance.copy ("28 Nov", or
"28 Nov, Epiphany Sunday" for a day printed on one Christmas track only). This check groups the printings of each
day/hour and compares their objects slot by slot:

  * identical in every copy  → the copies collapse (one set of objects, n_occ = number of printings);
  * psalmody differs only     → expected: the day falls on a different weekday, so the four-week psalter differs;
  * anything else             → listed for review (a calendar difference, or a source discrepancy).

If the plug-in has `calendar(copy)` (the days each copy must print, computed from its start date), the printed days
are checked against it, and the printed weekday of each dated day ("FERIA II" in its title or hour subtitle) against
the computed one. The psalter week each dated day uses is inferred by matching its psalms with the Ordinary-Time
psalter (PA). Writes reports/<key>_copies.md (python -m lh verify).
"""
from __future__ import annotations

import collections
import json
import re
import sqlite3

from lh.config import DB_PATH, REPORTS
from lh.model.days import weekday_of
from lh.sources import plugin

IGNORE = {"rubric", "link", "ordinary_ref"}            # navigation and rubrics: compared separately
PSALMODY = re.compile(r"^(ANT\d?|PS\d)(_R)?$")
HOUR_ORDER = ["V1", "COMPLINE1", "INV", "OR", "LAUDS", "MIDDAY", "VESPERS", "V2", "COMPLINE"]
WD = {"SUN": "Sun", "MON": "Mon", "TUE": "Tue", "WED": "Wed", "THU": "Thu", "FRI": "Fri", "SAT": "Sat"}
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}


def _base(copy: str | None) -> str:
    return re.sub(r" #\d+$", "", (copy or "").split(",")[0])


def _track(copy: str | None) -> str | None:
    """'28 Nov, Epiphany Sunday' → 'Epiphany Sunday'; '28 Nov' → None (a '#2' duplicate marker is dropped)."""
    if not copy or ", " not in copy:
        return None
    return re.sub(r" #\d+$", "", copy.split(", ", 1)[1])


def _cell(s: str) -> str:
    return s.replace("|", "/")


def copies_report(source: str, db=DB_PATH) -> dict | None:
    p = plugin(source)
    if not getattr(p, "COPIES", None):
        return None
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    hours = con.execute("""SELECT id, day_key, hour, copy, page_start, page_end, day_title FROM hour_instance
                           WHERE source=? AND copy IS NOT NULL ORDER BY id""", (source,)).fetchall()
    occ = collections.defaultdict(list)
    weekday = {}
    for r in con.execute("""SELECT o.hour_id, o.seq, o.type, o.slot, o.sub, o.cond, o.object_id, o.page, o.extra
                            FROM occurrence o JOIN hour_instance h ON h.id=o.hour_id WHERE h.source=? ORDER BY o.hour_id, o.seq""",
                         (source,)):
        if r["slot"] == "SUBTITLE" and r["hour_id"] not in weekday:
            wd = weekday_of(json.loads(r["extra"] or "{}").get("text", "").upper())
            if wd:
                weekday[r["hour_id"]] = wd
        if r["object_id"]:
            occ[r["hour_id"]].append(r)
    for h in hours:
        weekday.setdefault(h["id"], weekday_of(h["day_title"] or ""))
    printed_wd = dict(weekday)
    cal = getattr(p, "calendar", None)
    if cal:          # the computed weekday wins (octave days print none); printed ones are checked further down
        cwd = {}
        for _, _, lab in p.COPIES:
            for _, k, wd, t in cal(lab):
                cwd[(lab, k, t)] = wd
        for h in hours:
            b, t = _base(h["copy"]), _track(h["copy"])
            wd = cwd.get((b, h["day_key"], t)) or cwd.get((b, h["day_key"], None))
            if wd:
                weekday[h["id"]] = wd
    plain = {r[0]: r[1] for r in con.execute("SELECT id, plain FROM object")}
    psalter = _psalter_index(con)
    notes = getattr(p, "COPY_NOTES", {}) or {}

    # ---- group printings per day/hour and compare
    by_dh = collections.defaultdict(list)
    for h in hours:
        by_dh[(h["day_key"], h["hour"])].append(h)
    rows, rubric_only, n_multi, n_same = [], [], 0, 0
    for (dk, hr), insts in sorted(by_dh.items(), key=lambda kv: (kv[0][0], _hord(kv[0][1]))):
        if len(insts) < 2:
            continue
        n_multi += 1
        sig = {h["id"]: _sig(occ[h["id"]], content=True) for h in insts}
        full = {h["id"]: _sig(occ[h["id"]], content=False) for h in insts}
        if len(set(sig.values())) == 1:
            n_same += 1
            if len(set(full.values())) > 1:
                rubric_only.append((dk, hr, insts))
            continue
        groups = collections.OrderedDict()
        for h in insts:
            groups.setdefault(sig[h["id"]], []).append(h)
        slots = _diff_slots([occ[g[0]["id"]] for g in groups.values()])
        # weekdays per variant: a difference is explained by the weekday only if no two variants share a weekday
        gwd = [{weekday.get(h["id"]) for h in g} for g in groups.values()]
        distinct = all(not (a & b) for i, a in enumerate(gwd) for b in gwd[i + 1:])
        note = notes.get((dk, hr)) or notes.get((dk, "*"))
        if distinct and all(PSALMODY.match(s[0]) for s in slots):
            kind = "psalter"
        elif distinct and hr in ("COMPLINE", "COMPLINE1"):
            kind = "compline"
        elif note:
            kind = "explained"
        else:
            kind = "review"
        rows.append({"day": dk, "hour": hr, "kind": kind, "groups": list(groups.values()), "slots": slots,
                     "weekdays": gwd, "note": note})

    # ---- calendar check
    cal_rows, wd_table = [], collections.defaultdict(dict)
    printed = collections.defaultdict(set)
    printed_tracks = collections.defaultdict(set)
    for h in hours:
        printed[_base(h["copy"])].add(h["day_key"])
        printed_tracks[(_base(h["copy"]), h["day_key"])].add(_track(h["copy"]))
    cal = getattr(p, "calendar", None)
    if cal:
        for _, _, lab in p.COPIES:
            exp = cal(lab)
            keys = {k for _, k, _, _ in exp}
            for d, k, wd, t in exp:
                if k not in printed[lab]:
                    cal_rows.append((lab, d, k, t, "not printed"))
            for k in sorted(printed[lab] - keys):
                cal_rows.append((lab, None, k, None, "printed, but not in the calendar of this copy"))
            for k in sorted(printed[lab] & keys):         # a track label must match that track's calendar
                for t in sorted(printed_tracks[(lab, k)] - {None}):
                    if not any(k2 == k and t2 in (t, None) for _, k2, _, t2 in exp):
                        cal_rows.append((lab, None, k, t, "printed under this track, but not in its calendar"))
            for d, k, wd, t in exp:
                if re.match(r"^(ADV\.DEC|CHR\.(JAN|POSTEPI|2\.SUN))", k):
                    pr = {printed_wd.get(h["id"]) for h in hours if _base(h["copy"]) == lab and h["day_key"] == k
                          and (t is None or _track(h["copy"]) in (t, None))}
                    pw = _psalter_week(con, source, lab, k, t, psalter)
                    wd_table[k][(lab, t)] = (d, wd, pr - {None}, pw)
    con.close()
    out = {"source": source, "hours": len(hours), "day_hours": len(by_dh), "multi": n_multi, "same": n_same,
           "differ": rows, "rubric_only": rubric_only, "calendar": cal_rows, "weekdays": wd_table}
    _write(out, p, plain)
    return {"multi": n_multi, "same": n_same, "differ": len(rows),
            "explained": sum(1 for r in rows if r["kind"] == "explained"),
            "review": sum(1 for r in rows if r["kind"] == "review"), "calendar": len(cal_rows)}


def _hord(h):
    return HOUR_ORDER.index(h) if h in HOUR_ORDER else 99


def _sig(occs, content: bool) -> tuple:
    return tuple((o["slot"], o["sub"], o["cond"] or "", o["object_id"]) for o in occs
                 if not (content and o["type"] in IGNORE))


def _diff_slots(variants: list[list]) -> list[tuple]:
    """Slot keys (slot, sub, cond) whose objects differ between the variants; per variant the object ids + page."""
    per = []
    for occs in variants:
        d = collections.defaultdict(list)
        for o in occs:
            if o["type"] not in IGNORE:
                d[(o["slot"], o["sub"] or "", o["cond"] or "")].append((o["object_id"], o["page"]))
        per.append(d)
    keys = []
    for d in per:
        for k in d:
            if k not in keys:
                keys.append(k)
    out = []
    for k in keys:
        vals = [tuple(x[0] for x in d.get(k, [])) for d in per]
        if len(set(vals)) > 1:
            out.append((k[0], k[1], k[2], [d.get(k, []) for d in per]))
    return out


def _psalter_index(con) -> dict:
    """(hour, weekday, (PS1, PS2, PS3 object ids)) → Ordinary-Time psalter weeks, from the Per annum volume."""
    idx = collections.defaultdict(set)
    q = """SELECT h.id, h.hour, d.weekday, d.psalter_week FROM hour_instance h JOIN day d ON d.key=h.day_key
           WHERE h.source='PA' AND d.season='OT' AND d.rank IN ('sunday','weekday') AND d.psalter_week IS NOT NULL"""
    for hid, hr, wd, pw in con.execute(q).fetchall():
        ps = tuple(r[0] for r in con.execute("""SELECT object_id FROM occurrence WHERE hour_id=? AND slot GLOB 'PS[0-9]'
                                                ORDER BY seq""", (hid,)))
        if ps:
            idx[(hr, wd, ps)].add(pw)
    return idx


def _psalter_week(con, source, copy, key, track, idx) -> str:
    """Psalter week whose psalms the day's Lauds/Vespers/Office of Readings use in this copy ('proper' if none)."""
    per_hour: list[set] = []
    proper = 0
    for h in con.execute("""SELECT id, hour, copy FROM hour_instance WHERE source=? AND day_key=? AND hour IN ('OR','LAUDS','VESPERS')
                            AND (copy=? OR copy LIKE ?)""", (source, key, copy, f"{copy},%")).fetchall():
        if track and _track(h[2]) not in (track, None):
            continue
        ps = tuple(r[0] for r in con.execute("SELECT object_id FROM occurrence WHERE hour_id=? AND slot GLOB 'PS[0-9]' ORDER BY seq",
                                              (h[0],)))
        hit = [pw for (hr, _, p), pws in idx.items() if hr == h[1] and p == ps for pw in pws]
        if hit:
            per_hour.append(set(hit))
        else:
            proper += 1
    if not per_hour:
        return "proper" if proper else ""
    # a psalm unit can belong to two weeks (Thursday OR, Ps 43, weeks II and IV): keep the weeks every hour agrees on
    weeks = set.intersection(*per_hour) or set.union(*per_hour)
    return "/".join(ROMAN[w] for w in sorted(weeks)) + (" (+proper)" if proper else "")


def _write(r: dict, p, plain: dict) -> None:
    src = r["source"]
    review = [x for x in r["differ"] if x["kind"] == "review"]
    psal = [x for x in r["differ"] if x["kind"] == "psalter"]
    compl = [x for x in r["differ"] if x["kind"] == "compline"]
    expl = [x for x in r["differ"] if x["kind"] == "explained"]
    L = [f"# Duplicate copies — {src} ({p.TITLE})", "",
         "Generated by `python -m lh verify` (`lh/verify/copies.py`). The volume prints the same days in "
         f"{len(p.COPIES)} copies ({', '.join(c[2] for c in p.COPIES)}); each printed hour carries its copy label "
         "(`hour_instance.copy`). Rubrics and navigation links are left out of the object comparison.", "",
         "| | Count |", "|---|---|",
         f"| Hour instances in the copies | {r['hours']:,} |",
         f"| Distinct day/hour keys | {r['day_hours']:,} |",
         f"| Day/hours printed more than once | {r['multi']:,} |",
         f"| … same objects in every printing (collapse) | {r['same']:,} |",
         f"| … psalmody differs only (weekday, so psalter, differs between copies) | {len(psal):,} |",
         f"| … Compline differs, on different weekdays (weekly Compline cycle) | {len(compl):,} |",
         f"| … other differences, explained (calendar, or a source discrepancy in `TODO.md` §3) | {len(expl):,} |",
         f"| … other differences, **unexplained** (review) | {len(review):,} |",
         f"| … same texts, different rubrics/links only | {len(r['rubric_only']):,} |",
         f"| Calendar check: days missing or unexpected | {len(r['calendar']):,} |", ""]
    if getattr(p, "calendar", None):
        L += ["## Calendar check", "",
              "Each copy's days computed from its start date (`calendar()` in the plug-in: Immaculate Conception moved "
              "to Monday when 8 December is a Sunday; Holy Family on the Sunday in the Octave, else 30 December; "
              "after the Octave the two tracks, Epiphany on 6 January or on the Sunday 2–8 January) against the days "
              "printed.", ""]
        if r["calendar"]:
            L += ["| Copy | Date | Day | Track | Finding |", "|---|---|---|---|---|"]
            L += [f"| {c} | {d.strftime('%d %b') if d else ''} | `{k}` | {t or 'both'} | {f} |" for c, d, k, t, f in r["calendar"]]
        else:
            L.append("Every copy prints exactly the days of its calendar.")
        L.append("")
        L += ["## Weekday and psalter week of the dated days", "",
              "Per copy: the date, the weekday it falls on (computed), the weekday printed in the day title or hour "
              "subtitle (`FERIA II` …) and the psalter week whose psalms the Office of Readings, Lauds and Vespers use "
              "(matched against the Per annum psalter; *proper* = no match, the day has its own psalms). "
              "A `!` marks a printed weekday that differs from the computed one.", "",
              "| Day | " + " | ".join(c[2] for c in p.COPIES) + " |", "|---|" + "---|" * len(p.COPIES)]
        for k in sorted(r["weekdays"], key=_daysort):
            cells = []
            for _, _, lab in p.COPIES:
                items = [(t, v) for (c, t), v in r["weekdays"][k].items() if c == lab]
                parts = []
                for t, (d, wd, pr, pw) in sorted(items, key=lambda x: x[0] or ""):
                    bad = (" (weekday not printed)" if not pr else "" if pr == {wd}
                           else " ! printed " + "/".join(WD[x] for x in sorted(pr)))
                    tr = {None: "", "Epiphany 6 Jan": " (E6)", "Epiphany Sunday": " (ESun)"}.get(t, f" ({t})")
                    parts.append(f"{d.day} {d.strftime('%b')} {WD[wd]}{tr} {pw}{bad}".strip())
                cells.append("<br>".join(parts))
            L.append(f"| `{k}` | " + " | ".join(cells) + " |")
        L.append("")
    L += ["## Day/hours whose objects differ between copies", "",
          "For each day/hour printed in more than one copy with different objects: the variants (copies and first page "
          "of the hour) and every slot that differs, with the object printed in each variant. "
          "*psalter* = only antiphons/psalms differ and the variants fall on different weekdays (expected); "
          "*compline* = Compline on different weekdays (expected: Compline follows the weekly cycle); "
          "*explained* = a calendar difference or a source discrepancy, with the note from the plug-in's `COPY_NOTES`; "
          "*review* = anything else.", ""]
    for x in review + expl + psal + compl:
        L.append(f"### `{x['day']}` {x['hour']} — {x['kind']}")
        L.append("")
        if x.get("note"):
            L += [f"> {x['note']}", ""]
        for i, (g, wds) in enumerate(zip(x["groups"], x["weekdays"]), 1):
            L.append(f"- Variant {chr(64 + i)} ({'/'.join(WD[w] for w in sorted(wds - {None})) or '?'}): "
                     + ", ".join(f"{h['copy']} (p. {h['page_start']})" for h in g))
        L += ["", "| Slot | " + " | ".join(f"Variant {chr(65 + i)}" for i in range(len(x["groups"]))) + " |",
              "|---|" + "---|" * len(x["groups"])]
        for slot, sub, cond, vals in x["slots"]:
            name = slot + (f"@{sub}" if sub else "") + (f" {cond}" if cond else "")
            cells = ["<br>".join(f"`{oid}` p.{pg}: {_cell(plain.get(oid, '')[:60])}" for oid, pg in v) or "—" for v in vals]
            L.append(f"| {_cell(name)} | " + " | ".join(cells) + " |")
        L.append("")
    if r["rubric_only"]:
        L += ["## Same texts, different rubrics or navigation links", "",
              "| Day | Hour | Printings |", "|---|---|---|"]
        for dk, hr, insts in r["rubric_only"]:
            L.append(f"| `{dk}` | {hr} | " + ", ".join(f"{h['copy']} p.{h['page_start']}" for h in insts) + " |")
        L.append("")
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"{src.lower()}_copies.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def _daysort(k: str):
    m = re.search(r"(DEC|JAN)(\d+)$", k)
    if m:
        return (0 if m.group(1) == "DEC" else 1, int(m.group(2)), k)
    return (1, 0, k)
